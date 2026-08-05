"""코디 평가 원본 사진 S3 저장.

설계 결정은 wardrobe/services/storage.py와 동일하다 — 이미지 바이너리는 DB에
넣지 않고 S3에 두고 키(참조)만 저장한다. 버킷은 옷장과 분리할 수 있게
`OUTFIT_S3_BUCKET`을 먼저 보고, 없으면 옷장 버킷을 재사용한다
(팀 로컬 환경에서 env를 추가하지 않아도 동작하도록).

키 구조: outfits/{user_id|anonymous}/{analysis_id}/original.<ext>
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3
from botocore.config import Config


def bucket() -> str:
    """버킷명은 호출 시점에 읽는다 (테스트에서 환경변수 오버라이드 가능)."""
    return os.getenv("OUTFIT_S3_BUCKET", "") or os.getenv("WARDROBE_S3_BUCKET", "")


def is_configured() -> bool:
    """버킷이 지정되지 않은 환경(로컬 등)에서는 업로드를 건너뛴다."""
    return bool(bucket())


REGION = os.getenv("AWS_REGION", "ap-northeast-2")
PRESIGNED_GET_TTL = int(os.getenv("OUTFIT_PRESIGNED_GET_TTL", "3600"))
S3_CONNECT_TIMEOUT = int(os.getenv("OUTFIT_S3_CONNECT_TIMEOUT", "5"))
S3_READ_TIMEOUT = int(os.getenv("OUTFIT_S3_READ_TIMEOUT", "15"))


@lru_cache(maxsize=1)
def _client():
    # 자격증명은 표준 AWS 환경변수(AWS_ACCESS_KEY_ID 등) 또는 IAM 역할로 주입.
    # 업로드는 사용자 요청을 붙잡고 있는 동기 구간이라, 기본값(60s x 5회 재시도)으로
    # 두면 S3가 느릴 때 요청이 몇 분씩 매달린다. 짧게 끊고 포기하는 편이 낫다
    # — 사진 업로드는 실패해도 평가를 막지 않는 best-effort 단계다.
    return boto3.client(
        "s3",
        region_name=REGION,
        config=Config(
            connect_timeout=S3_CONNECT_TIMEOUT,
            read_timeout=S3_READ_TIMEOUT,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def original_key(user_id: int | str | None, analysis_id: str, filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower() or ".jpg"
    owner = user_id if user_id is not None else "anonymous"
    return f"outfits/{owner}/{analysis_id}/original{ext}"


def upload_fileobj(fileobj, key: str, content_type: str | None = None) -> None:
    extra = {"ContentType": content_type} if content_type else None
    _client().upload_fileobj(fileobj, bucket(), key, ExtraArgs=extra or {})


def download(key: str) -> bytes:
    """워커가 평가 대상 사진을 읽어온다. 실패 시 botocore 예외를 그대로 올린다."""
    return _client().get_object(Bucket=bucket(), Key=key)["Body"].read()


def presigned_get(key: str, ttl: int = PRESIGNED_GET_TTL) -> str:
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket(), "Key": key}, ExpiresIn=ttl
    )
