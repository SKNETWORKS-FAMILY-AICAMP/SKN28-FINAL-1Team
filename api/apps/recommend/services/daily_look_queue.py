"""오늘의 룩 생성·이미지 보정용 Redis reliable queue."""

from __future__ import annotations

import json
from functools import lru_cache

import redis
from django.conf import settings


@lru_cache(maxsize=1)
def get_client() -> redis.Redis:
    kwargs: dict = {
        "decode_responses": True,
        "socket_connect_timeout": settings.DAILY_LOOK_QUEUE_CONNECT_TIMEOUT_SECONDS,
        "socket_timeout": settings.DAILY_LOOK_QUEUE_BLOCK_SECONDS + 10,
    }
    if settings.REDIS_PASSWORD:
        kwargs["password"] = settings.REDIS_PASSWORD
    return redis.Redis.from_url(settings.REDIS_URL, **kwargs)


def enqueue(look_id, *, job: str = "recommend") -> None:
    payload = json.dumps(
        {"look_id": str(look_id), "job": job},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    get_client().lpush(settings.DAILY_LOOK_QUEUE_PENDING_KEY, payload)


def fetch(timeout: int | None = None) -> str | None:
    block = (
        settings.DAILY_LOOK_QUEUE_BLOCK_SECONDS if timeout is None else max(timeout, 0)
    )
    return get_client().blmove(
        settings.DAILY_LOOK_QUEUE_PENDING_KEY,
        settings.DAILY_LOOK_QUEUE_PROCESSING_KEY,
        block,
        src="RIGHT",
        dest="LEFT",
    )


def ack(raw: str, look_id: str) -> None:
    client = get_client()
    client.lrem(settings.DAILY_LOOK_QUEUE_PROCESSING_KEY, 1, raw)
    client.hdel(settings.DAILY_LOOK_QUEUE_RETRY_KEY, look_id)


def retry_or_dead(raw: str, look_id: str, error: str) -> bool:
    client = get_client()
    retries = client.hincrby(settings.DAILY_LOOK_QUEUE_RETRY_KEY, look_id, 1)
    client.lrem(settings.DAILY_LOOK_QUEUE_PROCESSING_KEY, 1, raw)
    if retries >= settings.DAILY_LOOK_QUEUE_MAX_RETRIES:
        client.lpush(
            settings.DAILY_LOOK_QUEUE_DEAD_KEY,
            json.dumps(
                {"payload": raw, "error": error[:500], "retries": retries},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        client.hdel(settings.DAILY_LOOK_QUEUE_RETRY_KEY, look_id)
        return True
    client.lpush(settings.DAILY_LOOK_QUEUE_PENDING_KEY, raw)
    return False


def recover_processing() -> int:
    client = get_client()
    moved = 0
    while client.lmove(
        settings.DAILY_LOOK_QUEUE_PROCESSING_KEY,
        settings.DAILY_LOOK_QUEUE_PENDING_KEY,
        src="RIGHT",
        dest="RIGHT",
    ):
        moved += 1
    return moved
