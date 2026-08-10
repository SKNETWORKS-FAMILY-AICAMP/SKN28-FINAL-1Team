"""S3 저장소 접근 (원본 업로드 · presigned URL 발급).

설계 결정: 이미지 바이너리는 서비스 간 직접 전달하지 않는다.
- 메인 API가 원본을 S3에 선업로드하고 이후에는 키(참조)만 전달
- 버킷은 비공개, 프론트 노출은 presigned GET으로만
키 구조: wardrobe/{user_id}/{job_id}/original.<ext> | item_XX.png
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from functools import lru_cache

import boto3

BUCKET = os.getenv("WARDROBE_S3_BUCKET", "")
REGION = os.getenv("AWS_REGION", "ap-northeast-2")
PRESIGNED_GET_TTL = int(os.getenv("WARDROBE_PRESIGNED_GET_TTL", "3600"))


from django.conf import settings

IS_LOCAL = not BUCKET or settings.DEBUG or hasattr(settings, 'AUTO_LOGIN_ENABLED')
LOCAL_MEDIA_DIR = os.path.join(settings.BASE_DIR, "media")

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
    if IS_LOCAL:
        local_path = os.path.join(LOCAL_MEDIA_DIR, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        # Ensure pointer is at start
        fileobj.seek(0)
        with open(local_path, "wb") as f:
            f.write(fileobj.read())
        return

    extra = {"ContentType": content_type} if content_type else None
    _client().upload_fileobj(
        fileobj, BUCKET, key, ExtraArgs=extra or {}
    )


def presigned_get(key: str, ttl: int = PRESIGNED_GET_TTL) -> str:
    if IS_LOCAL:
        return f"http://localhost:8000/media/{key}"

    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=ttl
    )


def delete_objects(keys: Iterable[str]) -> None:
    """DB 저장 실패 시 명시된 옷장 S3 객체만 정리한다."""
    if IS_LOCAL:
        for key in keys:
            if not key:
                continue
            local_path = os.path.join(LOCAL_MEDIA_DIR, key)
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass
        return

    unique_keys = list(dict.fromkeys(key for key in keys if key))
    for offset in range(0, len(unique_keys), 1000):
        batch = unique_keys[offset : offset + 1000]
        _client().delete_objects(
            Bucket=BUCKET,
            Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
        )
