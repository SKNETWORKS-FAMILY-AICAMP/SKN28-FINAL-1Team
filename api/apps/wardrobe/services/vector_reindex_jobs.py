"""기존 옷장 크롭 이미지의 임베딩 재생성 작업을 Redis에 적재한다."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from functools import lru_cache

import redis

from apps.wardrobe.models import WardrobeItem
from apps.wardrobe.services import storage
from apps.wardrobe.services.vectors import EMBEDDING_VERSION

QUEUE_KEY = os.getenv("WARDROBE_REINDEX_QUEUE", "wardrobe:reindex")
CALLBACK_URL = os.getenv("WARDROBE_REINDEX_CALLBACK_URL", "").strip()


class ReindexQueueConfigurationError(RuntimeError):
    """재인덱싱 작업에 필요한 외부 주소 설정이 빠진 경우."""


@lru_cache(maxsize=1)
def _redis() -> redis.Redis:
    kwargs = {"decode_responses": True}
    password = os.getenv("REDIS_PASSWORD", "")
    if password:
        kwargs["password"] = password
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        **kwargs,
    )


def _tags(item: WardrobeItem) -> dict[str, object]:
    return {
        "item_name": item.item_name,
        "category_large": item.category_large,
        "category_small": item.category_small,
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
    }


def build_payload(item: WardrobeItem) -> dict[str, object]:
    if not storage.BUCKET:
        raise ReindexQueueConfigurationError("WARDROBE_S3_BUCKET이 필요합니다.")
    if not CALLBACK_URL:
        raise ReindexQueueConfigurationError(
            "WARDROBE_REINDEX_CALLBACK_URL이 필요합니다."
        )
    return {
        "schema_version": "1.0",
        "item_id": str(item.pk),
        "user_id": item.user_id,
        "source": {"bucket": storage.BUCKET, "key": item.s3_key},
        "source_updated_at": item.updated_at.isoformat(),
        "embedding_version": EMBEDDING_VERSION,
        "tags": _tags(item),
        "callback_url": CALLBACK_URL,
    }


def enqueue_many(items: Iterable[WardrobeItem]) -> int:
    payloads = [build_payload(item) for item in items]
    if not payloads:
        return 0

    pipeline = _redis().pipeline(transaction=True)
    for payload in payloads:
        pipeline.lpush(QUEUE_KEY, json.dumps(payload, ensure_ascii=False))
    pipeline.execute()
    return len(payloads)
