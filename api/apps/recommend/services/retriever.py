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
import time
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from django.conf import settings
from qdrant_client import models as qm

from apps.recommend.services import vocabulary
from apps.recommend.services.body_profile import BodyProfile
from apps.recommend.services.gender import (
    GENDER_TO_PRESENTATION as GENDER_TO_PRESENTATION,
)
from apps.recommend.services.gender import (
    PRESENTATION_UNISEX as PRESENTATION_UNISEX,
)
from apps.recommend.services.gender import (
    allowed_presentation_groups,
    conflicting_item,
    normalize_gender,
)
from apps.recommend.services.qdrant import (
    GOLDEN_ITEM_COLLECTION,
    GOLDEN_OUTFIT_COLLECTION,
    IMAGE_VECTOR,
    TEXT_VECTOR,
    get_client,
)
from apps.recommend.services.style_rules import (
    BodyRules,
    Rule,
    WeatherBand,
    load_body_rules,
    load_weather_rules,
)
from apps.recommend.services.text_embedding import (
    TextEmbeddingClient,
    get_text_embedding_client,
)

logger = logging.getLogger(__name__)

#: 코디 payload에 인덱스가 있어 Qdrant 필터로 바로 쓸 수 있는 축.
#: `fit`·`length`·`sleeve`는 코디 단계에 인덱스가 없다 — 아이템 컬렉션을 거친다.
OUTFIT_FILTER_FIELDS = frozenset(
    {"style", "season", "occasion", "item_layer_roles", "item_categories"}
)

#: 성별 표현 그룹 상수와 표기 해석은 services/gender.py가 단일 출처다. 예전엔
#: 여기서 직접 들고 있었는데, 해석이 세 파일에 흩어진 탓에 그 중 한 곳에서 빈
#: 문자열이 "None"으로 굳어 성별 필터가 통째로 사라진 적이 있다 (gender.py 참고).
#: 재노출은 기존 import 경로를 쓰는 호출부·테스트를 위한 것이다.

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
    season: str = ""
    #: 자유 문구 (예: "비 오는 날 출근룩"). 있으면 텍스트 벡터로 검색한다.
    query_text: str = ""
    text_vector: list[float] | None = None
    #: 코디를 찍은 이미지 벡터로 검색할 때 (옷장 기반 추천의 '비슷한 코디')
    image_vector: list[float] | None = None
    presentation_groups: tuple[str, ...] = ()
    dataset_version: str = ""
    dataset_statuses: tuple[str, ...] = ()
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


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[OutfitCandidate, ...]
    search_mode: str
    embedding_model: str = ""
    embedding_version: str = ""


_PRESENTATION_GROUP_ALIASES = {
    "male": "men",
    "man": "men",
    "men": "men",
    "masculine": "men",
    "남성": "men",
    "female": "women",
    "woman": "women",
    "women": "women",
    "feminine": "women",
    "여성": "women",
    "unisex": "unisex",
    "유니섹스": "unisex",
}


def normalize_presentation_groups(values: Iterable[str]) -> tuple[str, ...]:
    """외부 표기를 골든셋의 men/women/unisex 값으로 통일한다."""
    normalized = {
        mapped
        for value in values
        if (mapped := _PRESENTATION_GROUP_ALIASES.get(str(value).strip().casefold()))
    }
    return tuple(sorted(normalized))


def _effective_presentation_groups(request: RetrievalRequest) -> tuple[str, ...]:
    """프로필 성별 안전 필터와 대화의 명시 조건을 함께 적용한다."""
    allowed = set(allowed_presentation_groups(request.gender))
    requested = set(normalize_presentation_groups(request.presentation_groups))
    if allowed and requested:
        intersection = allowed & requested
        # 서로 충돌할 때 필터를 빼면 반대 성별 코디가 전부 통과한다.
        return tuple(sorted(intersection or {"__no_matching_presentation_group__"}))
    return tuple(sorted(allowed or requested))


def _any_of(field_name: str, values: Iterable[str]) -> qm.FieldCondition:
    return qm.FieldCondition(key=field_name, match=qm.MatchAny(any=sorted(values)))


def _status_condition(statuses: Iterable[str]) -> qm.Filter:
    variants = {
        variant
        for value in statuses
        for variant in (
            str(value).strip(),
            str(value).strip().upper(),
            str(value).strip().lower(),
        )
        if variant
    }
    return qm.Filter(
        should=[
            _any_of("dataset_status", variants),
            _any_of("status", variants),
        ]
    )


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

    if request.dataset_version:
        must.append(
            qm.FieldCondition(
                key="dataset_version",
                match=qm.MatchValue(value=request.dataset_version),
            )
        )
    if request.dataset_statuses:
        must.append(_status_condition(request.dataset_statuses))

    # 성별은 하드 필터다. 남성 사용자에게 여성 코디를 "순위만 낮춰" 보여주는 건
    # 추천이 아니라 오작동으로 읽힌다. 계절과 달리 감점으로 둘 수 없는 축이다.
    #
    # 라벨이 없는 코디(presentation_group="")는 여기서 함께 빠진다. 미분류를
    # unisex로 취급하면 여성 코디가 그대로 남성에게 나가므로, 조용히 통과시키는
    # 대신 빠지게 두고 EMPTY 사유에 그 사실을 적는다.
    if groups := _effective_presentation_groups(request):
        must.append(_any_of("presentation_group", groups))

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


#: 코디 payload의 아이템 요약에 없는 태그. 체형 규칙이 정확히 이 축으로 조건을
#: 건다 (body_fit_rules.json의 fit·length·pattern).
#:
#: sync_qdrant의 ITEM_SUMMARY_FIELDS는 화면 구성에 필요한 최소치만 담는다 —
#: item_key·item_name·category_large·category_small·layer_role·color·s3_key.
#: 그래서 `Rule.matches()`가 item.get("fit") == None을 보고 전부 False를
#: 돌려주었고, **모든 체형에서 규칙 점수가 0**이었다. 실루엣이 뭐든 순위가
#: 같으니 체형을 바꿔도 같은 룩이 나온다.
#:
#: 태그 자체는 아이템 컬렉션에 이미 있으므로 조회 시점에 합친다. 재적재로
#: 코디 payload를 늘리면 이 왕복은 사라지고, 그때는 여기가 그냥 무해해진다
#: (이미 값이 있으면 덮어쓰지 않는다).
JOINED_ITEM_TAG_FIELDS = (
    "fit",
    "length",
    "pattern",
    "material",
    "sleeve",
    "style",
    "season",
)

#: point_id -> 태그. 프로세스 수명 동안만 산다.
_ITEM_TAG_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_ITEM_TAG_CACHE_MAX = 20000


def _cache_get(point_id: str, now: float) -> dict[str, Any] | None:
    ttl = settings.RETRIEVER_ITEM_TAG_CACHE_SECONDS
    if ttl <= 0:
        return None
    entry = _ITEM_TAG_CACHE.get(point_id)
    if entry is None or now - entry[0] > ttl:
        return None
    return entry[1]


def _cache_put(point_id: str, tags: dict[str, Any], now: float) -> None:
    if settings.RETRIEVER_ITEM_TAG_CACHE_SECONDS <= 0:
        return
    if len(_ITEM_TAG_CACHE) >= _ITEM_TAG_CACHE_MAX:
        # 정교한 축출은 필요 없다. 골든셋 크기를 넘으면 그냥 비운다.
        _ITEM_TAG_CACHE.clear()
    _ITEM_TAG_CACHE[point_id] = (now, tags)


def clear_item_tag_cache() -> None:
    """테스트와 재적재 직후에 쓴다."""
    _ITEM_TAG_CACHE.clear()


def _fetch_item_tags(client, point_ids: list[str]) -> dict[str, dict[str, Any]]:
    """아이템 포인트에서 태그만 가져온다. 캐시에 있는 건 건너뛴다."""
    now = time.monotonic()
    found: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for point_id in point_ids:
        cached = _cache_get(point_id, now)
        if cached is None:
            missing.append(point_id)
        else:
            found[point_id] = cached

    batch = max(1, settings.RETRIEVER_ITEM_TAG_BATCH)
    for start in range(0, len(missing), batch):
        chunk = missing[start : start + batch]
        try:
            points = client.retrieve(
                collection_name=GOLDEN_ITEM_COLLECTION,
                ids=chunk,
                with_payload=list(JOINED_ITEM_TAG_FIELDS),
                with_vectors=False,
            )
        except Exception:  # noqa: BLE001 — 태그를 못 붙여도 추천은 나가야 한다
            logger.warning(
                "아이템 태그 조회 실패 (%d건). 체형 규칙이 이번 요청에서는 "
                "적용되지 않습니다.", len(chunk), exc_info=True,
            )
            continue
        for point in points:
            tags = {
                field: value
                for field, value in (point.payload or {}).items()
                if field in JOINED_ITEM_TAG_FIELDS and value not in (None, "", [])
            }
            found[str(point.id)] = tags
            _cache_put(str(point.id), tags, now)

    return found


def attach_item_tags(client, records: list[tuple[str, float, dict[str, Any]]]) -> int:
    """코디 payload의 아이템 요약에 핏·기장·패턴 태그를 채워 넣는다.

    Returns: 태그를 붙인 아이템 수 (진단용).

    payload를 제자리에서 고친다. 이 dict는 방금 Qdrant에서 받아온 사본이고
    호출부(`_build_result`)도 같은 값을 쓰므로, 복사본을 따로 두면 화면과
    점수가 서로 다른 아이템을 보게 된다.
    """
    if not settings.RETRIEVER_ITEM_TAG_JOIN:
        return 0

    wanted: list[str] = []
    for _point_id, _similarity, payload in records:
        for item in payload.get("items") or []:
            point_id = str(item.get("point_id") or "")
            # 이미 태그가 있으면(재적재 이후) 굳이 조회하지 않는다.
            if point_id and not any(item.get(f) for f in JOINED_ITEM_TAG_FIELDS):
                wanted.append(point_id)
    if not wanted:
        return 0

    tags_by_point = _fetch_item_tags(client, sorted(set(wanted)))
    if not tags_by_point:
        return 0

    attached = 0
    for _point_id, _similarity, payload in records:
        for item in payload.get("items") or []:
            tags = tags_by_point.get(str(item.get("point_id") or ""))
            if not tags:
                continue
            for tag_field, value in tags.items():
                # 코디 payload의 값이 우선이다. 재적재로 값이 생기면 그쪽이
                # 그 시점의 진실이다.
                item.setdefault(tag_field, value)
            attached += 1
    return attached


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


def _tag_values(item: dict[str, Any], field: str) -> set[str]:
    """아이템 태그 하나를 **항상 집합으로** 읽는다.

    같은 축이라도 값이 하나일 수도(fit="오버핏") 여럿일 수도(style=["미니멀",
    "캐주얼"]) 있다. 아이템 컬렉션의 style·season이 리스트라, 태그 조인을
    붙인 뒤 `value in labels`가 리스트를 집합에 넣으려다 죽었다:

        TypeError: unhashable type: 'list'

    Rule.matches()는 이미 리스트를 다루고 있었는데 취향 매칭만 스칼라를
    가정하고 있었다. 두 곳이 같은 방식으로 읽도록 여기서 통일한다.
    """
    value = item.get(field)
    if isinstance(value, (list, tuple, set)):
        return {v for v in value if isinstance(v, str) and v}
    return {value} if isinstance(value, str) and value else set()


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
        """같은 근거는 코디당 한 번만 센다.

        예전에는 점수만 아이템마다 누적하고 이유는 한 번만 남겼다. 그래서
        상의가 셋인 코디는 같은 규칙으로 +45를 받는데 설명에는 +15 한 줄만
        보였다 — 점수와 설명이 서로 다른 말을 했다. 게다가 순위가 '규칙에
        얼마나 맞는가'가 아니라 '아이템이 몇 개인가'로 정해진다.
        """
        nonlocal total
        if text in seen:
            return
        seen.add(text)
        total += delta
        reasons.append(Reason(source=source, delta=delta, text=text))

    for item in items:
        for tag_field, labels in avoided_tags.items():
            for value in sorted(labels & _tag_values(item, tag_field)):
                add(
                    weights.preference_avoid,
                    "preference",
                    f"기피 항목 '{value}'이(가) 포함됨",
                )
        for tag_field, labels in preferred_tags.items():
            for value in sorted(labels & _tag_values(item, tag_field)):
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
        """_score_items와 같은 규칙 — 같은 근거는 코디당 한 번만."""
        nonlocal total
        if text in seen:
            return
        seen.add(text)
        total += delta
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

    # 체형 규칙은 fit·length·pattern으로 조건을 거는데 코디 payload의 아이템
    # 요약에는 그 축이 없다. 붙이지 않으면 모든 체형에서 규칙 점수가 0이 되어
    # 순위가 똑같아진다 — 체형을 바꿔도 같은 룩이 나오던 가장 큰 원인이다.
    attached = attach_item_tags(client, records)
    if records and not attached and settings.RETRIEVER_ITEM_TAG_JOIN:
        logger.info(
            "아이템 태그를 하나도 붙이지 못했습니다 (코디 %d건). 이미 payload에 "
            "있거나(재적재 완료) 아이템 컬렉션이 비어 있습니다.", len(records),
        )

    # 성별은 Qdrant 필터로도 걸지만, 파이썬에서 **한 번 더** 검사한다. 중복이
    # 아니라 다른 실패에 대비한 것이다: presentation_group 인덱스가 없거나,
    # 재적재로 payload 키가 빠졌거나, 오래된 이미지가 필터 없는 코드를 돌고
    # 있으면 Qdrant 쪽 must는 조용히 무력해진다. 그때도 남성 사용자에게 여성
    # 코디가 나가서는 안 된다. 통과하지 못한 건수는 로그로 드러낸다.
    allowed_groups = _effective_presentation_groups(request)
    blocked_by_gender = 0
    blocked_by_item = 0

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

    season = request.season.strip() or _season_from_weather(request.weather)
    weather_rules = load_weather_rules()
    band = weather_rules.band_for(celsius_of(request.weather))

    candidates: list[OutfitCandidate] = []
    for point_id, similarity, payload in records:
        if point_id in excluded:
            continue
        if allowed_groups and str(payload.get("presentation_group") or "") not in allowed_groups:
            blocked_by_gender += 1
            continue

        # 라벨을 통과했어도 **옷 자체**를 한 번 더 본다.
        #
        # presentation_group은 LLM이 사진을 보고 붙인 값이라 틀릴 수 있고,
        # 특히 "unisex"는 애매한 코디의 도피처가 된다. 실제로 여성 코디가
        # unisex로 태깅돼 남성 사용자에게 나갔다. 라벨만 믿는 한 반복된다.
        if conflict := conflicting_item(payload.get("items") or [], request.gender):
            blocked_by_item += 1
            logger.info(
                "성별 충돌로 제외: golden_id=%s group=%s 사유=%s",
                payload.get("golden_id"),
                payload.get("presentation_group") or "(미분류)",
                conflict,
            )
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

    if blocked_by_gender:
        # 검색 필터가 이미 걸렀어야 할 것이 여기까지 왔다는 뜻이다. 결과는
        # 안전하지만 원인(인덱스 누락·payload 누락·구버전 배포)은 남는다.
        logger.warning(
            "성별 필터를 통과한 뒤에도 %d건이 파이썬 단계에서 걸렸습니다 "
            "(성별=%s, 허용=%s). presentation_group 인덱스와 payload를 확인하세요.",
            blocked_by_gender,
            normalize_gender(request.gender) or "(미지정)",
            list(allowed_groups),
        )

    if blocked_by_item:
        # 라벨이 틀린 코디가 몇 건인지 남긴다. 이 수가 크면 태깅을 다시
        # 돌려야 한다는 뜻이다 — 매번 파이썬으로 걸러내는 건 임시방편이다.
        logger.warning(
            "presentation_group을 통과했지만 아이템이 성별과 충돌해 제외한 코디 "
            "%d건 (성별=%s). 태깅 정확도를 확인하세요.",
            blocked_by_item,
            normalize_gender(request.gender) or "(미지정)",
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

    # 동점일 때 무엇이 1등인지 못 박는다. 예전에는 파이썬의 안정 정렬 때문에
    # **스크롤 순서 1등이 그대로 1등**이었다. 유사도 기준선이 0인 지금(적재된
    # 코디에 human_score가 없다) 동점은 흔하다. 태그 신뢰도를 2순위로 두고,
    # 그것도 같으면 golden_id로 갈라 조회 순서와 무관하게 재현되게 한다.
    candidates.sort(
        key=lambda c: (
            -c.score,
            -float(c.payload.get("tag_confidence") or 0),
            c.golden_id,
        )
    )
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

    if request.text_vector is not None:
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=GOLDEN_OUTFIT_COLLECTION,
                query=request.text_vector,
                using=TEXT_VECTOR,
                query_filter=search_filter,
                limit=fetch,
                with_payload=True,
            )
            hits = response.points
        else:
            hits = client.search(
                collection_name=GOLDEN_OUTFIT_COLLECTION,
                query_vector=(TEXT_VECTOR, request.text_vector),
                query_filter=search_filter,
                limit=fetch,
                with_payload=True,
            )
        return [(str(h.id), float(h.score), h.payload or {}) for h in hits]

    # 벡터 질의가 없으면 scroll이다. scroll은 관련도가 아니라 **포인트 ID
    # 순서**로 돌려준다. 예전에는 여기서 앞 20건만 끊었는데, 그러면 골든셋이
    # 몇 건이든 언제나 같은 20건만 후보가 된다 — 체형·취향을 바꿔도 결과가
    # 안 변하던 원인 중 하나다. 이제 필터를 통과한 코디를 전부 훑는다.
    #
    # `fetch`는 무시한다. 그 값은 "상위 N의 재정렬 여유"를 뜻하는데, 순서가
    # 없는 스크롤에는 상위라는 개념이 없다.
    points = _scroll_all(client, search_filter)
    # 사람 점수(human_score)가 있으면 0~1로 정규화해 기준선으로 쓰고, 없으면
    # 0으로 두어 규칙 점수만 남긴다. sync_qdrant로 적재한 코디에는 이 값이
    # 없으므로 사실상 규칙 점수가 순위를 정한다.
    return [
        (
            str(point.id),
            float((point.payload or {}).get("human_score", 0.0)) / 100.0,
            point.payload or {},
        )
        for point in points
    ]


def _scroll_all(client, search_filter) -> list[Any]:
    """필터를 통과한 코디를 페이지네이션으로 전부 모은다.

    상한(RETRIEVER_SCROLL_CAP)에 걸리면 **경고를 남긴다.** 조용히 잘리면
    "골든셋을 다 봤다"고 오해하게 되고, 그 오해가 이번 버그를 오래 숨겼다.
    """
    cap = max(1, settings.RETRIEVER_SCROLL_CAP)
    page = max(1, settings.RETRIEVER_SCROLL_PAGE)

    collected: list[Any] = []
    offset = None
    while len(collected) < cap:
        points, offset = client.scroll(
            collection_name=GOLDEN_OUTFIT_COLLECTION,
            scroll_filter=search_filter,
            with_payload=True,
            with_vectors=False,
            limit=min(page, cap - len(collected)),
            offset=offset,
        )
        collected.extend(points)
        if offset is None or not points:
            break

    if len(collected) >= cap and offset is not None:
        logger.warning(
            "코디 후보를 %d건에서 잘랐습니다 (RETRIEVER_SCROLL_CAP). 남은 코디는 "
            "이번 추천에서 아예 고려되지 않습니다.", cap,
        )
    return collected


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


class GoldenOutfitRetriever:
    """main 리트리버의 성별·체형 검증을 유지하는 채팅용 인터페이스."""

    def __init__(
        self,
        *,
        client=None,
        embedding_client: TextEmbeddingClient | None = None,
        body_rules: BodyRules | None = None,
    ) -> None:
        self.client = client or get_client()
        self.embedding_client = embedding_client
        self.body_rules = body_rules

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        if not 1 <= request.limit <= 50:
            raise ValueError("limit은 1 이상 50 이하여야 합니다.")
        if request.image_vector is not None and request.query_text.strip():
            raise ValueError("image_vector와 query_text는 동시에 사용할 수 없습니다.")

        embedding_model = ""
        embedding_version = ""
        resolved = request
        if request.image_vector is not None:
            search_mode = "image"
        elif request.query_text.strip():
            search_mode = "text"
            embedding = (self.embedding_client or get_text_embedding_client()).embed(
                request.query_text
            )
            embedding_model = embedding.model
            embedding_version = embedding.version
            resolved = replace(request, text_vector=list(embedding.vector))
        else:
            search_mode = "filter"

        candidates = retrieve_outfits(
            resolved,
            client=self.client,
            rules=self.body_rules,
        )
        return RetrievalResult(
            candidates=tuple(candidates),
            search_mode=search_mode,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )
