"""캘린더 이미지 처리용 Redis List Queue producer.

옷장 등록 Queue와 key 및 payload 계약을 분리한다. producer는 LPUSH만 수행하며,
consumer가 별도 processing list로 원자적으로 이동하는 로직은 이미지 프로세서가
담당한다.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import TYPE_CHECKING

import redis

from apps.style_calendar.contracts import (
    CALENDAR_JOB_SCHEMA_VERSION,
    CALENDAR_JOB_TASK_TYPE,
)
from apps.style_calendar.services import storage

if TYPE_CHECKING:
    from apps.style_calendar.models import CalendarEntry

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
QUEUE_KEY = os.getenv("CALENDAR_JOB_QUEUE", "calendar:jobs").strip()
PROCESSING_QUEUE_KEY = os.getenv(
    "CALENDAR_PROCESSING_QUEUE",
    "calendar:jobs:processing",
).strip()
WARDROBE_QUEUE_KEY = os.getenv("WARDROBE_JOB_QUEUE", "wardrobe:jobs").strip()
CALLBACK_BASE_URL = os.getenv(
    "CALENDAR_CALLBACK_BASE_URL",
    "",
).strip().rstrip("/")


class CalendarQueueConfigurationError(RuntimeError):
    """Queue 분리 또는 callback 설정이 올바르지 않은 경우."""


def validate_configuration() -> None:
    if not REDIS_URL:
        raise CalendarQueueConfigurationError("REDIS_URL이 설정되지 않았습니다.")
    if not QUEUE_KEY.strip() or not PROCESSING_QUEUE_KEY.strip():
        raise CalendarQueueConfigurationError("캘린더 Queue key가 비어 있습니다.")
    if not WARDROBE_QUEUE_KEY.strip():
        raise CalendarQueueConfigurationError(
            "WARDROBE_JOB_QUEUE가 설정되지 않았습니다."
        )
    if QUEUE_KEY == PROCESSING_QUEUE_KEY:
        raise CalendarQueueConfigurationError(
            "대기 Queue와 processing Queue는 서로 달라야 합니다."
        )
    wardrobe_keys = {
        WARDROBE_QUEUE_KEY,
        f"{WARDROBE_QUEUE_KEY}:processing",
        f"{WARDROBE_QUEUE_KEY}:dead",
        f"{WARDROBE_QUEUE_KEY}:retries",
    }
    if {QUEUE_KEY, PROCESSING_QUEUE_KEY} & wardrobe_keys:
        raise CalendarQueueConfigurationError(
            "캘린더 Queue는 옷장 Queue와 다른 key를 사용해야 합니다."
        )
    if not CALLBACK_BASE_URL:
        raise CalendarQueueConfigurationError(
            "CALENDAR_CALLBACK_BASE_URL이 설정되지 않았습니다."
        )
    if not storage.BUCKET:
        raise CalendarQueueConfigurationError(
            "CALENDAR_S3_BUCKET 또는 WARDROBE_S3_BUCKET이 설정되지 않았습니다."
        )


@lru_cache(maxsize=1)
def _redis():
    kwargs: dict[str, object] = {"decode_responses": True}
    if REDIS_PASSWORD:
        kwargs["password"] = REDIS_PASSWORD
    return redis.Redis.from_url(REDIS_URL, **kwargs)


def callback_url(calendar_id: object) -> str:
    return f"{CALLBACK_BASE_URL}/{calendar_id}/callback/"


def build_payload(entry: CalendarEntry) -> dict[str, object]:
    """이미지 프로세서와 공유하는 versioned 캘린더 작업 payload."""

    return {
        "schema_version": CALENDAR_JOB_SCHEMA_VERSION,
        "task_type": CALENDAR_JOB_TASK_TYPE,
        "calendar_id": str(entry.pk),
        "user_id": entry.user_id,
        "source": {
            "bucket": storage.BUCKET,
            "key": entry.image_s3_key,
        },
        "output_prefix": storage.calendar_prefix(entry.user_id, entry.pk),
        "callback_url": callback_url(entry.pk),
        "created_at": entry.created_at.isoformat(),
    }


def enqueue(entry: CalendarEntry) -> None:
    """캘린더 작업을 LPUSH하며 Redis 오류는 호출자에게 그대로 전달한다."""

    validate_configuration()
    payload = build_payload(entry)
    _redis().lpush(QUEUE_KEY, json.dumps(payload, ensure_ascii=False))
