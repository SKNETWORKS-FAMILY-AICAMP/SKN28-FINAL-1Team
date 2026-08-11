"""오늘의 룩 추천과 누락 렌더 보정 큐를 처리한다."""

from __future__ import annotations

import json
import logging
import signal
import time
from datetime import timedelta
from typing import Any

import redis
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.recommend.models import DailyLook
from apps.recommend.services import daily_look, daily_look_queue

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "오늘의 룩 reliable queue를 소비해 골든셋 추천과 공통 이미지 렌더를 수행한다."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--once", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        self.running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        recovered = daily_look_queue.recover_processing()
        if recovered:
            logger.info("오늘의 룩 processing 복구: %s건", recovered)
        self._recover_orphaned_pending()
        logger.info("오늘의 룩 워커 시작")

        last_orphan_sweep = time.monotonic()
        while self.running:
            if (
                time.monotonic() - last_orphan_sweep
                >= settings.DAILY_LOOK_QUEUE_ORPHAN_SWEEP_SECONDS
            ):
                last_orphan_sweep = time.monotonic()
                self._recover_orphaned_pending()
            try:
                raw = daily_look_queue.fetch()
            except redis.RedisError:
                logger.exception("오늘의 룩 큐 읽기 실패")
                if options["once"]:
                    break
                time.sleep(1)
                continue
            if raw is None:
                if options["once"]:
                    break
                continue
            self._handle(raw)
            if options["once"]:
                break
        logger.info("오늘의 룩 워커 종료")

    def _stop(self, *_args: Any) -> None:
        self.running = False

    @staticmethod
    def _recover_orphaned_pending() -> int:
        cutoff = timezone.now() - timedelta(
            seconds=settings.DAILY_LOOK_QUEUE_ORPHAN_AGE_SECONDS
        )
        looks = list(
            DailyLook.objects.filter(
                status=DailyLook.Status.QUEUED,
                enqueued_at__isnull=True,
                created_at__lte=cutoff,
            ).order_by("created_at")[: settings.DAILY_LOOK_QUEUE_ORPHAN_SWEEP_LIMIT]
        )
        recovered = 0
        for look in looks:
            try:
                daily_look_queue.enqueue(look.pk)
            except redis.RedisError:
                logger.warning(
                    "미적재 오늘의 룩 작업 복구 중 Redis 연결 실패",
                    exc_info=True,
                )
                break
            now = timezone.now()
            updated = DailyLook.objects.filter(
                pk=look.pk,
                status=DailyLook.Status.QUEUED,
                enqueued_at__isnull=True,
            ).update(enqueued_at=now, updated_at=now)
            recovered += int(bool(updated))
        if recovered:
            logger.info(
                "미적재 오늘의 룩 작업 복구 완료: %s건",
                recovered,
                extra={"event": "daily_look_orphan_recovered"},
            )
        return recovered

    @staticmethod
    def _payload(raw: str) -> tuple[str, str] | None:
        try:
            payload = json.loads(raw)
            return str(payload["look_id"]), str(payload.get("job") or "recommend")
        except (ValueError, KeyError, TypeError):
            return None

    def _handle(self, raw: str) -> None:
        parsed = self._payload(raw)
        if parsed is None:
            daily_look_queue.ack(raw, "?")
            return
        look_id, job = parsed
        if job == "render":
            self._run_render(raw, look_id)
            return

        look = daily_look.claim(look_id)
        if look is None:
            daily_look_queue.ack(raw, look_id)
            return
        try:
            daily_look.run(look)
        except Exception as exc:  # noqa: BLE001 - 작업 단위 상태·큐 전이를 보장한다.
            self._failure(raw, look, exc)
            return
        look.refresh_from_db()
        logger.info(
            "오늘의 룩 처리 완료: look=%s status=%s",
            look_id,
            look.status,
            extra={"look_id": look_id, "status": look.status},
        )
        daily_look_queue.ack(raw, look_id)

    def _run_render(self, raw: str, look_id: str) -> None:
        try:
            daily_look.run_render_only(look_id)
        except Exception as exc:  # noqa: BLE001 - 제공자별 예외를 작업 재시도로 통합한다.
            self._retry_render(raw, look_id, exc)
            return
        daily_look_queue.ack(raw, look_id)

    @staticmethod
    def _failure(raw: str, look: DailyLook, exc: Exception) -> None:
        try:
            dead = daily_look_queue.retry_or_dead(raw, str(look.pk), str(exc))
        except redis.RedisError:
            dead = True
            logger.exception("오늘의 룩 실패 큐 전환 실패")
        if dead:
            daily_look.mark_failed(look, f"{type(exc).__name__}: {exc}")
        else:
            look.status = DailyLook.Status.QUEUED
            look.enqueued_at = timezone.now()
            look.save(update_fields=["status", "enqueued_at", "updated_at"])

    @staticmethod
    def _retry_render(raw: str, look_id: str, exc: Exception) -> None:
        try:
            dead = daily_look_queue.retry_or_dead(raw, look_id, str(exc))
        except redis.RedisError:
            dead = True
        if dead:
            logger.error(
                "오늘의 룩 렌더 보정 최종 실패: look=%s error=%s", look_id, exc
            )
