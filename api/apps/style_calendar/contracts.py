"""캘린더 API와 이미지 프로세서가 공유하는 계약 상수."""

from enum import StrEnum


class CalendarStatus(StrEnum):
    """캘린더 이미지 처리 상태."""

    REGISTERED = "REGISTERED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CalendarSourceType(StrEnum):
    """캘린더 등록 경로."""

    PHOTO_UPLOAD = "PHOTO_UPLOAD"
    WARDROBE_SELECTED = "WARDROBE_SELECTED"


class CalendarItemInternalStatus(StrEnum):
    """사용자 화면에 노출하지 않는 캘린더 아이템 내부 상태."""

    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


CALENDAR_JOB_SCHEMA_VERSION = "calendar-job.v1"
CALENDAR_JOB_TASK_TYPE = "calendar_image_extraction"
CALENDAR_CALLBACK_SCHEMA_VERSION = "calendar-callback.v1"
CALENDAR_RESULT_SCHEMA_VERSION = "calendar-result.v1"
