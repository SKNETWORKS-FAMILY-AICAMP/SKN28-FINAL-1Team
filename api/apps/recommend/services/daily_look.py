"""오늘의 룩 생성 서비스.

    ensure_today_look()  로그인·조회 시점: 그날 행이 없으면 만들고 큐에 넣는다
    claim() / run()      워커에서: 리트리버 → Gemini → 결과 기록

코디 평가(services/analysis.py)와 뼈대는 같지만 시작점이 다르다. 저쪽은 사용자가
사진을 올려야 시작하고, 이쪽은 **사용자 입력이 없다.** 그날 처음 로그인하는 순간
자동으로 걸리고, 재료는 미리 저장된 체형·추구미와 그 시점 날씨다.

멱등성은 DB가 보장한다. (user, look_date) 유니크 제약이 있으므로 여러 기기에서
동시에 로그인해도 행은 하나다. 서비스는 IntegrityError를 '이미 있음'으로 읽는다 —
select 후 insert하는 방식은 그 사이에 다른 요청이 끼어들면 깨진다.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.recommend.models import DailyLook
from apps.recommend.services import gemini
from apps.recommend.services import queue as queue_service
from apps.recommend.services.body_profile import build_profile
from apps.recommend.services.outfit_context import build_analysis_context
from apps.recommend.services.retriever import RetrievalRequest, retrieve_outfits
from apps.recommend.services.style_rules import load_body_rules

logger = logging.getLogger(__name__)

#: LLM에 넘길 후보 수. 너무 많으면 프롬프트가 길어지고 모델이 고르는 근거가 흐려진다.
CANDIDATE_LIMIT = 5


def today(user=None) -> date:
    """추천이 속한 날짜. 서비스 타임존(Asia/Seoul) 기준의 '오늘'.

    UTC로 계산하면 한국 시간 오전 9시 이전 로그인이 전날로 묶여 사용자는
    "어제 룩이 그대로 나온다"고 느낀다.
    """
    return timezone.localdate()


def ensure_today_look(user, *, lat: float | None = None, lon: float | None = None):
    """그날 행이 없으면 만들고 큐에 넣는다. 이미 있으면 그대로 돌려준다.

    Returns: (DailyLook, created)
    """
    look_date = today(user)
    existing = DailyLook.objects.filter(user=user, look_date=look_date).first()
    if existing is not None:
        return existing, False

    context = build_analysis_context(user, lat=lat, lon=lon)
    body = context.get("body")
    profile = build_profile(body)

    try:
        with transaction.atomic():
            look = DailyLook.objects.create(
                user=user,
                look_date=look_date,
                status=DailyLook.Status.QUEUED,
                weather=context.get("weather") or {},
                body=body,
                body_profile=_profile_snapshot(profile),
                pursuit=context.get("pursuit"),
            )
    except IntegrityError:
        # 다른 요청이 한 발 먼저 만들었다. 경합은 정상 흐름이므로 조용히 그것을 쓴다.
        existing = DailyLook.objects.filter(user=user, look_date=look_date).first()
        if existing is None:
            raise
        return existing, False

    try:
        queue_service.push(
            {"look_id": str(look.pk)}, spec=queue_service.DAILY_LOOK
        )
    except Exception:  # noqa: BLE001 — 큐가 죽어도 행은 남기고 워커가 쓸어담는다
        logger.exception("오늘의 룩 %s 큐 적재 실패", look.pk)
    return look, True


def _profile_snapshot(profile) -> dict[str, Any]:
    return {
        "silhouette": profile.silhouette,
        "bmi_band": profile.bmi_band,
        "bmi": profile.bmi,
        "ratios": dict(profile.ratios),
        "known": list(profile.known),
        "missing": list(profile.missing),
        "describe": profile.describe(),
    }


def claim(look_id: str) -> DailyLook | None:
    """작업을 집어 PROCESSING으로 전환한다. 이미 끝난 건이면 None."""
    with transaction.atomic():
        look = DailyLook.objects.select_for_update().filter(pk=look_id).first()
        if look is None:
            return None
        if look.status == DailyLook.Status.SUCCEEDED:
            # 재시도로 같은 작업이 두 번 올 수 있다. 성공한 건은 다시 만들지 않는다.
            return None
        look.status = DailyLook.Status.PROCESSING
        look.save(update_fields=["status", "updated_at"])
        return look


def run(look: DailyLook) -> None:
    """리트리버로 후보를 뽑고 Gemini에 코디 구성·근거 생성을 맡긴다."""
    from apps.recommend.services.body_profile import BodyProfile

    snapshot = look.retrieval_context()
    saved = snapshot.get("body_profile") or {}
    profile = BodyProfile(
        silhouette=saved.get("silhouette", "unknown"),
        bmi_band=saved.get("bmi_band", "unknown"),
        bmi=saved.get("bmi"),
        ratios=dict(saved.get("ratios") or {}),
    )

    rules = load_body_rules()
    candidates = retrieve_outfits(
        RetrievalRequest(
            body=profile,
            pursuit=snapshot.get("pursuit"),
            weather=snapshot.get("weather"),
            limit=CANDIDATE_LIMIT,
        ),
        rules=rules,
    )

    look.candidates = [_candidate_snapshot(c) for c in candidates]
    look.rules_version = rules.schema_version

    if not candidates:
        # 실패와 구분한다. 프론트는 "잠시 후 다시"가 아니라 "프로필을 채워주세요"를
        # 띄워야 하고, 워커는 재시도해봐야 같은 결과다.
        look.status = DailyLook.Status.EMPTY
        # 무엇이 없어서 0건인지 남긴다. 사용자에게는 다 똑같이 "추천 없음"이지만,
        # 운영자에게는 '적재가 안 됐다'와 '이 사용자 조건이 좁다'가 전혀 다른 문제다.
        avoided = (snapshot.get("pursuit") or {}).get("avoided") or {}
        look.error = (
            "조건에 맞는 골든 코디 후보가 없습니다 "
            f"(체형={profile.silhouette}/{profile.bmi_band}, "
            f"기피축={sorted(k for k, v in avoided.items() if v) or '없음'})"
        )
        look.save(update_fields=["candidates", "rules_version", "status", "error",
                                 "updated_at"])
        logger.info("오늘의 룩 %s: 후보 0건", look.pk)
        return

    result = gemini.compose_daily_look(
        candidates=[_candidate_for_llm(c) for c in candidates],
        context=snapshot,
    )
    look.llm_model = result.model
    look.llm_request = result.request
    look.llm_response = result.response
    look.llm_latency_ms = result.latency_ms
    look.result = result.parsed
    look.status = DailyLook.Status.SUCCEEDED
    look.error = ""
    look.save(
        update_fields=[
            "candidates", "rules_version", "llm_model", "llm_request",
            "llm_response", "llm_latency_ms", "result", "status", "error",
            "updated_at",
        ]
    )


def _candidate_snapshot(candidate) -> dict[str, Any]:
    """DB에 남길 후보 요약. 벡터와 payload 전체는 넣지 않는다 (행이 비대해진다)."""
    return {
        "point_id": candidate.point_id,
        "golden_id": candidate.golden_id,
        "score": candidate.score,
        "similarity": candidate.similarity,
        "reasons": [
            {"source": r.source, "delta": r.delta, "text": r.text}
            for r in candidate.reasons
        ],
        "item_keys": list(candidate.payload.get("item_keys", [])),
    }


def _candidate_for_llm(candidate) -> dict[str, Any]:
    """LLM 프롬프트에 넣을 형태. 이미지 대신 태그와 근거만 넘긴다.

    골든 원본은 대개 exposable=False라 사용자에게 그대로 보여줄 수 없다. 모델도
    사진을 볼 필요가 없다 — 조합과 근거를 말로 풀어내는 일이라 태그로 충분하고,
    멀티모달 호출보다 훨씬 싸다.
    """
    payload = candidate.payload
    return {
        "golden_id": candidate.golden_id,
        "score": candidate.score,
        "style": payload.get("style", []),
        "season": payload.get("season", []),
        "occasion": payload.get("occasion", []),
        "items": [
            {
                "item_key": item.get("item_key"),
                "name": item.get("item_name"),
                "category": item.get("category_large"),
                "sub_category": item.get("category_small"),
                "layer_role": item.get("layer_role"),
                "color": item.get("color"),
            }
            for item in payload.get("items", [])
        ],
        "rule_notes": [r.text for r in candidate.reasons if r.source == "rule"],
        "preference_notes": [
            r.text for r in candidate.reasons if r.source == "preference"
        ],
    }


def mark_failed(look: DailyLook, error: str) -> None:
    look.status = DailyLook.Status.FAILED
    look.error = error[:2000]
    look.save(update_fields=["status", "error", "updated_at"])
