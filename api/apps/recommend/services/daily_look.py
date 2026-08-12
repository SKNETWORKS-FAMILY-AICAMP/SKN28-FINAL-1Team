"""오늘의 룩 생성 서비스.

    ensure_today_look()  홈 진입·조회 시점: 그날 행이 없으면 만들고 큐에 넣는다
    claim() / run()      워커에서: 리트리버 → Gemini → 결과 기록

코디 평가(services/analysis.py)와 뼈대는 같지만 시작점이 다르다. 저쪽은 사용자가
사진을 올려야 시작하고, 이쪽은 **사용자 입력이 없다.** 그날 처음 홈 화면에
들어오는 순간(GET /api/v1/home/) 자동으로 걸리고, 재료는 미리 저장된
체형·추구미와 그 시점 날씨다.

멱등성은 DB가 보장한다. (user, look_date) 유니크 제약이 있으므로 여러 기기에서
동시에 홈을 열어도 행은 하나다. 서비스는 IntegrityError를 '이미 있음'으로 읽는다 —
select 후 insert하는 방식은 그 사이에 다른 요청이 끼어들면 깨진다.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.recommend.models import DailyLook
from apps.recommend.services import gemini
from apps.recommend.services import outfit_render
from apps.recommend.services import queue as queue_service
from apps.recommend.services.body_profile import build_profile
from apps.recommend.services.gender import normalize_gender
from apps.recommend.services.outfit_context import build_analysis_context
from apps.recommend.services.retriever import RetrievalRequest, retrieve_outfits
from apps.recommend.services.style_rules import load_body_rules

logger = logging.getLogger(__name__)

#: LLM에 넘길 후보 수. 너무 많으면 프롬프트가 길어지고 모델이 고르는 근거가 흐려진다.
CANDIDATE_LIMIT = 5

#: 최근 며칠간 나간 코디를 다시 추천하지 않을지. 하루 1건이므로 최대 5개
#: 골든 코디가 제외 대상이 된다.
RECENT_EXCLUDE_DAYS = 5


def today(user=None) -> date:
    """추천이 속한 날짜. 서비스 타임존(Asia/Seoul) 기준의 '오늘'.

    UTC로 계산하면 한국 시간 오전 9시 이전 접속이 전날로 묶여 사용자는
    "어제 룩이 그대로 나온다"고 느낀다.
    """
    return timezone.localdate()


def _recent_golden_ids(user, look_date: date) -> frozenset[str]:
    """이 사용자에게 최근 RECENT_EXCLUDE_DAYS일 동안 **실제로 나간** 골든 코디 id.

    '나간 것'의 기준은 채택된 결과(result.golden_id)다. 후보 목록(candidates)까지
    빼면 하루에 5개씩 소진돼 골든셋이 작을 때 며칠 만에 뺄 코디가 없어진다 —
    사용자가 본 것은 1위 하나뿐이므로 그것만 반복으로 친다.

    오늘 행(look_date 당일)은 넣지 않는다. FAILED 재시도로 같은 날 run()이 다시
    돌 때, 아직 결과도 없는 자기 자신 때문에 후보가 좁아지면 안 된다.
    """
    rows = DailyLook.objects.filter(
        user=user,
        status=DailyLook.Status.SUCCEEDED,
        look_date__gte=look_date - timedelta(days=RECENT_EXCLUDE_DAYS),
        look_date__lt=look_date,
    ).values_list("result", flat=True)
    return frozenset(
        str(row["golden_id"])
        for row in rows
        if isinstance(row, dict) and row.get("golden_id")
    )


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
    gender = normalize_gender((snapshot.get("body") or {}).get("gender"))

    # 성별을 모르면 추천을 만들지 않는다.
    #
    # 예전에는 그냥 필터 없이 검색해서, 성별이 비어 있는 사용자에게 아무 코디나
    # 나갔다. 사용자 입장에서 그건 "덜 맞는 추천"이 아니라 틀린 추천이다 —
    # 남성에게 여성복이 나오면 기능 전체의 신뢰가 무너진다. 검색 계층은 범용이라
    # 제약을 스스로 만들지 않으므로, 그 판단은 오늘의 룩이 여기서 내린다.
    if not gender:
        look.status = DailyLook.Status.EMPTY
        look.rules_version = rules.schema_version
        look.candidates = []
        look.error = (
            "성별 정보가 없어 오늘의 룩을 만들지 않았습니다. "
            "체형 정보(PUT /users/me/body/basic)에 성별을 저장한 뒤 다시 로그인하세요."
        )
        look.save(update_fields=["candidates", "rules_version", "status", "error",
                                 "updated_at"])
        logger.warning("오늘의 룩 %s: 성별 미상으로 생성 중단", look.pk)
        return

    candidates = retrieve_outfits(
        RetrievalRequest(
            body=profile,
            pursuit=snapshot.get("pursuit"),
            weather=snapshot.get("weather"),
            gender=gender,
            limit=CANDIDATE_LIMIT,
            # 최근 며칠 안에 이미 나간 코디는 top k에서 빼고 다음 순위로 채운다.
            # 골든셋·규칙이 그대로면 순위도 그대로라, 이게 없으면 매일 같은
            # 코디가 1위로 뽑혀 "오늘의" 룩이 아니게 된다.
            exclude_golden_ids=_recent_golden_ids(look.user, look.look_date),
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
            f"(성별={gender or '미지정'}, "
            f"체형={profile.silhouette}/{profile.bmi_band}, "
            f"기피축={sorted(k for k, v in avoided.items() if v) or '없음'})"
        )
        look.save(update_fields=["candidates", "rules_version", "status", "error",
                                 "updated_at"])
        logger.info("오늘의 룩 %s: 후보 0건", look.pk)
        return

    # ── 여기까지가 추천의 성립 조건이다 ──────────────────────
    # 코디는 리트리버가 정한다. 1위를 그대로 채택하고, 문장이 붙기 전에 상태를
    # SUCCEEDED로 확정한다. 예전에는 Gemini가 죽으면 FAILED가 되어, 멀쩡히 찾아둔
    # 코디가 있는데도 사용자는 아무것도 못 봤다.
    chosen = candidates[0]
    look.result = _build_result(chosen, snapshot)
    look.status = DailyLook.Status.SUCCEEDED
    look.error = ""
    look.save(
        update_fields=["candidates", "rules_version", "result", "status", "error",
                       "updated_at"]
    )

    # ── 여기부터는 있으면 좋은 것 ────────────────────────────
    # 둘 다 실패해도 추천은 이미 SUCCEEDED다. 화면은 아이템 카드로 성립한다.
    _attach_render(look, chosen, gender)
    _enrich_with_copy(look, chosen, snapshot)


def _attach_render(look: DailyLook, candidate, gender: str = "") -> None:
    """정면 착용 이미지를 붙인다. 이미 만들어 둔 코디면 생성 없이 참조만 얻는다.

    성별을 함께 넘긴다. 유니섹스 코디는 남녀 모두에게 추천되므로 그 사용자에
    맞는 모델로 그려야 하고, 성별별로 따로 저장·재사용한다.
    """
    payload = candidate.payload
    try:
        reference = outfit_render.ensure_render(
            bucket=str(payload.get("source_bucket", "")),
            items=list(payload.get("items", [])),
            gender=gender,
        )
    except Exception as exc:  # noqa: BLE001 — 이미지 실패가 추천을 되돌리면 안 된다
        logger.warning("오늘의 룩 %s 착용 이미지 실패: %s", look.pk, exc)
        look.error = f"착용 이미지 생성 실패(추천은 정상): {exc}"[:2000]
        look.save(update_fields=["error", "updated_at"])
        return

    if reference is None:
        return
    result = dict(look.result)
    result["render_image"] = reference.as_dict()
    look.result = result
    look.save(update_fields=["result", "updated_at"])


# ── 조회 시점의 착용 이미지 보정 ──────────────────────────
#
# 착용 이미지 생성은 생성 시점에 실패해도 다음 시행에서 성공하는 일이 잦다
# (제공자 일시 오류·타임아웃). 그런데 결과 JSON은 생성이 끝날 때 한 번만 쓰이므로,
# 그 한 번이 실패하면 이미지가 S3에 생긴 뒤에도 행은 계속 비어 있다. 사용자는
# 그날 내내 대표 이미지를 못 본다.
#
# 그래서 조회할 때마다 한 번 더 본다. 조회는 폴링으로 자주 들어오므로 두 가지를
# 분리했다.
#
#   1. 이미 S3에 있는가  → HEAD 한두 번. 조회 경로에서 바로 확인하고 붙인다.
#   2. 아직 없다         → 생성은 수십 초라 요청을 잡아둘 수 없다. 큐에 넣되
#                          쿨다운을 걸어 폴링마다 재생성이 쌓이지 않게 한다.

#: 같은 코디의 재생성을 다시 걸기까지의 최소 간격. 프론트가 2초마다 폴링해도
#: 이 간격 안에서는 한 번만 걸린다. 락은 코디(= 착용 이미지 키) 단위라 같은
#: 코디를 받은 여러 사용자가 동시에 눌러도 생성은 한 번이다.
RENDER_RETRY_COOLDOWN_SECONDS = int(
    os.getenv("DAILY_LOOK_RENDER_RETRY_COOLDOWN_SECONDS", "600")
)

#: 큐 페이로드의 작업 종류. 없으면 기존처럼 전체 생성이다 (하위호환).
JOB_RENDER = "render"


def _render_source(result: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """결과 JSON에서 착용 이미지 생성에 필요한 재료를 되살린다.

    Qdrant를 다시 조회하지 않는다. 결과에 이미 아이템의 버킷·키·분류가 들어
    있고, 벡터스토어는 재적재로 내용이 바뀔 수 있어 그때의 기록이 더 정확하다.

    _build_result()가 category_large를 `category`로 줄여 담으므로 여기서 원래
    이름으로 되돌린다 — 참조를 고를 때 그 값으로 우선순위를 매긴다.
    """
    items = result.get("items") or []
    bucket = ""
    restored: list[dict[str, Any]] = []
    for item in items:
        if not item.get("s3_key"):
            continue
        bucket = bucket or str(item.get("s3_bucket") or "")
        restored.append(
            {
                "s3_key": item.get("s3_key"),
                "s3_bucket": item.get("s3_bucket"),
                "category_large": item.get("category"),
                "item_name": item.get("name"),
            }
        )
    return bucket, restored


def refresh_render(look: DailyLook) -> bool:
    """조회 시점에 착용 이미지를 한 번 더 확인해 붙인다.

    Returns: 행을 갱신했으면 True.

    생성은 하지 않는다. 이 함수는 사용자의 요청 스레드에서 돌고, 이미지 생성은
    수십 초가 걸린다. 대신 이미 만들어져 있으면 붙이고, 없으면 재생성을 큐에
    맡긴다.
    """
    if look.status != DailyLook.Status.SUCCEEDED:
        return False
    result = look.result or {}
    if not result or result.get("render_image"):
        return False

    bucket, items = _render_source(result)
    if not bucket or not items:
        return False

    gender = normalize_gender((look.body or {}).get("gender"))
    reference = outfit_render.existing_render(
        bucket, str(items[0]["s3_key"]), gender
    )
    if reference is None:
        _schedule_render_retry(look, bucket, str(items[0]["s3_key"]), gender)
        return False

    result = dict(result)
    result["render_image"] = reference.as_dict()
    look.result = result
    fields = ["result", "updated_at"]
    # 이미지가 붙었으면 그때의 실패 메시지는 사실이 아니다. 남겨두면 운영자가
    # 멀쩡한 행을 계속 문제로 읽는다.
    if look.error.startswith("착용 이미지 생성 실패"):
        look.error = ""
        fields.append("error")
    look.save(update_fields=fields)
    logger.info(
        "오늘의 룩 %s 착용 이미지 보정: s3://%s/%s",
        look.pk, reference.s3_bucket, reference.s3_key,
    )
    return True


def _schedule_render_retry(
    look: DailyLook, bucket: str, item_key: str, gender: str = ""
) -> None:
    """아직 없으면 재생성을 큐에 건다. 쿨다운 안에서는 한 번만.

    락이 없으면 프론트 폴링(기본 2초)마다 생성 작업이 쌓여 요금이 폭주한다.
    락 키를 사용자가 아니라 **착용 이미지 키**로 잡는 이유는, 같은 골든 코디를
    받은 사용자가 여럿이어도 만들 이미지는 하나이기 때문이다.
    """
    if not settings.DAILY_LOOK_RENDER_ENABLED:
        return
    # 성별을 키에 넣는다. 같은 코디라도 남성용·여성용 이미지는 별개라,
    # 하나로 묶으면 한쪽이 쿨다운에 막혀 영영 안 만들어진다.
    lock_key = f"daily_look:render_retry:{bucket}:{item_key}:{gender or 'none'}"
    try:
        client = queue_service.get_client()
        acquired = client.set(
            lock_key, "1", nx=True, ex=RENDER_RETRY_COOLDOWN_SECONDS
        )
        if not acquired:
            return
        queue_service.push(
            {"look_id": str(look.pk), "job": JOB_RENDER}, spec=queue_service.DAILY_LOOK
        )
    except Exception:  # noqa: BLE001 — 보정 실패가 조회를 막으면 안 된다
        logger.warning("오늘의 룩 %s 착용 이미지 재생성 예약 실패", look.pk, exc_info=True)
        return
    logger.info("오늘의 룩 %s 착용 이미지 재생성 예약", look.pk)


def run_render_only(look_id: str) -> bool:
    """워커에서: 추천은 건드리지 않고 착용 이미지만 다시 만든다.

    claim()을 쓰지 않는다. 그 함수는 SUCCEEDED면 None을 돌려주는데, 여기서
    다루는 건 정확히 **이미 성공한 행**이다. 상태도 바꾸지 않는다 — 이미지가
    없다고 해서 사용자에게 '생성 중'을 다시 보여줄 이유가 없다.

    Returns: 이미지를 붙였으면 True.
    """
    look = DailyLook.objects.filter(pk=look_id).first()
    if look is None or look.status != DailyLook.Status.SUCCEEDED:
        return False
    result = look.result or {}
    if result.get("render_image"):
        return False

    bucket, items = _render_source(result)
    if not bucket or not items:
        return False

    try:
        reference = outfit_render.ensure_render(
            bucket=bucket,
            items=items,
            gender=normalize_gender((look.body or {}).get("gender")),
        )
    except Exception as exc:  # noqa: BLE001 — 이미지 실패가 추천을 되돌리면 안 된다
        logger.warning("오늘의 룩 %s 착용 이미지 재생성 실패: %s", look.pk, exc)
        look.error = f"착용 이미지 생성 실패(추천은 정상): {exc}"[:2000]
        look.save(update_fields=["error", "updated_at"])
        return False

    if reference is None:
        return False

    result = dict(result)
    result["render_image"] = reference.as_dict()
    look.result = result
    fields = ["result", "updated_at"]
    if look.error.startswith("착용 이미지 생성 실패"):
        look.error = ""
        fields.append("error")
    look.save(update_fields=fields)
    logger.info("오늘의 룩 %s 착용 이미지 재생성 완료", look.pk)
    return True


def _build_result(candidate, snapshot: dict[str, Any]) -> dict[str, Any]:
    """LLM 없이도 화면을 그릴 수 있는 결과를 만든다.

    이미지 URL은 **넣지 않는다.** presigned URL은 만료되므로 조회 시점에
    만들어야 한다 — DB에 구워 넣으면 며칠 뒤 죽은 링크가 남는다. 대신 버킷과
    키를 담아 두고 직렬화 단계가 서명한다.

    아이템 이미지는 원본 사진이 아니라 파이프라인이 만든 흰 배경 파생물이라,
    원본이 노출 불가(exposable=False)여도 보여줄 수 있다.
    """
    payload = candidate.payload
    bucket = str(payload.get("source_bucket", ""))
    rule_notes = [r.text for r in candidate.reasons if r.source == "rule"]

    return {
        "golden_id": candidate.golden_id,
        "headline": _template_headline(snapshot),
        "rationale_ko": _template_rationale(rule_notes, snapshot),
        "styling_tips": [],
        # 문장을 누가 썼는지 프론트가 알 수 있게 한다 (템플릿이면 담백한 톤이다).
        "generated_by": "template",
        # 정면 착용 이미지. 코디당 한 번만 만들고 재사용하므로, 여기서는
        # 자리만 비워 두고 _attach_render()가 채운다.
        "render_image": None,
        # 원본 코디 사진은 사용권이 열린 것만 내보낸다.
        "outfit_image": (
            {"s3_bucket": bucket, "s3_key": str(payload.get("source_key", ""))}
            if payload.get("exposable") and payload.get("source_key")
            else None
        ),
        "items": [
            {
                "item_key": item.get("item_key", ""),
                "name": item.get("item_name", ""),
                "category": item.get("category_large", ""),
                "sub_category": item.get("category_small", ""),
                "layer_role": item.get("layer_role", ""),
                "color": item.get("color", ""),
                "s3_bucket": bucket,
                "s3_key": item.get("s3_key", ""),
                "note": "",
            }
            for item in payload.get("items", [])
        ],
    }


def _template_headline(snapshot: dict[str, Any]) -> str:
    weather = snapshot.get("weather") or {}
    temperature = weather.get("temperature")
    if temperature is None:
        return "오늘의 추천 코디"
    return f"{round(float(temperature))}도, 오늘은 이렇게"


def _template_rationale(rule_notes: list[str], snapshot: dict[str, Any]) -> str:
    """규칙표 문장을 이어 붙인다.

    규칙표의 reason이 이미 한국어 문장이라 그대로 재료가 된다. LLM이 붙으면 이걸
    더 자연스럽게 다듬는 것이지, 없다고 못 쓸 내용은 아니다.
    """
    profile = snapshot.get("body_profile") or {}
    parts: list[str] = []
    if describe := profile.get("describe"):
        parts.append(f"{describe} 기준으로 골랐어요.")
    if rule_notes:
        # 같은 근거가 여러 아이템에서 나올 수 있어 앞의 두 개만 쓴다.
        parts.append(" ".join(note.rstrip(".") + "." for note in rule_notes[:2]))
    weather = snapshot.get("weather") or {}
    if (temperature := weather.get("temperature")) is not None:
        parts.append(f"기온은 {round(float(temperature))}도입니다.")
    return " ".join(parts) or "오늘 조건에 맞춰 골랐어요."


def _enrich_with_copy(look: DailyLook, candidate, snapshot: dict[str, Any]) -> None:
    """문장을 LLM으로 다듬는다. 실패해도 추천은 그대로 남는다.

    매일 같은 사용자에게 나가는 기능이라 템플릿만으로는 사흘이면 "또 같은 말"이
    된다. 그래서 LLM을 쓰되, 없어도 기능이 성립하도록 순서를 뒤에 뒀다.
    """
    try:
        copy = gemini.write_daily_look_copy(
            outfit=_candidate_for_llm(candidate), context=snapshot
        )
    except Exception as exc:  # noqa: BLE001 — 문장 실패가 추천을 되돌리면 안 된다
        logger.warning("오늘의 룩 %s 문장 생성 실패 (템플릿 유지): %s", look.pk, exc)
        look.error = f"문장 생성 실패(추천은 정상): {type(exc).__name__}: {exc}"[:2000]
        look.save(update_fields=["error", "updated_at"])
        return

    notes = {
        str(row.get("item_key")): str(row.get("note", ""))
        for row in copy.parsed.get("items") or []
    }
    result = dict(look.result)
    result.update(
        {
            "headline": copy.parsed.get("headline") or result["headline"],
            "rationale_ko": copy.parsed.get("rationale_ko") or result["rationale_ko"],
            "styling_tips": copy.parsed.get("styling_tips") or [],
            "generated_by": "llm",
        }
    )
    for item in result["items"]:
        item["note"] = notes.get(item["item_key"], "")

    look.result = result
    look.llm_model = copy.model
    look.llm_request = copy.request
    look.llm_response = copy.response
    look.llm_latency_ms = copy.latency_ms
    look.save(
        update_fields=["result", "llm_model", "llm_request", "llm_response",
                       "llm_latency_ms", "updated_at"]
    )


def _candidate_snapshot(candidate) -> dict[str, Any]:
    """DB에 남길 후보 요약. 벡터와 payload 전체는 넣지 않는다 (행이 비대해진다)."""
    return {
        "point_id": candidate.point_id,
        "golden_id": candidate.golden_id,
        "score": candidate.score,
        "similarity": candidate.similarity,
        # 성별 사고가 재발하면 이 한 칸만 보면 된다. 후보에 무엇이 통과했는지
        # 남기지 않았던 탓에 지난번엔 Qdrant를 따로 뒤져야 했다.
        "presentation_group": str(candidate.payload.get("presentation_group") or ""),
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
