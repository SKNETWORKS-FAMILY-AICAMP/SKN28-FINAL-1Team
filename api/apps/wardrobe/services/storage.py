"""S3 저장소 접근 (원본 업로드 · presigned URL 발급).

설계 결정: 이미지 바이너리는 서비스 간 직접 전달하지 않는다.
- 메인 API가 원본을 S3에 선업로드하고 이후에는 키(참조)만 전달
- 버킷은 비공개, 프론트 노출은 presigned GET으로만
키 구조: wardrobe/{user_id}/{job_id}/original.<ext> | item_XX.png
"""
from __future__ import annotations

import os
from functools import lru_cache

import boto3

BUCKET = os.getenv("WARDROBE_S3_BUCKET", "")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")
PRESIGNED_GET_TTL = int(os.getenv("WARDROBE_PRESIGNED_GET_TTL", "3600"))


@lru_cache(maxsize=1)
def _client():
    # 자격증명은 표준 AWS 환경변수(AWS_ACCESS_KEY_ID 등) 또는 IAM 역할로 주입
    return boto3.client("s3", region_name=REGION)


def original_key(user_id: int | str, job_id: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"wardrobe/{user_id}/{job_id}/original{ext}"


def output_prefix(user_id: int | str, job_id: str) -> str:
    """이미지 프로세서가 아이템 크롭을 업로드할 프리픽스."""
    return f"wardrobe/{user_id}/{job_id}/"


def upload_fileobj(fileobj, key: str, content_type: str | None = None) -> None:
    extra = {"ContentType": content_type} if content_type else None
    _client().upload_fileobj(
        fileobj, BUCKET, key, ExtraArgs=extra or {}
    )


def presigned_get(key: str, ttl: int = PRESIGNED_GET_TTL) -> str:
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=ttl
    )
