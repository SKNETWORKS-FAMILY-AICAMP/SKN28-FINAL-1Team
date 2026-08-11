"""렌더 작업 한 건의 캐시 조회·이미지 생성·S3 저장 실행 계층."""

from __future__ import annotations

from django.conf import settings

from apps.recommend.models import OutfitRenderJob
from apps.recommend.services import render_jobs, storage
from apps.recommend.services.outfit_render import OutfitRenderService, RenderInputError
from apps.recommend.services.render_cache import RenderCacheEntry, RenderResultCache


def _entry_values(entry: RenderCacheEntry) -> dict:
    return {
        "output_s3_bucket": entry.output_s3_bucket,
        "output_s3_key": entry.output_s3_key,
        "output_media_type": entry.output_media_type,
        "output_bytes": entry.output_bytes,
        "provider": entry.provider,
        "model": entry.model,
        "prompt_version": entry.prompt_version,
        "reference_count": entry.reference_count,
        "usage": entry.usage,
    }


def _job_entry(job: OutfitRenderJob) -> RenderCacheEntry:
    return RenderCacheEntry(
        render_fingerprint=job.render_fingerprint,
        output_s3_bucket=job.output_s3_bucket,
        output_s3_key=job.output_s3_key,
        output_media_type=job.output_media_type,
        output_bytes=job.output_bytes or 0,
        provider=job.provider,
        model=job.model,
        prompt_version=job.prompt_version,
        reference_count=job.reference_count,
        usage=job.usage or {},
    )


def _usable(entry: RenderCacheEntry) -> bool:
    return bool(
        entry.output_s3_bucket
        and entry.output_s3_key
        and entry.output_media_type
        and storage.exists_for(entry.output_s3_bucket, entry.output_s3_key)
    )


def execute(
    job: OutfitRenderJob,
    *,
    renderer: OutfitRenderService | None = None,
    cache: RenderResultCache | None = None,
) -> OutfitRenderJob:
    """PROCESSING 작업을 캐시 재사용 또는 실제 생성으로 완료한다."""
    if job.status != OutfitRenderJob.Status.PROCESSING:
        raise RenderInputError("PROCESSING 상태의 이미지 작업만 실행할 수 있습니다.")
    if job.composition.composition_fingerprint.strip().lower() != (
        job.composition_fingerprint
    ):
        raise RenderInputError("작업 접수 후 코디 구성이 변경되었습니다.")

    result_cache = cache or RenderResultCache()
    cached = result_cache.get(job.render_fingerprint)
    if cached is not None and _usable(cached):
        return render_jobs.mark_succeeded(
            job.pk,
            values=_entry_values(cached),
            cache_hit=True,
        )

    durable = (
        OutfitRenderJob.objects.filter(
            render_fingerprint=job.render_fingerprint,
            status=OutfitRenderJob.Status.SUCCEEDED,
        )
        .exclude(pk=job.pk)
        .order_by("-finished_at")
        .first()
    )
    if durable is not None:
        entry = _job_entry(durable)
        if _usable(entry):
            result_cache.set(entry)
            return render_jobs.mark_succeeded(
                job.pk,
                values=_entry_values(entry),
                cache_hit=True,
            )

    bucket = settings.OUTFIT_RENDER_RESULT_BUCKET
    if not bucket:
        raise RenderInputError("OUTFIT_RENDER_RESULT_BUCKET이 설정되지 않았습니다.")
    rendered = (renderer or OutfitRenderService()).render(job.composition)
    key = render_jobs.output_key(job.render_fingerprint)
    storage.put_bytes_for(bucket, key, rendered.content, rendered.media_type)
    entry = RenderCacheEntry(
        render_fingerprint=job.render_fingerprint,
        output_s3_bucket=bucket,
        output_s3_key=key,
        output_media_type=rendered.media_type,
        output_bytes=len(rendered.content),
        provider=rendered.provider,
        model=rendered.model,
        prompt_version=rendered.prompt_version,
        reference_count=rendered.reference_count,
        usage=rendered.usage,
    )
    completed = render_jobs.mark_succeeded(
        job.pk,
        values=_entry_values(entry),
        cache_hit=False,
    )
    result_cache.set(entry)
    return completed
