"""골든셋 오늘의 룩 생성과 공통 코디 이미지 렌더 연계."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.recommend.models import DailyLook
from apps.recommend.services import daily_look_queue, gemini, render_artifacts
from apps.recommend.services.body_profile import BodyProfile, build_profile
from apps.recommend.services.outfit_context import build_analysis_context
from apps.recommend.services.outfit_render import (
    OutfitRenderRequest,
    RenderItemReference,
    RenderSource,
)
from apps.recommend.services.retriever import (
    RetrievalRequest,
    normalize_presentation_groups,
    retrieve_outfits,
)
from apps.recommend.services.style_rules import load_body_rules

logger = logging.getLogger(__name__)
CANDIDATE_LIMIT = 5


def _profile_snapshot(profile: BodyProfile) -> dict[str, Any]:
    return {
        "silhouette": profile.silhouette,
        "bmi_band": profile.bmi_band,
        "bmi": profile.bmi,
        "ratios": dict(profile.ratios),
        "known": list(profile.known),
        "missing": list(profile.missing),
        "describe": profile.describe(),
    }


def ensure_today_look(user, *, lat: float | None = None, lon: float | None = None):
    """서비스 타임존 기준 하루 한 행을 만들고 reliable queue에 넣는다."""
    look_date = timezone.localdate()
    if existing := DailyLook.objects.filter(user=user, look_date=look_date).first():
        return existing, False

    context = build_analysis_context(user, lat=lat, lon=lon)
    body = context.get("body")
    try:
        with transaction.atomic():
            look = DailyLook.objects.create(
                user=user,
                look_date=look_date,
                weather=context.get("weather") or {},
                body=body,
                body_profile=_profile_snapshot(build_profile(body)),
                pursuit=context.get("pursuit"),
            )
    except IntegrityError:
        return DailyLook.objects.get(user=user, look_date=look_date), False

    try:
        daily_look_queue.enqueue(look.pk)
    except Exception:  # Redis 장애가 로그인·조회 자체를 막지 않는다.
        logger.exception("오늘의 룩 큐 적재 실패: look=%s", look.pk)
    return look, True


def claim(look_id: str) -> DailyLook | None:
    with transaction.atomic():
        look = DailyLook.objects.select_for_update().filter(pk=look_id).first()
        if look is None or look.status in DailyLook.TERMINAL_STATUSES:
            return None
        look.status = DailyLook.Status.PROCESSING
        look.save(update_fields=["status", "updated_at"])
        return look


def _presentation(body: dict | None) -> tuple[str, tuple[str, ...]]:
    raw = str((body or {}).get("gender") or "").strip().casefold()
    primary = {
        "male": "man",
        "man": "man",
        "남성": "man",
        "female": "woman",
        "woman": "woman",
        "여성": "woman",
        "unisex": "unisex",
        "유니섹스": "unisex",
    }.get(raw, "")
    return primary, normalize_presentation_groups((raw,))


def run(look: DailyLook) -> None:
    """현재 골든셋 계약으로 1위 코디를 정하고 공통 렌더 결과를 붙인다."""
    snapshot = look.retrieval_context()
    saved = snapshot.get("body_profile") or {}
    profile = BodyProfile(
        silhouette=saved.get("silhouette", "unknown"),
        bmi_band=saved.get("bmi_band", "unknown"),
        bmi=saved.get("bmi"),
        ratios=dict(saved.get("ratios") or {}),
        known=tuple(saved.get("known") or ()),
        missing=tuple(saved.get("missing") or ()),
    )
    presentation, presentation_groups = _presentation(snapshot.get("body"))
    rules = load_body_rules()
    if not presentation_groups:
        look.status = DailyLook.Status.EMPTY
        look.rules_version = rules.schema_version
        look.error = "성별 정보가 없어 오늘의 룩 후보를 검색하지 않았습니다."
        look.save(update_fields=["status", "rules_version", "error", "updated_at"])
        return

    candidates = retrieve_outfits(
        RetrievalRequest(
            body=profile,
            pursuit=snapshot.get("pursuit"),
            weather=snapshot.get("weather"),
            presentation_groups=presentation_groups,
            dataset_version=settings.CHAT_GOLDENSET_DATASET_VERSION,
            dataset_statuses=settings.CHAT_GOLDENSET_DATASET_STATUSES,
            limit=CANDIDATE_LIMIT,
        )
    )
    look.candidates = [_candidate_snapshot(candidate) for candidate in candidates]
    look.rules_version = rules.schema_version
    if not candidates:
        look.status = DailyLook.Status.EMPTY
        look.error = "조건에 맞는 골든 코디 후보가 없습니다."
        look.save(
            update_fields=[
                "candidates",
                "rules_version",
                "status",
                "error",
                "updated_at",
            ]
        )
        return

    chosen = candidates[0]
    look.result = _build_result(chosen, snapshot)
    look.status = DailyLook.Status.SUCCEEDED
    look.error = ""
    look.save(
        update_fields=[
            "candidates",
            "rules_version",
            "result",
            "status",
            "error",
            "updated_at",
        ]
    )
    _attach_render(look, presentation)
    _enrich_with_copy(look, chosen, snapshot)


def _composition_fingerprint(result: dict[str, Any], presentation: str) -> str:
    contract = {
        "golden_id": result.get("golden_id", ""),
        "presentation": presentation,
        "items": [
            {
                "item_key": item.get("item_key", ""),
                "bucket": item.get("s3_bucket", ""),
                "key": item.get("s3_key", ""),
            }
            for item in result.get("items") or []
        ],
    }
    raw = json.dumps(
        contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _render_request(look: DailyLook, presentation: str) -> OutfitRenderRequest | None:
    result = look.result or {}
    references: list[RenderItemReference] = []
    for index, item in enumerate(result.get("items") or [], start=1):
        image_ref = str(item.get("s3_key") or "").strip()
        if not image_ref:
            continue
        category = str(item.get("category") or "ITEM").strip().upper()
        references.append(
            RenderItemReference(
                item_id=str(item.get("item_key") or index),
                position=index,
                slot=f"{category}:{index}",
                source_type=RenderSource.GOLDENSET_ITEM,
                image_ref=image_ref,
                source_bucket=str(item.get("s3_bucket") or ""),
            )
        )
    if not references:
        return None
    fingerprint = _composition_fingerprint(result, presentation)
    return OutfitRenderRequest(
        composition_id=f"daily-look:{look.pk}",
        composition_fingerprint=fingerprint,
        items=tuple(references),
        subject_presentation=presentation,
    )


def _render_reference(entry) -> dict[str, Any]:
    return {
        "s3_bucket": entry.output_s3_bucket,
        "s3_key": entry.output_s3_key,
        "media_type": entry.output_media_type,
        "render_fingerprint": entry.render_fingerprint,
    }


def _attach_render(look: DailyLook, presentation: str) -> bool:
    request = _render_request(look, presentation)
    if request is None:
        return False
    try:
        entry, _ = render_artifacts.get_or_render(request)
    except Exception as exc:  # noqa: BLE001 - 이미지 실패가 추천 성공을 되돌리지 않는다.
        logger.warning("오늘의 룩 공통 렌더 실패: look=%s error=%s", look.pk, exc)
        look.error = f"착용 이미지 생성 실패(추천은 정상): {exc}"[:2000]
        look.save(update_fields=["error", "updated_at"])
        return False
    result = dict(look.result)
    result["render_image"] = _render_reference(entry)
    look.result = result
    look.save(update_fields=["result", "updated_at"])
    return True


def refresh_render(look: DailyLook) -> bool:
    """조회 스레드에서는 생성하지 않고 공통 캐시 확인 또는 재생성 예약만 한다."""
    if look.status != DailyLook.Status.SUCCEEDED or (look.result or {}).get(
        "render_image"
    ):
        return False
    presentation, _ = _presentation(look.body)
    request = _render_request(look, presentation)
    if request is None:
        return False
    render_fingerprint = render_artifacts.fingerprint(
        request.composition_fingerprint,
        request.subject_presentation,
    )
    try:
        entry = render_artifacts.find_cached(render_fingerprint)
    except Exception:
        logger.warning(
            "오늘의 룩 공통 렌더 캐시 확인 실패: look=%s", look.pk, exc_info=True
        )
        return False
    if entry is not None:
        result = dict(look.result)
        result["render_image"] = _render_reference(entry)
        look.result = result
        look.error = (
            "" if look.error.startswith("착용 이미지 생성 실패") else look.error
        )
        look.save(update_fields=["result", "error", "updated_at"])
        return True

    lock_key = f"daily-look:render-retry:{render_fingerprint}"
    try:
        if daily_look_queue.get_client().set(
            lock_key,
            "1",
            nx=True,
            ex=settings.DAILY_LOOK_RENDER_RETRY_COOLDOWN_SECONDS,
        ):
            daily_look_queue.enqueue(look.pk, job="render")
    except Exception:
        logger.warning(
            "오늘의 룩 렌더 재시도 예약 실패: look=%s", look.pk, exc_info=True
        )
    return False


def run_render_only(look_id: str) -> bool:
    look = DailyLook.objects.filter(
        pk=look_id, status=DailyLook.Status.SUCCEEDED
    ).first()
    if look is None or (look.result or {}).get("render_image"):
        return False
    presentation, _ = _presentation(look.body)
    return _attach_render(look, presentation)


def mark_failed(look: DailyLook, error: str) -> None:
    look.status = DailyLook.Status.FAILED
    look.error = error[:2000]
    look.save(update_fields=["status", "error", "updated_at"])


def _build_result(candidate, snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = candidate.payload
    bucket = str(payload.get("source_bucket") or "")
    temperature = (snapshot.get("weather") or {}).get("temperature")
    headline = "오늘의 추천 코디"
    if temperature is not None:
        try:
            headline = f"{round(float(temperature))}도, 오늘은 이렇게"
        except (TypeError, ValueError):
            pass
    notes = [reason.text for reason in candidate.reasons if reason.source == "rule"]
    return {
        "golden_id": candidate.golden_id,
        "headline": headline,
        "rationale_ko": " ".join(notes[:2]) or "오늘 조건과 취향에 맞춰 골랐어요.",
        "styling_tips": [],
        "generated_by": "template",
        "render_image": None,
        "outfit_image": (
            {"s3_bucket": bucket, "s3_key": str(payload.get("source_key") or "")}
            if payload.get("exposable") and payload.get("source_key")
            else None
        ),
        "items": [
            {
                "item_key": str(item.get("item_key") or ""),
                "name": str(item.get("item_name") or ""),
                "category": str(item.get("category_large") or ""),
                "sub_category": str(item.get("category_small") or ""),
                "layer_role": str(item.get("layer_role") or ""),
                "color": str(item.get("color") or ""),
                "s3_bucket": str(item.get("s3_bucket") or bucket),
                "s3_key": str(item.get("s3_key") or ""),
                "note": "",
            }
            for item in payload.get("items") or []
        ],
    }


def _candidate_snapshot(candidate) -> dict[str, Any]:
    return {
        "point_id": candidate.point_id,
        "golden_id": candidate.golden_id,
        "score": candidate.score,
        "similarity": candidate.similarity,
        "presentation_group": str(candidate.payload.get("presentation_group") or ""),
        "reasons": [
            {"source": reason.source, "delta": reason.delta, "text": reason.text}
            for reason in candidate.reasons
        ],
    }


def _enrich_with_copy(look: DailyLook, candidate, snapshot: dict[str, Any]) -> None:
    outfit = {
        "golden_id": candidate.golden_id,
        "style": candidate.payload.get("style", []),
        "season": candidate.payload.get("season", []),
        "occasion": candidate.payload.get("occasion", []),
        "items": [
            {
                "item_key": item.get("item_key"),
                "name": item.get("item_name"),
                "category": item.get("category_large"),
                "color": item.get("color"),
            }
            for item in candidate.payload.get("items") or []
        ],
        "rule_notes": [
            reason.text for reason in candidate.reasons if reason.source == "rule"
        ],
    }
    try:
        copy = gemini.write_daily_look_copy(outfit=outfit, context=snapshot)
    except Exception as exc:  # noqa: BLE001 - 설명 실패는 템플릿 추천을 되돌리지 않는다.
        logger.warning("오늘의 룩 설명 생성 실패: look=%s error=%s", look.pk, exc)
        return

    notes = {
        str(row.get("item_key")): str(row.get("note") or "")
        for row in copy.parsed.get("items") or []
    }
    result = dict(look.result)
    result["headline"] = copy.parsed.get("headline") or result["headline"]
    result["rationale_ko"] = copy.parsed.get("rationale_ko") or result["rationale_ko"]
    result["styling_tips"] = copy.parsed.get("styling_tips") or []
    result["generated_by"] = "llm"
    for item in result.get("items") or []:
        item["note"] = notes.get(str(item.get("item_key")), "")
    look.result = result
    look.llm_model = copy.model
    look.llm_request = copy.request
    look.llm_response = copy.response
    look.llm_latency_ms = copy.latency_ms
    look.save(
        update_fields=[
            "result",
            "llm_model",
            "llm_request",
            "llm_response",
            "llm_latency_ms",
            "updated_at",
        ]
    )
