"""룩북 API와 이미지 프로세서가 공유하는 계약 상수.

캘린더(style_calendar)와 같은 이름·같은 값을 쓴다. 두 도메인이 같은 옷장
업로드 파이프라인을 태우기 때문에 상태 문자열이 갈리면 프론트가 화면마다
다른 분기를 들고 있어야 한다. 그렇다고 캘린더의 것을 import하지는 않는다 —
룩북은 날짜가 없어도 되는 별도 도메인이라, 한쪽 상태가 늘어날 때 다른 쪽이
따라 늘어나야 하는 결합을 만들지 않는다.
"""

from enum import StrEnum


class LookbookStatus(StrEnum):
    """룩북 이미지 처리 상태."""

    REGISTERED = "REGISTERED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LookbookSourceType(StrEnum):
    """룩북 등록 경로."""

    PHOTO_UPLOAD = "PHOTO_UPLOAD"
    WARDROBE_SELECTED = "WARDROBE_SELECTED"


class LookbookLinkType(StrEnum):
    """룩북에 옷장 아이템이 붙은 경로.

    SELECTED  — 사용자가 '입은 옷'으로 직접 고른 아이템
    EXTRACTED — 룩 사진에서 이미지 프로세서가 새로 뽑아 등록한 아이템
    """

    SELECTED = "SELECTED"
    EXTRACTED = "EXTRACTED"


class LookbookProcessingErrorCode(StrEnum):
    """룩 사진 처리의 표준 전체 실패 코드."""

    QUEUE_ENQUEUE_FAILED = "QUEUE_ENQUEUE_FAILED"
    NO_ITEM_EXTRACTED = "NO_ITEM_EXTRACTED"
    IMAGE_PROCESSING_FAILED = "IMAGE_PROCESSING_FAILED"
