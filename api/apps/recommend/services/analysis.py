"""코디 평가 유스케이스 — 컨텍스트 조립 → 사진 보관 → LLM 호출 → 기록.

view는 HTTP 변환만 하고 흐름은 여기서 관리한다 (fat model / thin view).

기록 정책
- 요청 접수 시점에 PENDING 행을 먼저 만든다. 그래야 LLM이 죽은 요청도 남는다.
- **기록 실패가 평가 응답을 깨뜨리지 않는다**: DB나 S3 문제로 저장이 실패해도
  사용자는 평가를 받아야 한다. 저장 실패는 로그로만 남기고 `analysis_id`를
  NULL로 응답한다. 평가 자체(LLM)가 실패한 경우에만 503을 낸다.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from apps.weather.services import resolve_coordinates

from ..models import OutfitAnalysis
from . import gemini, storage
from .outfit_context import build_analysis_context

logger = logging.getLogger(__name__)


def _create_pending(
    user,
    image: UploadedFile,
    context: dict[str, Any],
    *,
    lat: float | None,
    lon: float | None,
) -> OutfitAnalysis | None:
    resolved_lat, resolved_lon = resolve_coordinates(lat, lon)
    analysis = OutfitAnalysis(
        user=user if (user and user.is_authenticated) else None,
        status=OutfitAnalysis.Status.PENDING,
        image_content_type=image.content_type or "",
        image_bytes=image.size,
        requested_lat=lat,
        requested_lon=lon,
        resolved_lat=resolved_lat,
        resolved_lon=resolved_lon,
        weather=context.get("weather") or {},
        body=context.get("body"),
        pursuit=context.get("pursuit"),
        personalized=bool(context.get("personalized")),
        llm_model=settings.GEMINI_MODEL,
    )
    try:
        analysis.save()
    except Exception:  # noqa: BLE001 — 기록 실패로 평가를 막지 않는다
        logger.exception("코디 평가 기록 생성 실패")
        return None
    return analysis


def _update(analysis: OutfitAnalysis | None, **fields: Any) -> None:
    if analysis is None:
        return
    for name, value in fields.items():
        setattr(analysis, name, value)
    try:
        analysis.save(update_fields=list(fields))
    except Exception:  # noqa: BLE001
        logger.exception("코디 평가 기록 갱신 실패: analysis=%s", analysis.pk)


def _store_image(analysis: OutfitAnalysis, image: UploadedFile) -> None:
    """원본 사진을 S3에 올리고 키를 기록한다 (best-effort).

    버킷 미설정(로컬)이나 업로드 실패는 평가를 막지 않는다 — 사진이 없어도
    평가 자체는 이미 수행 가능하고, 사진은 사후 재현용 부가 데이터다.
    """
    if not storage.is_configured():
        return
    key = storage.original_key(analysis.user_id, str(analysis.pk), image.name)
    try:
        image.seek(0)
        storage.upload_fileobj(image, key, image.content_type)
    except Exception:  # noqa: BLE001
        logger.exception("코디 사진 S3 업로드 실패: analysis=%s", analysis.pk)
        return
    _update(analysis, image_s3_key=key)


def analyze_outfit(
    user,
    image: UploadedFile,
    *,
    lat: float | None,
    lon: float | None,
) -> tuple[OutfitAnalysis | None, dict[str, Any], dict[str, Any]]:
    """코디 사진을 평가하고 요청·응답 전체를 기록한다.

    Returns: (기록 행 또는 None, 평가 결과, 질의 컨텍스트)
    Raises: gemini.GeminiConfigurationError, gemini.GeminiServiceError
    """
    context = build_analysis_context(user, lat=lat, lon=lon)
    analysis = _create_pending(user, image, context, lat=lat, lon=lon)
    if analysis is not None:
        _store_image(analysis, image)

    request_payload = gemini.build_request_payload(
        context,
        mime_type=image.content_type or "",
        image_bytes=image.size,
    )

    try:
        result = gemini.evaluate_outfit(image, context=context)
    except gemini.GeminiConfigurationError as exc:
        _update(
            analysis,
            status=OutfitAnalysis.Status.FAILED,
            request_payload=request_payload,
            error_message=str(exc) or exc.__class__.__name__,
            finished_at=timezone.now(),
        )
        raise
    except gemini.GeminiServiceError as exc:
        _update(
            analysis,
            status=OutfitAnalysis.Status.FAILED,
            request_payload=request_payload,
            response_payload=exc.response_payload or {},
            error_message=str(exc) or exc.__class__.__name__,
            finished_at=timezone.now(),
        )
        raise

    _update(
        analysis,
        status=OutfitAnalysis.Status.SUCCEEDED,
        llm_model=result.model,
        request_payload=request_payload,
        response_payload=result.response_payload,
        evaluation=result.evaluation,
        latency_ms=result.latency_ms,
        finished_at=timezone.now(),
    )
    return analysis, result.evaluation, context
