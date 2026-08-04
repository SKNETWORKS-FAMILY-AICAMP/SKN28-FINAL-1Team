"""캘린더 생성·조회·수정·삭제 비즈니스 로직."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q, QuerySet
from django.utils import timezone

from apps.style_calendar.contracts import (
    CalendarItemInternalStatus,
    CalendarProcessingErrorCode,
    CalendarSourceType,
    CalendarStatus,
)
from apps.style_calendar.models import (
    CalendarEntry,
    CalendarItem,
    CalendarWardrobeItem,
)
from apps.style_calendar.services import storage
from apps.wardrobe.models import WardrobeItem

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from apps.users.models import User

logger = logging.getLogger(__name__)


class WardrobeItemsNotFoundError(Exception):
    """요청 사용자가 소유하지 않은 옷장 아이템이 포함된 경우."""


class CalendarDateConflictError(Exception):
    """사용자의 해당 날짜 캘린더가 이미 존재하는 경우."""


class CalendarStorageError(Exception):
    """캘린더 소유 S3 경로로 이미지 복사 또는 정리에 실패한 경우."""


class CalendarDeletionNotFoundError(Exception):
    """삭제 대상 캘린더가 없거나 요청 사용자 소유가 아닌 경우."""


class CalendarDeletionConflictError(Exception):
    """이미지 처리가 끝나지 않아 안전하게 삭제할 수 없는 경우."""

    def __init__(self, current_status: str) -> None:
        self.current_status = current_status
        super().__init__("이미지 처리 중인 캘린더는 삭제할 수 없습니다.")


def entries_for_user(*, user) -> QuerySet[CalendarEntry]:
    """사용자 소유 캘린더와 조회 응답에 필요한 하위 데이터를 반환한다."""

    return CalendarEntry.objects.filter(user=user).prefetch_related(
        Prefetch(
            "wardrobe_links",
            queryset=CalendarWardrobeItem.objects.order_by("sort_order", "created_at"),
        ),
        Prefetch(
            "items",
            queryset=CalendarItem.objects.order_by("sort_order", "created_at"),
        ),
    )


def entries_in_period(
    *,
    user,
    start_date: date,
    end_date: date,
) -> QuerySet[CalendarEntry]:
    """시작일과 종료일을 모두 포함하는 사용자 캘린더 목록을 반환한다."""

    return entries_for_user(user=user).filter(
        date__gte=start_date,
        date__lte=end_date,
    )


def processing_statuses_for_user(*, user) -> QuerySet[CalendarEntry]:
    """처리 상태 응답에 필요한 아이템 집계를 포함한 사용자 캘린더 QuerySet."""

    return CalendarEntry.objects.filter(user=user).annotate(
        total_item_count=Count("items"),
        extracted_item_count=Count(
            "items",
            filter=Q(
                items__internal_status=CalendarItemInternalStatus.EXTRACTED.value
            ),
        ),
        failed_item_count=Count(
            "items",
            filter=Q(items__internal_status=CalendarItemInternalStatus.FAILED.value),
        ),
    )


@transaction.atomic
def delete_entry(*, user, calendar_id: UUID) -> None:
    """종료된 사용자 캘린더를 삭제하고 커밋 후 S3 prefix를 정리한다.

    callback과 같은 행 잠금을 사용해 완료 처리와 삭제가 동시에 반영되지 않게
    한다. DB 삭제가 성공한 뒤 S3 정리를 수행하므로 저장소 장애가 발생해도
    사용자에게 깨진 DB 참조를 남기지 않는다.
    """

    entry = (
        CalendarEntry.objects.select_for_update()
        .filter(pk=calendar_id, user=user)
        .first()
    )
    if entry is None:
        raise CalendarDeletionNotFoundError
    if entry.status not in {
        CalendarStatus.COMPLETED.value,
        CalendarStatus.FAILED.value,
    }:
        raise CalendarDeletionConflictError(entry.status)

    user_id = entry.user_id
    entry_id = entry.pk
    entry.delete()
    transaction.on_commit(
        lambda: _cleanup_deleted_calendar_s3(
            user_id=user_id,
            calendar_id=entry_id,
        )
    )


def _cleanup_deleted_calendar_s3(*, user_id: int | str, calendar_id: UUID) -> None:
    try:
        storage.delete_calendar(user_id, calendar_id)
    except Exception:
        # DB 삭제는 이미 커밋됐다. 사용자 요청을 실패로 되돌리지 않고 운영 로그로
        # 남겨 고아 S3 객체를 별도로 정리할 수 있게 한다.
        logger.exception(
            "삭제된 캘린더 S3 prefix 정리 실패: user_id=%s calendar_id=%s",
            user_id,
            calendar_id,
        )


def _wardrobe_snapshot(
    item: WardrobeItem,
    *,
    calendar_s3_key: str,
) -> dict[str, object]:
    """옷장 데이터 변경과 무관하게 캘린더에 남길 연결 시점 정보."""

    return {
        "id": str(item.pk),
        "s3_key": calendar_s3_key,
        "source_wardrobe_s3_key": item.s3_key,
        "item_name": item.item_name,
        "category_large": item.category_large,
        "category_small": item.category_small,
        "tags": {
            "season": list(item.season),
            "style": list(item.style),
            "color": item.color,
            "pattern": item.pattern,
            "fit": item.fit,
            "material": item.material,
            "sleeve": item.sleeve,
            "length": item.length,
            "usage": list(item.usage),
            "layer_role": item.layer_role,
            "layer_order": item.layer_order,
        },
    }


def _cleanup_s3_objects(keys: Sequence[str]) -> None:
    if not keys:
        return
    try:
        storage.delete_objects(keys)
    except Exception:
        logger.exception("캘린더 S3 객체 정리 실패: object_count=%s", len(keys))


def _owned_wardrobe_items(
    *,
    user: User,
    wardrobe_item_ids: Sequence[UUID],
) -> list[WardrobeItem]:
    owned_items = WardrobeItem.objects.filter(
        user=user,
        pk__in=wardrobe_item_ids,
    )
    item_by_id = {item.pk: item for item in owned_items}
    if len(item_by_id) != len(wardrobe_item_ids):
        raise WardrobeItemsNotFoundError
    return [item_by_id[item_id] for item_id in wardrobe_item_ids]


def _prepare_wardrobe_links(
    *,
    entry: CalendarEntry,
    ordered_items: Sequence[WardrobeItem],
) -> tuple[list[CalendarWardrobeItem], list[str]]:
    links: list[CalendarWardrobeItem] = []
    destination_keys: list[str] = []
    for sort_order, item in enumerate(ordered_items):
        link = CalendarWardrobeItem(
            calendar=entry,
            wardrobe_item=item,
            sort_order=sort_order,
        )
        destination_key = storage.selected_item_key(
            entry.user_id,
            entry.pk,
            link.pk,
            item.s3_key,
        )
        link.snapshot = _wardrobe_snapshot(
            item,
            calendar_s3_key=destination_key,
        )
        links.append(link)
        destination_keys.append(destination_key)
    return links, destination_keys


def _copy_wardrobe_images(
    *,
    ordered_items: Sequence[WardrobeItem],
    destination_keys: Sequence[str],
    stored_keys: list[str],
) -> None:
    for item, destination_key in zip(ordered_items, destination_keys, strict=True):
        storage.copy_wardrobe_item(item.s3_key, destination_key)
        stored_keys.append(destination_key)


def _save_entry_with_links(
    *,
    entry: CalendarEntry,
    links: Sequence[CalendarWardrobeItem],
    stored_keys: Sequence[str],
) -> None:
    try:
        with transaction.atomic():
            entry.save(force_insert=True)
            CalendarWardrobeItem.objects.bulk_create(links)
    except IntegrityError as exc:
        _cleanup_s3_objects(stored_keys)
        cause = getattr(exc, "__cause__", None)
        diag = getattr(cause, "diag", None)
        if getattr(diag, "constraint_name", None) == "uq_calendar_user_date":
            raise CalendarDateConflictError from exc
        raise
    except Exception:
        _cleanup_s3_objects(stored_keys)
        raise


def create_from_wardrobe(
    *,
    user: User,
    entry_date: date,
    wardrobe_item_ids: Sequence[UUID],
    schedule: str,
    tpo: list[str],
    hashtags: list[str],
) -> CalendarEntry:
    """사용자 소유 옷장 아이템을 직접 선택해 완료 상태 캘린더를 만든다."""

    if CalendarEntry.objects.filter(user=user, date=entry_date).exists():
        raise CalendarDateConflictError

    ordered_items = _owned_wardrobe_items(
        user=user,
        wardrobe_item_ids=wardrobe_item_ids,
    )

    entry = CalendarEntry(
        user=user,
        date=entry_date,
        source_type=CalendarSourceType.WARDROBE_SELECTED.value,
        image_s3_key="",
        schedule=schedule,
        tpo=tpo,
        hashtags=hashtags,
        status=CalendarStatus.COMPLETED.value,
    )
    links, destination_keys = _prepare_wardrobe_links(
        entry=entry,
        ordered_items=ordered_items,
    )

    stored_keys: list[str] = []
    try:
        _copy_wardrobe_images(
            ordered_items=ordered_items,
            destination_keys=destination_keys,
            stored_keys=stored_keys,
        )
    except Exception as exc:
        _cleanup_s3_objects(stored_keys)
        raise CalendarStorageError from exc

    entry.image_s3_key = destination_keys[0]
    _save_entry_with_links(entry=entry, links=links, stored_keys=stored_keys)

    return entries_for_user(user=user).get(pk=entry.pk)


def create_from_photo(
    *,
    user: User,
    image: UploadedFile,
    entry_date: date,
    wardrobe_item_ids: Sequence[UUID],
    schedule: str,
    tpo: list[str],
    hashtags: list[str],
) -> CalendarEntry:
    """사용자 사진을 S3에 먼저 저장하고 조회 가능한 캘린더를 생성한다."""

    if CalendarEntry.objects.filter(user=user, date=entry_date).exists():
        raise CalendarDateConflictError

    ordered_items = _owned_wardrobe_items(
        user=user,
        wardrobe_item_ids=wardrobe_item_ids,
    )
    entry = CalendarEntry(
        user=user,
        date=entry_date,
        source_type=CalendarSourceType.PHOTO_UPLOAD.value,
        image_s3_key="",
        schedule=schedule,
        tpo=tpo,
        hashtags=hashtags,
        status=CalendarStatus.REGISTERED.value,
    )
    original_s3_key = storage.original_key(
        user.pk,
        entry.pk,
        image.name,
        image.content_type,
    )
    entry.image_s3_key = original_s3_key
    links, destination_keys = _prepare_wardrobe_links(
        entry=entry,
        ordered_items=ordered_items,
    )

    stored_keys: list[str] = []
    try:
        storage.upload_fileobj(image, original_s3_key, image.content_type)
        stored_keys.append(original_s3_key)
        _copy_wardrobe_images(
            ordered_items=ordered_items,
            destination_keys=destination_keys,
            stored_keys=stored_keys,
        )
    except Exception as exc:
        _cleanup_s3_objects(stored_keys)
        raise CalendarStorageError from exc

    _save_entry_with_links(entry=entry, links=links, stored_keys=stored_keys)

    return entries_for_user(user=user).get(pk=entry.pk)


def mark_queue_enqueue_failed(entry: CalendarEntry) -> None:
    """Redis 적재 실패를 PostgreSQL의 최종 실패 상태로 기록한다."""

    completed_at = timezone.now()
    entry.status = CalendarStatus.FAILED.value
    entry.processing_error_code = CalendarProcessingErrorCode.QUEUE_ENQUEUE_FAILED.value
    entry.processing_error_message = "캘린더 이미지 처리 큐 적재 실패"
    entry.processing_completed_at = completed_at
    entry.save(
        update_fields=[
            "status",
            "processing_error_code",
            "processing_error_message",
            "processing_completed_at",
            "updated_at",
        ]
    )
