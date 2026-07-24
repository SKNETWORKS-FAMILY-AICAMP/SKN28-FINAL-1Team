"""이미지 처리 job 큐잉.

설계 결정: 메인 API → 이미지 프로세서는 직접 HTTP가 아니라 큐를 경유한다.
GPU 서버가 내려가 있어도 job이 유실되지 않고, 서버리스 GPU 전환도 쉬워진다.

큐 구현은 Redis 리스트(LPUSH → 프로세서가 BRPOP)로 시작한다.
이미지 프로세서는 아래 페이로드를 소비한다고 가정한다:
{
  "job_id": "...", "user_id": 1,
  "source": {"bucket": "...", "key": "wardrobe/1/<job>/original.jpg"},
  "output_prefix": "wardrobe/1/<job>/",
  "callback_url": "https://api.../api/v1/internal/wardrobe/callback/"
}
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

import redis

from . import storage

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = os.getenv("WARDROBE_JOB_QUEUE", "wardrobe:jobs")
CALLBACK_URL = os.getenv("WARDROBE_CALLBACK_URL", "")


@lru_cache(maxsize=1)
def _redis():
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def enqueue(job) -> None:
    """job을 처리 큐에 적재한다. 실패 시 redis.RedisError를 그대로 올린다."""
    payload = {
        "job_id": str(job.id),
        "user_id": job.user_id,
        "source": {"bucket": storage.BUCKET, "key": job.source_s3_key},
        "output_prefix": storage.output_prefix(job.user_id, job.id),
        "callback_url": CALLBACK_URL,
    }
    _redis().lpush(QUEUE_KEY, json.dumps(payload, ensure_ascii=False))
