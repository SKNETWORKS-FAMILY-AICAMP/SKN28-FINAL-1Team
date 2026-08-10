"""골든 코디 리트리버 — 추천 기능 세 개가 공유하는 베이스.

"오늘의 룩 추천", "옷장 기반 추천", "추구미 기반 추천"이 전부 이 위에 올라간다.
셋의 차이는 입력을 어떻게 채우느냐뿐이고, 검색·필터·점수화는 여기서 한 번만 한다.

가이드 6장의 하이브리드 분담을 그대로 따른다.

    기피/탈락 요건 (Hard)  → 이 모듈. 필터로 즉시 떨어뜨린다.
    가중치·컨텍스트 (Soft) → 이 모듈이 점수와 근거만 계산한다.
    설명문 생성            → 이 모듈 밖(Agent). reasons를 재료로 쓴다.

우선순위는 가이드 Q2를 따른다. **사용자 취향이 1순위, 체형 규칙이 2순위.**
가중치로 그 서열을 표현한다 (preference_avoid -60 vs rule_avoid -20).

이 모듈은 LLM을 부르지 않는다. 순수 함수형 검색 계층이라 테스트가 쉽고, 응답
지연이 예측 가능하다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from qdrant_client import models as qm

from apps.recommend.services import vocabulary
from apps.recommend.services.body_profile import BodyProfile
from apps.recommend.services.qdrant import (
    GOLDEN_ITEM_COLLECTION,
    GOLDEN_OUTFIT_COLLECTION,
    IMAGE_VECTOR,
    get_client,
)
from apps.recommend.services.style_rules import (
    BodyRules,
    Rule,
    WeatherBand,
    load_body_rules,
    load_weather_rules,
)

logger = logging.getLogger(__name__)

#: 코디 payload에 인덱스가 있어 Qdrant 필터로 바로 쓸 수 있는 축.
#: `fit`·`length`·`sleeve`는 코디 단계에 인덱스가 없다 — 아이템 컬렉션을 거친다.
OUTFIT_FILTER_FIELDS = frozenset(
    {"style", "season", "occasion", "item_layer_roles", "item_categories"}
)

#: 성별 표현 그룹. golden_set/manifest.py의 표준 값과 같아야 한다.
#: golden_set은 Django 없이 도는 패키지라 import할 수 없어 값을 복제한다 —
#: point_ids.POINT_NAMESPACE와 같은 이유다. 한쪽을 바꾸면 다른 쪽도 바꿔야 한다.
PRESENTATION_UNISEX = "unisex"
GENDER_TO_PRESENTATION = {"male": "men", "female": "women"}

#: 후보를 몇 배수로 넉넉히 뽑아 놓고 점수화 후 자를지. 소프트 감점 때문에
#: 상위 N개가 뒤바뀌므로 limit만큼만 뽑으면 좋은 후보를 놓친다.
_OVERFETCH = 4


@dataclass(frozen=True)
class RetrievalRequest:
    """세 기능이 공유하는 입력. 채우지 않은 축은 그냥 반영되지 않는다."""

    body: BodyProfile | None = None
    #: users/services/pursuit.get_pursuit() 의 payload 그대로
    pursuit: dict[str, dict[str, list[str]]] | None = None
    weather: dict[str, Any] | None = None
    #: 사용자 성별 (BodyMeasurement.gender: "male" | "female" | ""). 값이 있으면
    #: 성별 표현이 다른 코디를 검색에서 즉시 탈락시킨다 — 가이드 6장의 하드 필터.
    gender: str = ""
    occasion: str = ""
    #: 자유 문구 (예: "비 오는 날 출근룩"). 있으면 텍스트 벡터로 검색한다.
    query_text: str = ""
    #: 코디를 찍은 이미지 벡터로 검색할 때 (옷장 기반 추천의 '비슷한 코디')
    image_vector: list[float] | None = None
    limit: int = 10
    #: 기피 규칙을 하드 필터로 걸지. 가이드 6장 기본 동작.
    hard_filter: bool = True
    #: 노출 가능한 원본만 (기본은 제한 없음 — 골든 원본은 대개 exposable=False다)
    exposable_only: bool = False


@dataclass(frozen=True)
class Reason:
    """점수가 움직인 이유 한 줄. Agent가 설명문을 만들 재료다."""

    source: str          # "preference" | "rule" | "similarity"
    delta: float
    text: str


@dataclass(frozen=True)
class OutfitCandidate:
    point_id: str
    golden_id: str
    score: float
    similarity: float
    reasons: tuple[Reason, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def items(self) -> list[dict[str, Any]]:
        return list(self.payload.get("items", []))


def _any_of(field_name: str, values: Iterable[str]) -> qm.FieldCondition:
    return qm.FieldCondition(key=field_name, match=qm.MatchAny(any=sorted(values)))


def build_filter(
    request: RetrievalRequest,
    *,
    rules: BodyRules | None = None,
) -> qm.Filter | None:
    """검색 단계에서 걸 수 있는 조건만 Qdrant 필터로 만든다.

    코디 포인트에 인덱스가 있는 축만 다룬다. 나머지(핏·기장 등)는 아이템 단계나
    파이썬 후처리로 넘어간다 — `_hard_excluded_outfits()` 참고.
    """
    must: list[qm.Condition] = []
    must_not: list[qm.Condition] = []

    if request.exposable_only:
        must.append(qm.FieldCondition(key="exposable", match=qm.MatchValue(value=True)))

    # 성별은 하드 필터다. 남성 사용자에게 여성 코디를 "순위만 낮춰" 보여주는 건
    # 추천이 아니라 오작동으로 읽힌다. 계절과 달리 감점으로 둘 수 없는 축이다.
    #
    # 라벨이 없는 코디(presentation_group="")는 여기서 함께 빠진다. 미분류를
    # unisex로 취급하면 여성 코디가 그대로 남성에게 나가므로, 조용히 통과시키는
    # 대신 빠지게 두고 EMPTY 사유에 그 사실을 적는다.
    if presentation := GENDER_TO_PRESENTATION.get(request.gender.strip().lower()):
        must.append(_any_of("presentation_group", [presentation, PRESENTATION_UNISEX]))

    # 계절·상황은 하드 필터로 걸지 않는다.
    #
    # 가이드 6장은 하드 필터를 "절대적인 기피 규칙"에만 쓰라고 했는데 처음엔
    # 여기에 계절까지 얹었다. 그러자 모든 추천이 EMPTY로 끝났다 — 골든 코디의
    # season/style/occasion은 analyses.jsonl에서 오는데 그 분석 단계가 유료
    # 호출이 커서 기본으로 꺼져 있어, 적재된 포인트가 전부 빈 배열이었기
    # 때문이다. 있지도 않은 값에 must를 걸면 결과는 언제나 0건이다.
    #
    # 계절은 "맞으면 좋은 것"이지 "틀리면 탈락"이 아니다. 소프트 가산으로 옮겨
    # _score_context()가 처리한다. 태그가 채워진 뒤에도 이 판단은 유효하다.

    if request.pursuit:
        preferred = vocabulary.translate(request.pursuit.get("preferred"))
        avoided = vocabulary.translate(request.pursuit.get("avoided"))
        # 선호 스타일은 좁히는 조건이 아니라 넓히는 조건이라 must에 넣지 않는다.
        # 반면 기피 스타일은 사용자가 명시적으로 거부한 것이라 즉시 탈락시킨다.
        if request.hard_filter:
            for tag_field, labels in avoided.tags.items():
                if tag_field in OUTFIT_FILTER_FIELDS and labels:
                    must_not.append(_any_of(tag_field, labels))
        if preferred.unmapped or avoided.unmapped:
            logger.info(
                "검색에 반영하지 못한 선호 항목: %s",
                sorted(set(preferred.unmapped) | set(avoided.unmapped)),
            )

    if not must and not must_not:
        return None
    return qm.Filter(must=must or None, must_not=must_not or None)


def _season_from_weather(weather: dict[str, Any] | None) -> str:
    """기온을 태그 어휘의 계절로 바꾼다. 날씨가 없으면 빈 문자열."""
    if not weather:
        return ""
    temperature = weather.get("temperature")
    if temperature is None:
        return ""
    try:
        celsius = float(temperature)
    except (TypeError, ValueError):
        return ""
    if celsius >= 23:
        return "여름"
    if celsius >= 17:
        return "간절기"
    if celsius >= 9:
        return "가을"
    return "겨울"


def _hard_excluded_outfits(
    client, rules: BodyRules, profile: BodyProfile, limit: int
) -> set[str]:
    """하드 기피 규칙에 걸리는 아이템을 가진 코디의 point_id를 모은다.

    코디 포인트에는 핏·기장 인덱스가 없다. 그래서 아이템 컬렉션에서 먼저
    '걸리는 아이템'을 찾고 그 `outfit_point_id`를 제외 목록으로 쓴다. 코디
    payload에 핏을 심어 인덱싱하면 이 왕복이 사라지지만, 그건 재적재가 필요하다.
    """
    hard = [rule for rule in rules.for_profile(profile).avoid if rule.hard]
    if not hard:
        return set()

    excluded: set[str] = set()
    for rule in hard:
        conditions = [
            qm.FieldCondition(key=field_name, match=qm.MatchValue(value=value))
            for field_name, value in rule.match.items()
            # 아이템 컬렉션에 인덱스가 있는 축만. `length`·`sleeve`는 payload에
            # 있어도 인덱스가 없어 필터로 못 쓴다 (services/qdrant.py 참고).
            if field_name in {"category_large", "category_small", "fit", "color",
                              "pattern", "material", "layer_role", "style", "season"}
        ]
        if len(conditions) != len(rule.match):
            # 인덱스 없는 축이 섞인 규칙은 이 단계에서 정확히 걸 수 없다.
            # 소프트 감점으로는 여전히 작동하므로 조용히 넘어가되 흔적을 남긴다.
            logger.debug("하드 필터로 옮기지 못한 규칙: %s", rule.match)
            continue
        points, _ = client.scroll(
            collection_name=GOLDEN_ITEM_COLLECTION,
            scroll_filter=qm.Filter(must=conditions),
            with_payload=["outfit_point_id"],
            with_vectors=False,
            limit=limit,
        )
        excluded.update(
            str(point.payload.get("outfit_point_id"))
            for point in points
            if point.payload.get("outfit_point_id")
        )
    return excluded


def _score_items(
    items: list[dict[str, Any]],
    *,
    rules_prefer: tuple[Rule, ...],
    rules_avoid: tuple[Rule, ...],
    preferred_tags: dict[str, set[str]],
    avoided_tags: dict[str, set[str]],
    weights,
) -> tuple[float, list[Reason]]:
    """코디에 속한 아이템들을 규칙·취향에 비추어 점수화한다.

    같은 근거가 아이템마다 반복되면 설명이 지저분해지므로 이유는 한 번만 남긴다.
    """
    total = 0.0
    reasons: list[Reason] = []
    seen: set[str] = set()

    def add(delta: float, source: str, text: str) -> None:
        nonlocal total
        total += delta
        if text not in seen:
            seen.add(text)
            reasons.append(Reason(source=source, delta=delta, text=text))

    for item in items:
        for tag_field, labels in avoided_tags.items():
            value = item.get(tag_field)
            if value in labels:
                add(
                    weights.preference_avoid,
                    "preference",
                    f"기피 항목 '{value}'이(가) 포함됨",
                )
        for tag_field, labels in preferred_tags.items():
            value = item.get(tag_field)
            if value in labels:
                add(weights.preference_match, "preference", f"선호 항목 '{value}' 일치")

        for rule in rules_avoid:
            if rule.matches(item):
                add(weights.rule_avoid, "rule", rule.reason)
        for rule in rules_prefer:
            if rule.matches(item):
                add(weights.rule_prefer, "rule", rule.reason)

    return total, reasons


def celsius_of(weather: dict[str, Any] | None) -> float | None:
    """날씨 dict에서 섭씨 기온을 꺼낸다. 값이 없거나 숫자가 아니면 None."""
    if not weather:
        return None
    try:
        return float(weather.get("temperature"))
    except (TypeError, ValueError):
        return None


def _score_weather(
    items: list[dict[str, Any]], band: WeatherBand | None, weights
) -> tuple[float, list[Reason]]:
    """기온대에 맞지 않는 아이템을 감점하고 맞는 아이템을 가산한다.

    검색 필터로 아예 제외하지 않는 이유가 있다. 27도에 아우터가 든 코디를 전부
    빼버리면, 골든셋이 아우터 코디 위주일 때 후보가 0건이 되어 사용자는 아무것도
    못 본다 — 계절을 하드 필터로 걸었다가 모든 추천이 EMPTY로 끝난 적이 있다.
    감점은 순위만 밀어내므로 그 사고가 없다.

    같은 근거는 아이템이 여럿이어도 한 번만 남긴다.
    """
    if band is None:
        return 0.0, []

    total = 0.0
    reasons: list[Reason] = []
    seen: set[str] = set()

    def add(delta: float, text: str) -> None:
        nonlocal total
        total += delta
        if text not in seen:
            seen.add(text)
            reasons.append(Reason(source="weather", delta=delta, text=text))

    for item in items:
        for rule in band.discourage:
            if rule.matches(item):
                add(weights.discourage, rule.reason)
        for rule in band.encourage:
            if rule.matches(item):
                add(weights.encourage, rule.reason)
    return total, reasons


def _score_context(
    payload: dict[str, Any], *, season: str, occasion: str, weights
) -> tuple[float, list[Reason]]:
    """계절·상황이 맞으면 가산한다. 안 맞아도 탈락시키지 않는다.

    태그가 비어 있으면(분석 단계를 돌리지 않은 골든셋) 가산도 감산도 없다 —
    "정보가 없음"과 "안 맞음"은 다르다.
    """
    total = 0.0
    reasons: list[Reason] = []
    if season and season in (payload.get("season") or []):
        total += weights.context_match
        reasons.append(
            Reason(source="context", delta=weights.context_match, text=f"{season} 코디")
        )
    if occasion and occasion in (payload.get("occasion") or []):
        total += weights.context_match
        reasons.append(
            Reason(
                source="context", delta=weights.context_match, text=f"{occasion}에 어울림"
            )
        )
    return total, reasons


def retrieve_outfits(
    request: RetrievalRequest,
    *,
    client=None,
    rules: BodyRules | None = None,
) -> list[OutfitCandidate]:
    """골든 코디 후보를 점수순으로 돌려준다.

    검색 방식은 입력에 따라 갈린다.
      - `image_vector`가 있으면 이미지 벡터 유사도 (비슷한 코디 찾기)
      - `query_text`가 있으면 텍스트 벡터 유사도 — 다만 질의 임베딩은 호출부가
        만들어 넣어야 한다 (이 모듈은 모델을 로드하지 않는다)
      - 둘 다 없으면 필터만으로 훑는다 (추구미 기반 추천의 기본 경로)
    """
    client = client or get_client()
    rules = rules or load_body_rules()
    profile = request.body or BodyProfile()
    weights = rules.weights

    search_filter = build_filter(request, rules=rules)
    fetch = max(request.limit * _OVERFETCH, request.limit)

    excluded: set[str] = set()
    if request.hard_filter and not profile.is_empty:
        excluded = _hard_excluded_outfits(client, rules, profile, fetch * 4)

    records = _fetch(client, request, search_filter, fetch)

    axis = rules.for_profile(profile)
    preferred = (
        vocabulary.translate((request.pursuit or {}).get("preferred")).tags
        if request.pursuit
        else {}
    )
    avoided = (
        vocabulary.translate((request.pursuit or {}).get("avoided")).tags
        if request.pursuit
        else {}
    )

    season = _season_from_weather(request.weather)
    weather_rules = load_weather_rules()
    band = weather_rules.band_for(celsius_of(request.weather))

    candidates: list[OutfitCandidate] = []
    for point_id, similarity, payload in records:
        if point_id in excluded:
            continue
        delta, reasons = _score_items(
            list(payload.get("items", [])),
            rules_prefer=axis.prefer,
            rules_avoid=axis.avoid,
            preferred_tags=preferred,
            avoided_tags=avoided,
            weights=weights,
        )
        context_delta, context_reasons = _score_context(
            payload, season=season, occasion=request.occasion, weights=weights
        )
        delta += context_delta
        reasons.extend(context_reasons)

        # 기온은 계절 태그와 달리 아이템 구성만으로 판단된다. 골든셋에 계절
        # 태그가 없어도 "27도에 아우터"는 여기서 걸린다.
        weather_delta, weather_reasons = _score_weather(
            list(payload.get("items", [])), band, weather_rules.weights
        )
        delta += weather_delta
        reasons.extend(weather_reasons)
        # 유사도(0~1)를 100점 척도로 올려 규칙 가감점과 같은 단위에 둔다.
        base = similarity * 100
        candidates.append(
            OutfitCandidate(
                point_id=point_id,
                golden_id=str(payload.get("golden_id", "")),
                score=round(base + delta, 2),
                similarity=round(similarity, 4),
                reasons=tuple(reasons),
                payload=payload,
            )
        )

    if not candidates:
        # 왜 0건인지 남긴다. 필터가 문제인지 적재가 문제인지 로그만 보고
        # 갈릴 수 있어야 한다 — 사용자에게는 둘 다 똑같이 "추천 없음"이다.
        logger.warning(
            "골든 코디 후보 0건: 조회 %d건 / 하드제외 %d건 / 성별=%s / 필터=%s",
            len(records),
            len(excluded),
            request.gender or "(미지정)",
            search_filter,
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[: request.limit]


def _fetch(
    client, request: RetrievalRequest, search_filter, fetch: int
) -> list[tuple[str, float, dict[str, Any]]]:
    if request.image_vector is not None:
        hits = client.search(
            collection_name=GOLDEN_OUTFIT_COLLECTION,
            query_vector=(IMAGE_VECTOR, request.image_vector),
            query_filter=search_filter,
            limit=fetch,
            with_payload=True,
        )
        return [(str(h.id), float(h.score), h.payload or {}) for h in hits]

    points, _ = client.scroll(
        collection_name=GOLDEN_OUTFIT_COLLECTION,
        scroll_filter=search_filter,
        with_payload=True,
        with_vectors=False,
        limit=fetch,
    )
    # 벡터 질의가 없으면 유사도가 없다. 사람 점수(human_score)가 있으면 그걸
    # 0~1로 정규화해 기준선으로 쓰고, 없으면 0으로 두어 규칙 점수만 남긴다.
    return [
        (
            str(point.id),
            float((point.payload or {}).get("human_score", 0.0)) / 100.0,
            point.payload or {},
        )
        for point in points
    ]


def retrieve_substitutes(
    item: dict[str, Any],
    *,
    collection: str,
    client=None,
    user_id: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """골든 코디의 아이템 하나를 교체할 후보를 찾는다.

    `collection`은 "wardrobe"(옷장) 또는 "products"(상품). 세 컬렉션이 같은 태그
    인덱스를 쓰도록 맞춰 두었기 때문에 같은 필터 언어가 그대로 통한다.

    같은 대분류·레이어 역할로 좁히는 이유는, 상의를 하의로 바꾸는 제안이 나오면
    코디가 성립하지 않기 때문이다.
    """
    client = client or get_client()
    must: list[qm.Condition] = []
    for field_name in ("category_large", "layer_role"):
        if value := item.get(field_name):
            must.append(
                qm.FieldCondition(key=field_name, match=qm.MatchValue(value=value))
            )
    if collection == "wardrobe" and user_id:
        must.append(
            qm.FieldCondition(key="user_id", match=qm.MatchValue(value=str(user_id)))
        )

    vector = item.get("image_vector")
    if vector is None:
        # 벡터 없이 태그만으로 좁힌다. 정확도는 떨어지지만 결과가 비지는 않는다.
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=qm.Filter(must=must) if must else None,
            with_payload=True,
            with_vectors=False,
            limit=limit,
        )
        return [{"id": str(p.id), "score": None, **(p.payload or {})} for p in points]

    hits = client.search(
        collection_name=collection,
        query_vector=(IMAGE_VECTOR, vector),
        query_filter=qm.Filter(must=must) if must else None,
        limit=limit,
        with_payload=True,
    )
    return [{"id": str(h.id), "score": float(h.score), **(h.payload or {})} for h in hits]
