"""캘린더 전용 Redis consumer.

이 모듈은 캘린더 작업 수신, payload 계약 검증, ack 경계를 담당한다.
실제 이미지 처리와 callback은 다음 단계에서 ``handler``로 연결한다.

성공한 handler만 ack한다. payload 검증, 이미지 처리, callback 중 어느 하나라도
실패하면 작업을 자동 재시도하지 않고 ``calendar:jobs:processing``에 유지한다.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import config
from services import calendar_queue

logger = logging.getLogger(__name__)


class CalendarJobValidationError(ValueError):
    """calendar-job.v1 payload가 계약을 만족하지 않는 경우."""


class ConsumeOutcome(StrEnum):
    """consumer 1회 실행 결과."""

    EMPTY = "empty"
    ACKED = "acked"
    HELD = "held"


@dataclass(frozen=True)
class CalendarSource:
    bucket: str
    key: str


@dataclass(frozen=True)
class CalendarJob:
    schema_version: str
    task_type: str
    calendar_id: str
    user_id: int | str
    source: CalendarSource
    output_prefix: str
    callback_url: str
    created_at: str

    @classmethod
    def from_raw(cls, raw: str) -> CalendarJob:
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise CalendarJobValidationError("payload가 유효한 JSON이 아닙니다.") from exc
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: Any) -> CalendarJob:
        if not isinstance(payload, Mapping):
            raise CalendarJobValidationError("payload 최상위 값은 JSON object여야 합니다.")

        schema_version = _required_string(payload, "schema_version")
        if schema_version != config.CALENDAR_JOB_SCHEMA_VERSION:
            raise CalendarJobValidationError(
                f"지원하지 않는 schema_version입니다: {schema_version}"
            )

        task_type = _required_string(payload, "task_type")
        if task_type != config.CALENDAR_JOB_TASK_TYPE:
            raise CalendarJobValidationError(
                f"캘린더 consumer 대상이 아닌 task_type입니다: {task_type}"
            )

        calendar_id = _required_string(payload, "calendar_id")
        try:
            UUID(calendar_id)
        except ValueError as exc:
            raise CalendarJobValidationError(
                "calendar_id는 UUID 문자열이어야 합니다."
            ) from exc

        user_id = payload.get("user_id")
        if isinstance(user_id, bool) or user_id is None or user_id == "":
            raise CalendarJobValidationError("user_id가 비어 있습니다.")
        if not isinstance(user_id, (int, str)):
            raise CalendarJobValidationError("user_id는 정수 또는 문자열이어야 합니다.")

        source = payload.get("source")
        if not isinstance(source, Mapping):
            raise CalendarJobValidationError("source는 JSON object여야 합니다.")
        bucket = _required_string(source, "bucket", parent="source")
        key = _required_string(source, "key", parent="source")

        output_prefix = _required_string(payload, "output_prefix")
        callback_url = _required_string(payload, "callback_url")
        parsed_url = urlparse(callback_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise CalendarJobValidationError(
                "callback_url은 http 또는 https URL이어야 합니다."
            )

        created_at = _required_string(payload, "created_at")
        try:
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CalendarJobValidationError(
                "created_at은 ISO 8601 날짜/시간이어야 합니다."
            ) from exc

        return cls(
            schema_version=schema_version,
            task_type=task_type,
            calendar_id=calendar_id,
            user_id=user_id,
            source=CalendarSource(bucket=bucket, key=key),
            output_prefix=output_prefix,
            callback_url=callback_url,
            created_at=created_at,
        )


CalendarJobHandler = Callable[[CalendarJob], None]


class CalendarConsumer:
    """캘린더 큐의 작업을 하나씩 handler에 전달하는 consumer."""

    def __init__(self, handler: CalendarJobHandler) -> None:
        self.handler = handler

    def consume_once(self) -> ConsumeOutcome:
        raw = calendar_queue.fetch()
        if raw is None:
            return ConsumeOutcome.EMPTY

        calendar_id = "?"
        try:
            job = CalendarJob.from_raw(raw)
            calendar_id = job.calendar_id
            logger.info(
                "calendar %s 작업 수신 (%s/%s)",
                calendar_id,
                job.source.bucket,
                job.source.key,
            )
            self.handler(job)
            if not calendar_queue.ack(raw):
                raise RuntimeError("processing Queue에서 작업을 ack하지 못했습니다.")
        # 작업별 실패를 격리하고 raw payload를 processing에 보존한다.
        except Exception:
            logger.exception(
                "calendar %s 작업 실패; 자동 재시도 없이 processing Queue에 유지",
                calendar_id,
            )
            return ConsumeOutcome.HELD

        logger.info("calendar %s 작업 완료 및 ack", calendar_id)
        return ConsumeOutcome.ACKED

    def run_forever(self) -> None:
        calendar_queue.validate_configuration()
        logger.info(
            "캘린더 consumer 시작 | 큐: %s -> %s",
            config.CALENDAR_PENDING_KEY,
            config.CALENDAR_PROCESSING_KEY,
        )
        while True:
            self.consume_once()


def _required_string(
    payload: Mapping[str, Any],
    key: str,
    *,
    parent: str = "payload",
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CalendarJobValidationError(f"{parent}.{key}가 비어 있습니다.")
    return value.strip()
