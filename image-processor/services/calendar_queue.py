"""캘린더 이미지 작업용 Redis List Queue consumer adapter.

옷장 작업 큐와 key 및 실패 정책을 공유하지 않는다. 작업 수신 시
``pending -> processing``으로 원자 이동하고, 주입된 처리기가 S3 처리와
callback까지 모두 끝낸 뒤에만 processing에서 제거한다.

캘린더 작업은 현재 자동 재시도를 하지 않기로 합의했으므로 이 모듈에는
retry/dead/recover 동작을 두지 않는다. 실패한 raw payload는 processing에
남겨 운영자가 원인과 상태를 확인할 수 있게 한다.
"""

from __future__ import annotations

import logging

import config

from services.queue import _redis

logger = logging.getLogger(__name__)


class CalendarQueueConfigurationError(RuntimeError):
    """캘린더 큐가 옷장 큐와 분리되지 않은 경우."""


def validate_configuration() -> None:
    """대기/처리 큐가 서로 다르고 옷장 큐와도 겹치지 않는지 확인한다."""

    calendar_keys = {
        config.CALENDAR_PENDING_KEY,
        config.CALENDAR_PROCESSING_KEY,
    }
    if any(not key.strip() for key in calendar_keys):
        raise CalendarQueueConfigurationError("캘린더 Queue key가 비어 있습니다.")
    if len(calendar_keys) != 2:
        raise CalendarQueueConfigurationError(
            "캘린더 대기 Queue와 processing Queue는 서로 달라야 합니다."
        )
    if not config.PENDING_KEY.strip():
        raise CalendarQueueConfigurationError(
            "WARDROBE_JOB_QUEUE가 설정되지 않았습니다."
        )

    wardrobe_keys = {
        config.PENDING_KEY,
        config.PROCESSING_KEY,
        config.DEAD_KEY,
        config.RETRY_HASH,
    }
    duplicated = calendar_keys & wardrobe_keys
    if duplicated:
        keys = ", ".join(sorted(duplicated))
        raise CalendarQueueConfigurationError(
            f"캘린더 Queue는 옷장 Queue와 다른 key를 사용해야 합니다: {keys}"
        )


def fetch(timeout: int = config.QUEUE_BLOCK_SEC) -> str | None:
    """가장 오래된 캘린더 작업을 processing으로 원자 이동해 가져온다."""

    validate_configuration()
    return _redis().blmove(
        config.CALENDAR_PENDING_KEY,
        config.CALENDAR_PROCESSING_KEY,
        timeout,
        src="RIGHT",
        dest="LEFT",
    )


def ack(raw: str) -> bool:
    """처리가 끝난 작업만 processing에서 제거한다."""

    removed = int(_redis().lrem(config.CALENDAR_PROCESSING_KEY, 1, raw))
    if removed != 1:
        logger.warning("캘린더 processing Queue ack 대상이 없습니다.")
    return removed == 1
