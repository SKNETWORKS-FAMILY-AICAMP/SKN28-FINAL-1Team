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
from apps.recommend.services.qdrant import (
    GOLDEN_OUTFIT_COLLECTION,
    IMAGE_VECTOR,
    TEXT_VECTOR,
    get_client,
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
    pursuit: dict[str, dict[str, list[str]]] | None = None
    weather: dict[str, Any] | None = None
    occasion: str = ""
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
        must.append(_any_of("dataset_status", request.dataset_statuses))
    # presentation_group은 성별 대용 하드 필터가 아니다. 사용자가 명시적으로
    # 요청해 호출부가 값을 채운 경우에만 적용한다.
    if request.presentation_groups:
        must.append(_any_of("presentation_group", request.presentation_groups))

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
    if not weather:
        return ""
    try:
        temperature = float(weather.get("temperature"))
    except (TypeError, ValueError):
        return ""
    if temperature >= 23:
        return "여름"
    if temperature >= 17:
        return "간절기"
    if temperature >= 9:
        return "가을"
    return "겨울"


def _hard_excluded_by_items(
    payload: dict[str, Any], avoided_tags: dict[str, set[str]]
) -> bool:
    for field_name, expected in avoided_tags.items():
        if field_name not in OUTFIT_FILTER_FIELDS and _matches(
            payload, field_name, expected
        ):
            return True
    return False


def _score_candidate(
    payload: dict[str, Any],
    *,
    preferred_tags: dict[str, set[str]],
    avoided_tags: dict[str, set[str]],
    season: str,
    occasion: str,
    hard_filter: bool,
) -> tuple[float, list[Reason]]:
    delta = 0.0
    reasons: list[Reason] = []
    seen: set[tuple[str, str]] = set()

    def add(source: str, amount: float, text: str) -> None:
        nonlocal delta
        key = source, text
        if key in seen:
            return
        seen.add(key)
        delta += amount
        reasons.append(Reason(source=source, delta=amount, text=text))

    for field_name, expected in preferred_tags.items():
        for value in sorted(_matches(payload, field_name, expected)):
            add("preference", 8.0, f"선호 {field_name} '{value}' 일치")

    if not hard_filter:
        for field_name, expected in avoided_tags.items():
            for value in sorted(_matches(payload, field_name, expected)):
                add("preference", -20.0, f"기피 {field_name} '{value}' 포함")

    if season and season in _payload_values(payload, "season"):
        add("context", 6.0, f"현재 기온에 맞는 {season} 코디")
    normalized_occasion = occasion.strip()
    if normalized_occasion and normalized_occasion in _payload_values(
        payload, "occasion"
    ):
        add("context", 6.0, f"{normalized_occasion} 상황과 일치")
    return delta, reasons


class GoldenOutfitRetriever:
    def __init__(
        self,
        *,
        client=None,
        embedding_client: TextEmbeddingClient | None = None,
    ) -> None:
        self.client = client or get_client()
        self.embedding_client = embedding_client

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

        preferred = vocabulary.translate((request.pursuit or {}).get("preferred"))
        avoided = vocabulary.translate((request.pursuit or {}).get("avoided"))
        if preferred.unmapped or avoided.unmapped:
            logger.info(
                "골든 코디 검색에 반영하지 못한 추구미 항목: %s",
                sorted(set(preferred.unmapped) | set(avoided.unmapped)),
            )

        season = _season_from_weather(request.weather)
        candidates: list[OutfitCandidate] = []
        for point_id, similarity, payload in records:
            if request.hard_filter and _hard_excluded_by_items(payload, avoided.tags):
                continue
            delta, reasons = _score_candidate(
                payload,
                preferred_tags=preferred.tags,
                avoided_tags=avoided.tags,
                season=season,
                occasion=request.occasion,
                hard_filter=request.hard_filter,
            )
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
