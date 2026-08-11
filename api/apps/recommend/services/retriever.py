"""골든 코디 템플릿 검색 계층.

이 모듈은 ``outfit_goldenset`` 후보 검색과 결정적 점수화만 담당한다. LLM은
호출하지 않으며, 아이템 교체 검색은 다음 단계의 ItemCandidateRetriever 책임이다.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from qdrant_client import models as qm

from apps.recommend.services import vocabulary
from apps.recommend.services.body_profile import BodyProfile
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
    WeatherRules,
    load_body_rules,
    load_weather_rules,
)
from apps.recommend.services.text_embedding import (
    TextEmbeddingClient,
    get_text_embedding_client,
)

logger = logging.getLogger(__name__)

OUTFIT_FILTER_FIELDS = frozenset({"style", "season", "occasion"})
_OVERFETCH = 4


@dataclass(frozen=True)
class RetrievalRequest:
    body: BodyProfile | None = None
    pursuit: dict[str, dict[str, list[str]]] | None = None
    weather: dict[str, Any] | None = None
    occasion: str = ""
    season: str = ""
    query_text: str = ""
    image_vector: list[float] | None = None
    presentation_groups: tuple[str, ...] = ()
    dataset_version: str = ""
    dataset_statuses: tuple[str, ...] = ()
    limit: int = 10
    hard_filter: bool = True
    exposable_only: bool = False


@dataclass(frozen=True)
class Reason:
    source: str
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
        items = self.payload.get("items")
        return list(items) if isinstance(items, list) else []


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[OutfitCandidate, ...]
    search_mode: str
    embedding_model: str = ""
    embedding_version: str = ""


def _any_of(field_name: str, values: Iterable[str]) -> qm.FieldCondition:
    return qm.FieldCondition(
        key=field_name,
        match=qm.MatchAny(any=sorted(set(values))),
    )


_PRESENTATION_GROUP_ALIASES = {
    "male": "man",
    "man": "man",
    "masculine": "man",
    "남성": "man",
    "female": "woman",
    "woman": "woman",
    "feminine": "woman",
    "여성": "woman",
    "unisex": "unisex",
    "유니섹스": "unisex",
}


def normalize_presentation_groups(values: Iterable[str]) -> tuple[str, ...]:
    """프로필·대화의 성별 표현을 골든셋 metadata 값으로 통일한다."""
    normalized = {
        mapped
        for value in values
        if (mapped := _PRESENTATION_GROUP_ALIASES.get(str(value).strip().casefold()))
    }
    if normalized & {"man", "woman"}:
        normalized.add("unisex")
    return tuple(sorted(normalized))


def _status_condition(statuses: Iterable[str]) -> qm.Filter:
    values = tuple(
        sorted(
            {
                variant
                for value in statuses
                for variant in (
                    str(value).strip(),
                    str(value).strip().upper(),
                    str(value).strip().lower(),
                )
                if variant
            }
        )
    )
    return qm.Filter(
        should=[
            _any_of("dataset_status", values),
            _any_of("status", values),
        ]
    )


def build_filter(request: RetrievalRequest) -> qm.Filter | None:
    """명시적 필수 조건과 기피 조건만 Qdrant 하드 필터로 만든다."""
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
    presentation_groups = normalize_presentation_groups(request.presentation_groups)
    if presentation_groups:
        must.append(_any_of("presentation_group", presentation_groups))

    if request.pursuit and request.hard_filter:
        avoided = vocabulary.translate(request.pursuit.get("avoided"))
        for field_name, values in avoided.tags.items():
            if field_name in OUTFIT_FILTER_FIELDS and values:
                must_not.append(_any_of(field_name, values))

    if not must and not must_not:
        return None
    return qm.Filter(must=must or None, must_not=must_not or None)


def _normalize(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        text = value.strip()
        return {text, text.lower()} if text else set()
    if isinstance(value, (list, tuple, set)):
        result: set[str] = set()
        for item in value:
            result.update(_normalize(item))
        return result
    return {str(value)}


def _payload_values(payload: dict[str, Any], field_name: str) -> set[str]:
    values = _normalize(payload.get(field_name))
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        values.update(_normalize(metadata.get(field_name)))
    look_tags = payload.get("look_tags")
    if isinstance(look_tags, dict):
        values.update(_normalize(look_tags.get(field_name)))
    elif field_name == "style":
        values.update(_normalize(look_tags))
    return values


def _item_values(payload: dict[str, Any], field_name: str) -> set[str]:
    values: set[str] = set()
    items = payload.get("items")
    if not isinstance(items, list):
        return values
    for item in items:
        if isinstance(item, dict):
            values.update(_normalize(item.get(field_name)))
    return values


def _matches(payload: dict[str, Any], field_name: str, expected: set[str]) -> set[str]:
    actual = _payload_values(payload, field_name) | _item_values(payload, field_name)
    return actual & expected


def _season_from_weather(weather: dict[str, Any] | None) -> str:
    temperature = celsius_of(weather)
    if temperature is None:
        return ""
    if temperature >= 23:
        return "여름"
    if temperature >= 17:
        return "간절기"
    if temperature >= 9:
        return "가을"
    return "겨울"


def celsius_of(weather: dict[str, Any] | None) -> float | None:
    if not weather:
        return None
    try:
        return float(weather.get("temperature"))
    except (TypeError, ValueError):
        return None


def _hard_excluded_by_preferences(
    payload: dict[str, Any], avoided_tags: dict[str, set[str]]
) -> bool:
    for field_name, expected in avoided_tags.items():
        if _matches(payload, field_name, expected):
            return True
    return False


def _hard_excluded_by_body(
    items: list[dict[str, Any]], rules: tuple[Rule, ...]
) -> bool:
    hard_rules = tuple(rule for rule in rules if rule.hard)
    return any(rule.matches(item) for item in items for rule in hard_rules)


def _score_items(
    items: list[dict[str, Any]],
    *,
    rules_prefer: tuple[Rule, ...],
    rules_avoid: tuple[Rule, ...],
    preferred_tags: dict[str, set[str]],
    avoided_tags: dict[str, set[str]],
    weights,
) -> tuple[float, list[Reason]]:
    total = 0.0
    reasons: list[Reason] = []
    seen: set[tuple[str, str]] = set()

    def add(amount: float, source: str, text: str) -> None:
        nonlocal total
        total += amount
        key = source, text
        if key not in seen:
            seen.add(key)
            reasons.append(Reason(source=source, delta=amount, text=text))

    for item in items:
        for field_name, expected in avoided_tags.items():
            matched = _payload_values(item, field_name) & expected
            for value in sorted(matched):
                add(
                    weights.preference_avoid,
                    "preference",
                    f"기피 {field_name} '{value}' 포함",
                )
        for field_name, expected in preferred_tags.items():
            matched = _payload_values(item, field_name) & expected
            for value in sorted(matched):
                add(
                    weights.preference_match,
                    "preference",
                    f"선호 {field_name} '{value}' 일치",
                )
        for rule in rules_avoid:
            if rule.matches(item):
                add(weights.rule_avoid, "rule", rule.reason)
        for rule in rules_prefer:
            if rule.matches(item):
                add(weights.rule_prefer, "rule", rule.reason)
    return total, reasons


def _score_context(
    payload: dict[str, Any],
    *,
    season: str,
    occasion: str,
    weights,
) -> tuple[float, list[Reason]]:
    total = 0.0
    reasons: list[Reason] = []
    if season and season in _payload_values(payload, "season"):
        total += weights.context_match
        reasons.append(
            Reason("context", weights.context_match, f"{season} 조건과 일치")
        )
    normalized_occasion = occasion.strip()
    if normalized_occasion and normalized_occasion in _payload_values(
        payload, "occasion"
    ):
        total += weights.context_match
        reasons.append(
            Reason(
                "context",
                weights.context_match,
                f"{normalized_occasion} 상황과 일치",
            )
        )
    return total, reasons


def _score_weather(
    items: list[dict[str, Any]],
    band: WeatherBand | None,
    weights,
) -> tuple[float, list[Reason]]:
    if band is None:
        return 0.0, []
    total = 0.0
    reasons: list[Reason] = []
    seen: set[str] = set()

    def add(amount: float, text: str) -> None:
        nonlocal total
        total += amount
        if text not in seen:
            seen.add(text)
            reasons.append(Reason("weather", amount, text))

    for item in items:
        for rule in band.discourage:
            if rule.matches(item):
                add(weights.discourage, rule.reason)
        for rule in band.encourage:
            if rule.matches(item):
                add(weights.encourage, rule.reason)
    return total, reasons


class GoldenOutfitRetriever:
    def __init__(
        self,
        *,
        client=None,
        embedding_client: TextEmbeddingClient | None = None,
        body_rules: BodyRules | None = None,
        weather_rules: WeatherRules | None = None,
    ) -> None:
        self.client = client or get_client()
        self.embedding_client = embedding_client
        self.body_rules = body_rules or load_body_rules()
        self.weather_rules = weather_rules or load_weather_rules()

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        if not 1 <= request.limit <= 50:
            raise ValueError("limit은 1 이상 50 이하여야 합니다.")
        if request.image_vector is not None and request.query_text.strip():
            raise ValueError("image_vector와 query_text는 동시에 사용할 수 없습니다.")

        search_filter = build_filter(request)
        fetch = max(request.limit * _OVERFETCH, request.limit)
        embedding_model = ""
        embedding_version = ""

        if request.image_vector is not None:
            search_mode = "image"
            records = self._search(
                vector=request.image_vector,
                vector_name=IMAGE_VECTOR,
                search_filter=search_filter,
                limit=fetch,
            )
        elif request.query_text.strip():
            search_mode = "text"
            embedding = (self.embedding_client or get_text_embedding_client()).embed(
                request.query_text
            )
            embedding_model = embedding.model
            embedding_version = embedding.version
            records = self._search(
                vector=list(embedding.vector),
                vector_name=TEXT_VECTOR,
                search_filter=search_filter,
                limit=fetch,
            )
        else:
            search_mode = "filter"
            records = self._scroll(search_filter=search_filter, limit=fetch)

        records = self._hydrate_items(records)

        preferred = vocabulary.translate((request.pursuit or {}).get("preferred"))
        avoided = vocabulary.translate((request.pursuit or {}).get("avoided"))
        if preferred.unmapped or avoided.unmapped:
            logger.info(
                "골든 코디 검색에 반영하지 못한 추구미 항목: %s",
                sorted(set(preferred.unmapped) | set(avoided.unmapped)),
            )

        profile = request.body or BodyProfile()
        axis_rules = self.body_rules.for_profile(profile)
        season = request.season.strip() or _season_from_weather(request.weather)
        weather_band = self.weather_rules.band_for(celsius_of(request.weather))
        candidates: list[OutfitCandidate] = []
        for point_id, similarity, payload in records:
            items = [
                item for item in payload.get("items", []) if isinstance(item, dict)
            ]
            if request.hard_filter and _hard_excluded_by_preferences(
                payload, avoided.tags
            ):
                continue
            if request.hard_filter and _hard_excluded_by_body(items, axis_rules.avoid):
                continue

            scoring_items = [payload, *items]
            delta, reasons = _score_items(
                scoring_items,
                rules_prefer=axis_rules.prefer,
                rules_avoid=axis_rules.avoid,
                preferred_tags=preferred.tags,
                avoided_tags={} if request.hard_filter else avoided.tags,
                weights=self.body_rules.weights,
            )
            context_delta, context_reasons = _score_context(
                payload,
                season=season,
                occasion=request.occasion,
                weights=self.body_rules.weights,
            )
            weather_delta, weather_reasons = _score_weather(
                items,
                weather_band,
                self.weather_rules.weights,
            )
            delta += context_delta + weather_delta
            reasons.extend(context_reasons)
            reasons.extend(weather_reasons)
            candidates.append(
                OutfitCandidate(
                    point_id=point_id,
                    golden_id=str(payload.get("golden_id") or ""),
                    score=round(similarity * 100 + delta, 2),
                    similarity=round(similarity, 4),
                    reasons=tuple(reasons),
                    payload=payload,
                )
            )

        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        if not candidates:
            logger.warning(
                "골든 코디 후보 0건: mode=%s, 조회=%d, filter=%s",
                search_mode,
                len(records),
                search_filter,
            )
        return RetrievalResult(
            candidates=tuple(candidates[: request.limit]),
            search_mode=search_mode,
            embedding_model=embedding_model,
            embedding_version=embedding_version,
        )

    @staticmethod
    def _item_point_ids(payload: dict[str, Any]) -> tuple[str, ...]:
        values: list[str] = []
        raw_ids = payload.get("item_point_ids")
        if isinstance(raw_ids, (list, tuple)):
            values.extend(str(value) for value in raw_ids if value not in (None, ""))
        raw_items = payload.get("items")
        if isinstance(raw_items, list):
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                value = item.get("item_point_id") or item.get("point_id")
                if value not in (None, ""):
                    values.append(str(value))
        return tuple(dict.fromkeys(values))

    def _hydrate_items(
        self,
        records: list[tuple[str, float, dict[str, Any]]],
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """코디의 item_point_ids를 한꺼번에 조회해 상세 태그를 보충한다."""
        if not hasattr(self.client, "retrieve"):
            return records

        point_ids = tuple(
            dict.fromkeys(
                point_id
                for _, _, payload in records
                for point_id in self._item_point_ids(payload)
            )
        )
        if not point_ids:
            return records

        loaded: dict[str, dict[str, Any]] = {}
        for start in range(0, len(point_ids), 256):
            points = self.client.retrieve(
                collection_name=GOLDEN_ITEM_COLLECTION,
                ids=list(point_ids[start : start + 256]),
                with_payload=True,
                with_vectors=False,
            )
            loaded.update((str(point.id), point.payload or {}) for point in points)

        hydrated = []
        for outfit_id, similarity, raw_payload in records:
            payload = dict(raw_payload)
            summaries: dict[str, dict[str, Any]] = {}
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                point_id = item.get("item_point_id") or item.get("point_id")
                if point_id not in (None, ""):
                    summaries[str(point_id)] = item

            items: list[dict[str, Any]] = []
            for point_id in self._item_point_ids(payload):
                summary = summaries.get(point_id, {})
                details = loaded.get(point_id, {})
                items.append({**summary, **details, "point_id": point_id})
            if items:
                payload["items"] = items
            hydrated.append((outfit_id, similarity, payload))
        return hydrated

    def _search(
        self,
        *,
        vector: list[float],
        vector_name: str,
        search_filter: qm.Filter | None,
        limit: int,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        collection_name = GOLDEN_OUTFIT_COLLECTION
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=collection_name,
                query=vector,
                using=vector_name,
                query_filter=search_filter,
                limit=limit,
                with_payload=True,
            )
            hits = response.points
        else:  # qdrant-client 구버전 호환
            hits = self.client.search(
                collection_name=collection_name,
                query_vector=(vector_name, vector),
                query_filter=search_filter,
                limit=limit,
                with_payload=True,
            )
        return [(str(hit.id), float(hit.score), hit.payload or {}) for hit in hits]

    def _scroll(
        self,
        *,
        search_filter: qm.Filter | None,
        limit: int,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        points, _ = self.client.scroll(
            collection_name=GOLDEN_OUTFIT_COLLECTION,
            scroll_filter=search_filter,
            with_payload=True,
            with_vectors=False,
            limit=limit,
        )
        return [
            (
                str(point.id),
                float((point.payload or {}).get("human_score") or 0.0) / 100.0,
                point.payload or {},
            )
            for point in points
        ]


def retrieve_outfits(
    request: RetrievalRequest,
    *,
    client=None,
    embedding_client: TextEmbeddingClient | None = None,
) -> list[OutfitCandidate]:
    """기존 golenset_new 호출 형태를 유지하는 편의 함수."""
    result = GoldenOutfitRetriever(
        client=client,
        embedding_client=embedding_client,
    ).retrieve(request)
    return list(result.candidates)
