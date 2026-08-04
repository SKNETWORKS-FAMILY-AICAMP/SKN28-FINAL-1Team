"""이미지 프로세서 캘린더 callback의 원자적 DB 반영."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.style_calendar.contracts import (
    CalendarCallbackItemStatus,
    CalendarCallbackStatus,
    CalendarItemInternalStatus,
    CalendarProcessingErrorCode,
    CalendarSourceType,
    CalendarStatus,
)
from apps.style_calendar.models import CalendarEntry, CalendarItem
from apps.style_calendar.services import storage


class CalendarCallbackNotFoundError(RuntimeError):
    """callback 대상 캘린더가 존재하지 않는 경우."""


class CalendarCallbackConflictError(RuntimeError):
    """callback을 적용할 수 없는 캘린더 상태 또는 등록 경로인 경우."""


class CalendarCallbackStorageKeyError(RuntimeError):
    """callback 결과 S3 키가 대상 캘린더 소유 경로가 아닌 경우."""


@dataclass(frozen=True)
class CalendarCallbackResult:
    entry: CalendarEntry
    created_items: int
    duplicate: bool


@transaction.atomic
def apply_callback(
    *,
    calendar_id: UUID,
    data: dict,
) -> CalendarCallbackResult:
    """calendar_id 행을 잠그고 callback을 한 번만 반영한다."""

    entry = (
        CalendarEntry.objects.select_for_update()
        .filter(pk=calendar_id)
        .first()
    )
    if entry is None:
        raise CalendarCallbackNotFoundError
    if entry.source_type != CalendarSourceType.PHOTO_UPLOAD.value:
        raise CalendarCallbackConflictError(
            "사진 업로드 캘린더에만 이미지 처리 callback을 적용할 수 있습니다."
        )

    callback_status = data["status"]
    if callback_status == CalendarCallbackStatus.PROCESSING.value:
        return _apply_processing(entry)

    if entry.callback_applied_at is not None:
        return CalendarCallbackResult(
            entry=entry,
            created_items=entry.items.count(),
            duplicate=True,
        )
    if entry.status in {
        CalendarStatus.COMPLETED.value,
        CalendarStatus.FAILED.value,
    }:
        raise CalendarCallbackConflictError(
            "이미 종료된 캘린더이며 callback으로 완료된 작업이 아닙니다."
        )

    _validate_storage_keys(entry, data)
    item_models = [
        CalendarItem(
            calendar=entry,
            internal_status=(
                CalendarItemInternalStatus.EXTRACTED.value
                if item["status"] == CalendarCallbackItemStatus.EXTRACTED.value
                else CalendarItemInternalStatus.FAILED.value
            ),
            processor_item_id=item["processor_item_id"],
            image_s3_key=item["image_s3_key"],
            category=item["category"],
            tags=item["tags"],
            bbox=item["bbox"],
            sort_order=item["sort_order"],
            processing_error=item["error"],
        )
        for item in data["items"]
    ]
    CalendarItem.objects.bulk_create(item_models)

    completed_at = data["completed_at"]
    entry.status = (
        CalendarStatus.COMPLETED.value
        if callback_status == CalendarCallbackStatus.COMPLETED.value
        else CalendarStatus.FAILED.value
    )
    entry.manifest_s3_key = data["manifest_s3_key"]
    if callback_status == CalendarCallbackStatus.FAILED.value:
        entry.processing_error_code = (
            data["error_code"]
            or CalendarProcessingErrorCode.IMAGE_PROCESSING_FAILED.value
        )
    else:
        entry.processing_error_code = ""
    entry.processing_error_message = data["error_message"]
    entry.processing_started_at = entry.processing_started_at or completed_at
    entry.processing_completed_at = completed_at
    entry.callback_applied_at = timezone.now()
    entry.save(
        update_fields=[
            "status",
            "manifest_s3_key",
            "processing_error_code",
            "processing_error_message",
            "processing_started_at",
            "processing_completed_at",
            "callback_applied_at",
            "updated_at",
        ]
    )
    return CalendarCallbackResult(
        entry=entry,
        created_items=len(item_models),
        duplicate=False,
    )


def _apply_processing(entry: CalendarEntry) -> CalendarCallbackResult:
    if entry.callback_applied_at is not None:
        return CalendarCallbackResult(
            entry=entry,
            created_items=entry.items.count(),
            duplicate=True,
        )
    if entry.status in {
        CalendarStatus.COMPLETED.value,
        CalendarStatus.FAILED.value,
    }:
        raise CalendarCallbackConflictError(
            "이미 종료된 캘린더에는 PROCESSING callback을 적용할 수 없습니다."
        )
    if entry.status == CalendarStatus.PROCESSING.value:
        return CalendarCallbackResult(entry=entry, created_items=0, duplicate=True)

    entry.status = CalendarStatus.PROCESSING.value
    entry.processing_started_at = timezone.now()
    entry.processing_error_code = ""
    entry.processing_error_message = ""
    entry.save(
        update_fields=[
            "status",
            "processing_started_at",
            "processing_error_code",
            "processing_error_message",
            "updated_at",
        ]
    )
    return CalendarCallbackResult(entry=entry, created_items=0, duplicate=False)


def _validate_storage_keys(entry: CalendarEntry, data: dict) -> None:
    manifest_s3_key = data["manifest_s3_key"]
    if manifest_s3_key and manifest_s3_key != storage.manifest_key(
        entry.user_id,
        entry.pk,
    ):
        raise CalendarCallbackStorageKeyError(
            "manifest_s3_key가 대상 캘린더 경로와 일치하지 않습니다."
        )

    for item in data["items"]:
        image_s3_key = item["image_s3_key"]
        if image_s3_key and not storage.owns_key(
            image_s3_key,
            user_id=entry.user_id,
            calendar_id=entry.pk,
        ):
            raise CalendarCallbackStorageKeyError(
                "아이템 image_s3_key가 대상 캘린더 소유 경로가 아닙니다."
            )
