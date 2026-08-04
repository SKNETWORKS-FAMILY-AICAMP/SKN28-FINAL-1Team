"""캘린더 이미지 처리 결과 manifest 생성.

``calendar-result.v1``은 이미지 프로세서가 만든 S3 결과의 기준 문서다.
callback은 이 manifest를 바탕으로 메인 API에 캘린더 상태와 아이템 결과를
전달한다. 임베딩 및 옷장 매칭 정보는 계약에 포함하지 않는다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import config
from calendar_consumer import CalendarJob
from pipeline import ProcessedItem
from services import s3io


def create_manifest(
    *,
    job: CalendarJob,
    pipeline_key: str,
    items: list[ProcessedItem],
    total_sec: float,
    completed_at: datetime | None = None,
) -> dict:
    """이미지 처리 결과를 직렬화 가능한 calendar-result.v1으로 만든다."""

    succeeded = sum(item.ok for item in items)
    failed = len(items) - succeeded
    completed_at = completed_at or datetime.now(UTC)
    if completed_at.utcoffset() is None:
        raise ValueError("completed_at은 timezone-aware datetime이어야 합니다.")

    manifest_s3_key = s3io.manifest_key(job.output_prefix)
    return {
        "schema_version": config.CALENDAR_RESULT_SCHEMA_VERSION,
        "calendar_id": job.calendar_id,
        # 일부 아이템 실패는 아이템별 FAILED로 남기고, 하나라도 추출되면
        # 캘린더 전체 처리는 완료로 본다. PARTIAL 상태는 사용하지 않는다.
        "status": "COMPLETED" if succeeded else "FAILED",
        "source": {
            "bucket": job.source.bucket,
            "key": job.source.key,
        },
        "output": {
            "bucket": job.source.bucket,
            "prefix": job.output_prefix,
            "manifest_s3_key": manifest_s3_key,
        },
        "pipeline": {
            "impl": pipeline_key,
            "version": config.PIPELINE_VERSION,
            "embedding_enabled": False,
        },
        "counts": {
            "detected": len(items),
            "succeeded": succeeded,
            "failed": failed,
        },
        "total_sec": round(total_sec, 3),
        "completed_at": completed_at.isoformat(),
        "items": [_manifest_item(job, item) for item in items],
    }


def _manifest_item(job: CalendarJob, item: ProcessedItem) -> dict:
    tags = dict(item.tags or {})
    missing_required = tags.pop("_missing_required", [])
    image_s3_key = (
        s3io.item_key(job.output_prefix, item.index) if item.ok else ""
    )
    category = (
        tags.get("category_small")
        or tags.get("category_large")
        or item.enum.category_large
    )
    return {
        "processor_item_id": f"{job.calendar_id}:{item.index:03d}",
        "status": "EXTRACTED" if item.ok else "FAILED",
        "image_s3_key": image_s3_key,
        "category": category,
        "tags": tags,
        "bbox": item.enum.bbox,
        "sort_order": item.index,
        "processing_error": item.error or "",
        "meta": {
            "label_ko": item.enum.label_ko,
            "view_angle": item.enum.view_angle,
            "occluded_by": item.enum.occluded_by,
            "missing_required": missing_required,
            "timings_sec": item.timings,
        },
    }
