"""캘린더 생성·조회·수정·삭제 비즈니스 로직."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, QuerySet

from apps.style_calendar.contracts import CalendarSourceType, CalendarStatus
from apps.style_calendar.models import (
    CalendarEntry,
    CalendarItem,
    CalendarWardrobeItem,
)
from apps.style_calendar.services import storage
from apps.wardrobe.models import WardrobeItem

if TYPE_CHECKING:
    from apps.users.models import User

logger = logging.getLogger(__name__)


class WardrobeItemsNotFoundError(Exception):
    """요청 사용자가 소유하지 않은 옷장 아이템이 포함된 경우."""


class CalendarDateConflictError(Exception):
    """사용자의 해당 날짜 캘린더가 이미 존재하는 경우."""


class CalendarStorageError(Exception):
    """캘린더 소유 S3 경로로 이미지 복사 또는 정리에 실패한 경우."""


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


def _cleanup_copied_objects(keys: Sequence[str]) -> None:
    try:
        storage.delete_objects(keys)
    except Exception:
        logger.exception("캘린더 S3 복사 객체 정리 실패: object_count=%s", len(keys))


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

    owned_items = WardrobeItem.objects.filter(
        user=user,
        pk__in=wardrobe_item_ids,
    )
    item_by_id = {item.pk: item for item in owned_items}
    if len(item_by_id) != len(wardrobe_item_ids):
        raise WardrobeItemsNotFoundError

    ordered_items = [item_by_id[item_id] for item_id in wardrobe_item_ids]

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
    links: list[CalendarWardrobeItem] = []
    destination_keys: list[str] = []
    for sort_order, item in enumerate(ordered_items):
        link = CalendarWardrobeItem(
            calendar=entry,
            wardrobe_item=item,
            sort_order=sort_order,
        )
        destination_key = storage.selected_item_key(
            user.pk,
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

    copied_keys: list[str] = []
    try:
        for item, destination_key in zip(ordered_items, destination_keys, strict=True):
            storage.copy_wardrobe_item(item.s3_key, destination_key)
            copied_keys.append(destination_key)
    except Exception as exc:
        _cleanup_copied_objects(copied_keys)
        raise CalendarStorageError from exc

    entry.image_s3_key = destination_keys[0]
    try:
        with transaction.atomic():
            entry.save(force_insert=True)
            CalendarWardrobeItem.objects.bulk_create(links)
    except IntegrityError as exc:
        _cleanup_copied_objects(destination_keys)
        cause = getattr(exc, "__cause__", None)
        diag = getattr(cause, "diag", None)
        if getattr(diag, "constraint_name", None) == "uq_calendar_user_date":
            raise CalendarDateConflictError from exc
        raise
    except Exception:
        _cleanup_copied_objects(destination_keys)
        raise

    return entries_for_user(user=user).get(pk=entry.pk)
