"""캘린더 사진 이미지 처리 파이프라인.

캘린더 consumer가 검증한 작업을 받아 원본을 S3에서 내려받고, 사진 속 의류를
열거·아이템 이미지 생성·태깅한 뒤 결과 이미지와 ``calendar-result.v1``
manifest를 같은 버킷에 저장한다.

캘린더 결과에는 임베딩을 생성하거나 기록하지 않으며 옷장 아이템 검색·매칭도
수행하지 않는다. DB 반영과 상태 변경은 이후 callback 단계의 책임이다.
"""

from __future__ import annotations

import io
import logging
import mimetypes
import tempfile
import time
from pathlib import Path
from typing import Protocol

from PIL import Image

import config
from calendar_consumer import CalendarJob
from calendar_manifest import create_manifest
from pipeline import ProcessedItem, WardrobePipeline, build_calendar_pipeline
from services import s3io

logger = logging.getLogger(__name__)


class CalendarManifestConflictError(RuntimeError):
    """기존 manifest가 현재 작업의 계약이나 식별자와 다른 경우."""


class ItemPipeline(Protocol):
    @property
    def key(self) -> str: ...

    def process(self, image_bytes: bytes, mime: str) -> list[ProcessedItem]: ...


class CalendarImagePipeline:
    """캘린더 작업 한 건을 S3 결과 manifest까지 처리한다."""

    def __init__(self, pipeline: ItemPipeline | None = None) -> None:
        self.pipeline = pipeline or build_calendar_pipeline()

    def process(self, job: CalendarJob) -> dict:
        """결과 manifest를 반환한다. 동일 작업의 기존 manifest는 재사용한다."""

        manifest_key = s3io.manifest_key(job.output_prefix)
        existing = s3io.get_json(job.source.bucket, manifest_key)
        if existing is not None:
            _validate_existing_manifest(existing, job)
            logger.info(
                "calendar %s: 결과 manifest 존재 → 이미지 처리 생략",
                job.calendar_id,
            )
            return existing

        started_at = time.perf_counter()
        image_bytes, mime = _download_source(job)
        items = self.pipeline.process(image_bytes, mime)

        for item in items:
            if not item.ok:
                continue
            with Image.open(io.BytesIO(item.image_png)) as image:
                image.load()
                s3io.upload_png(
                    job.source.bucket,
                    s3io.item_key(job.output_prefix, item.index),
                    image,
                )

        manifest = create_manifest(
            job=job,
            pipeline_key=self.pipeline.key,
            items=items,
            total_sec=time.perf_counter() - started_at,
        )
        # 아이템 결과 업로드가 모두 끝난 뒤 manifest를 마지막에 기록한다.
        s3io.put_json(job.source.bucket, manifest_key, manifest)
        return manifest


def _download_source(job: CalendarJob) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        filename = Path(job.source.key).name or "source-image"
        local_path = Path(temp_dir) / filename
        s3io.download(job.source.bucket, job.source.key, str(local_path))
        image_bytes = local_path.read_bytes()
    mime = mimetypes.guess_type(filename)[0] or "image/jpeg"
    return image_bytes, mime


def _validate_existing_manifest(manifest: dict, job: CalendarJob) -> None:
    if not isinstance(manifest, dict) or (
        manifest.get("schema_version") != config.CALENDAR_RESULT_SCHEMA_VERSION
        or manifest.get("calendar_id") != job.calendar_id
    ):
        raise CalendarManifestConflictError(
            "기존 manifest가 현재 캘린더 작업과 일치하지 않습니다."
        )


def build_default_calendar_pipeline() -> CalendarImagePipeline:
    """실행 진입점에서 사용할 기본 캘린더 파이프라인 factory."""

    pipeline: WardrobePipeline = build_calendar_pipeline()
    return CalendarImagePipeline(pipeline)
