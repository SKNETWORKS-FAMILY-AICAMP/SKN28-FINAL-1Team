"""골든 코디의 슬롯별 대체·보완 아이템 후보 검색.

완성된 조합을 만드는 책임은 OutfitComposer에 있다. 이 모듈은 골든 아이템 하나를
기준으로 옷장, 골든셋 아이템, 상품 컬렉션에서 같은 슬롯의 후보와 근거만 반환한다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from qdrant_client import models as qm

from apps.recommend.services.qdrant import (
    GOLDEN_ITEM_COLLECTION,
    IMAGE_VECTOR,
    TEXT_VECTOR,
    collection_spec,
    get_client,
    product_collection_names,
)


class ItemRetrievalError(RuntimeError):
    """아이템 후보 검색을 안전하게 수행할 수 없는 경우."""


class TemplateItemNotFound(ItemRetrievalError):
    """기준 골든 아이템이 존재하지 않는 경우."""


class ItemSource(StrEnum):
    WARDROBE = "WARDROBE"
    GOLDENSET_ITEM = "GOLDENSET_ITEM"
    PRODUCT = "PRODUCT"


@dataclass(frozen=True)
class ItemRetrievalRequest:
    template_item_point_id: str
    sources: tuple[ItemSource, ...] = (
        ItemSource.WARDROBE,
        ItemSource.GOLDENSET_ITEM,
        ItemSource.PRODUCT,
    )
    user_id: int | None = None
    allowed_wardrobe_item_ids: tuple[str, ...] | None = None
    max_price: int | None = None
    category_budgets: dict[str, int] = field(default_factory=dict)
    dataset_version: str = ""
    dataset_statuses: tuple[str, ...] = ()
    limit_per_source: int = 10
    #: 사용자가 명시적으로 기피한 태그 (Qdrant 필드명 -> 라벨).
    avoided_tags: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class TemplateItem:
    point_id: str
    payload: dict[str, Any]
    image_vector: tuple[float, ...] = ()
    text_vector: tuple[float, ...] = ()


@dataclass(frozen=True)
class ItemCandidate:
    point_id: str
    source_type: ItemSource
    source_id: str
    source_collection: str
    score: float | None
    reasons: tuple[str, ...]
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_owned(self) -> bool:
        return self.source_type is ItemSource.WARDROBE

    @property
    def is_purchasable(self) -> bool:
        return self.source_type is ItemSource.PRODUCT

    @property
    def price(self) -> int | None:
        raw = self.payload.get("price")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def image_ref(self) -> str:
        for key in ("s3_key", "image_s3_key", "image_url"):
            if value := self.payload.get(key):
                return str(value)
        return ""


@dataclass(frozen=True)
class ItemRetrievalResult:
    template: TemplateItem
    candidates: tuple[ItemCandidate, ...]
    vector_name: str
    pinned_candidate: ItemCandidate | None = None

    def for_source(self, source_type: ItemSource) -> tuple[ItemCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.source_type is source_type
        )


def _match_value(field_name: str, value: Any) -> qm.FieldCondition:
    return qm.FieldCondition(key=field_name, match=qm.MatchValue(value=value))


def _match_any(field_name: str, values: Iterable[str]) -> qm.FieldCondition:
    return qm.FieldCondition(
        key=field_name,
        match=qm.MatchAny(any=sorted(set(values))),
    )


def _vector(point: Any, name: str) -> tuple[float, ...]:
    vectors = getattr(point, "vector", None)
    if not isinstance(vectors, dict):
        return ()
    raw = vectors.get(name)
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(float(value) for value in raw)


def _avoided_conditions(request: ItemRetrievalRequest) -> list[qm.Condition]:
    """기피 태그를 가진 아이템은 후보 검색 단계에서 제외한다.

    예전에는 이 조건이 골든 코디 검색에만 걸리고 아이템 후보 검색에는 없었다.
    그래서 기피 태그를 가진 아이템이 후보로 올라와 조합까지 만들어진 뒤에야
    Validator가 EXPLICIT_TAG_EXCLUDED로 떨어뜨렸고, 후보를 다 소진할 때까지
    반복하다 추천 전체가 실패했다. 걸러야 할 것은 검색에서 거른다.
    """

    return [
        _match_any(tag_field, labels)
        for tag_field, labels in request.avoided_tags.items()
        if labels
    ]


def _single_value(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value.strip()
    return ""


class ItemCandidateRetriever:
    def __init__(self, *, client=None) -> None:
        self.client = client or get_client()

    def retrieve(self, request: ItemRetrievalRequest) -> ItemRetrievalResult:
        self._validate_request(request)
        template = self._load_template(request.template_item_point_id)
        category_budget = request.category_budgets.get(
            _single_value(template.payload, "category_large")
        )
        effective_max_price = (
            min(
                price
                for price in (
                    request.max_price,
                    category_budget,
                )
                if price is not None
            )
            if any(
                price is not None
                for price in (
                    request.max_price,
                    category_budget,
                )
            )
            else None
        )
        vector_name, vector = self._select_vector(template)
        common_conditions = self._common_conditions(template.payload)

        by_source: dict[ItemSource, list[ItemCandidate]] = {}
        for source_type in request.sources:
            if source_type is ItemSource.WARDROBE:
                by_source[source_type] = self._retrieve_wardrobe(
                    request,
                    common_conditions,
                    vector_name,
                    vector,
                )
            elif source_type is ItemSource.GOLDENSET_ITEM:
                by_source[source_type] = self._retrieve_goldenset(
                    request,
                    common_conditions,
                    vector_name,
                    vector,
                )
            elif source_type is ItemSource.PRODUCT:
                by_source[source_type] = self._retrieve_products(
                    request,
                    common_conditions,
                    vector_name,
                    vector,
                    max_price=effective_max_price,
                )

        # 호출부가 지정한 출처 순서를 유지한다. 출처 내부에서는 유사도 순이다.
        candidates = tuple(
            candidate
            for source_type in request.sources
            for candidate in by_source.get(source_type, [])
        )
        return ItemRetrievalResult(
            template=template,
            candidates=candidates,
            vector_name=vector_name,
        )

    @staticmethod
    def _validate_request(request: ItemRetrievalRequest) -> None:
        if (
            not isinstance(request.template_item_point_id, str)
            or not request.template_item_point_id.strip()
        ):
            raise ValueError("template_item_point_id가 필요합니다.")
        if not 1 <= request.limit_per_source <= 50:
            raise ValueError("limit_per_source는 1 이상 50 이하여야 합니다.")
        if len(set(request.sources)) != len(request.sources):
            raise ValueError("sources에 같은 출처를 중복 지정할 수 없습니다.")
        if ItemSource.WARDROBE in request.sources and (
            not isinstance(request.user_id, int)
            or isinstance(request.user_id, bool)
            or request.user_id <= 0
        ):
            raise ValueError("옷장 후보 검색에는 양수 user_id가 필요합니다.")
        if request.max_price is not None and (
            not isinstance(request.max_price, int)
            or isinstance(request.max_price, bool)
            or request.max_price < 0
        ):
            raise ValueError("max_price는 0 이상의 정수여야 합니다.")
        if any(
            not isinstance(category, str)
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
            for category, amount in request.category_budgets.items()
        ):
            raise ValueError("category_budgets는 대분류별 0 이상의 정수여야 합니다.")
    def _load_template(self, point_id: str) -> TemplateItem:
        points = self.client.retrieve(
            collection_name=GOLDEN_ITEM_COLLECTION,
            ids=[point_id],
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            raise TemplateItemNotFound(f"골든 아이템을 찾을 수 없습니다: {point_id}")
        point = points[0]
        return TemplateItem(
            point_id=str(point.id),
            payload=point.payload or {},
            image_vector=_vector(point, IMAGE_VECTOR),
            text_vector=_vector(point, TEXT_VECTOR),
        )

    @staticmethod
    def _select_vector(template: TemplateItem) -> tuple[str, list[float] | None]:
        if template.image_vector:
            return IMAGE_VECTOR, list(template.image_vector)
        if template.text_vector:
            return TEXT_VECTOR, list(template.text_vector)
        return "filter", None

    @staticmethod
    def _common_conditions(payload: dict[str, Any]) -> list[qm.Condition]:
        conditions: list[qm.Condition] = []
        # 최소 대분류는 있어야 상의를 하의로 교체하는 식의 잘못된 후보를 막는다.
        category_large = _single_value(payload, "category_large")
        if not category_large:
            raise ItemRetrievalError("골든 아이템에 category_large가 없습니다.")
        conditions.append(_match_value("category_large", category_large))

        # 세부 카테고리는 교체 범위를 과도하게 좁힐 수 있어 강제하지 않는다.
        # 레이어 역할이 제공된 템플릿은 같은 슬롯의 후보만 허용한다.
        if layer_role := _single_value(payload, "layer_role"):
            conditions.append(_match_value("layer_role", layer_role))
        return conditions

    def _retrieve_wardrobe(
        self,
        request: ItemRetrievalRequest,
        common_conditions: list[qm.Condition],
        vector_name: str,
        vector: list[float] | None,
    ) -> list[ItemCandidate]:
        if request.allowed_wardrobe_item_ids == ():
            return []
        conditions = [*common_conditions, _match_value("confirmed", True)]
        if request.allowed_wardrobe_item_ids is None:
            conditions.append(_match_value("user_id", request.user_id))
        else:
            conditions.append(
                qm.HasIdCondition(has_id=list(request.allowed_wardrobe_item_ids))
            )
        return self._retrieve_collection(
            collection_name=collection_spec("wardrobe").name,
            source_type=ItemSource.WARDROBE,
            conditions=conditions,
            vector_name=vector_name,
            vector=vector,
            limit=request.limit_per_source,
            must_not=_avoided_conditions(request),
        )

    def _retrieve_goldenset(
        self,
        request: ItemRetrievalRequest,
        common_conditions: list[qm.Condition],
        vector_name: str,
        vector: list[float] | None,
    ) -> list[ItemCandidate]:
        conditions = list(common_conditions)
        if request.dataset_version:
            conditions.append(_match_value("dataset_version", request.dataset_version))
        # golenset_new의 아이템 포인트에는 dataset_status/status가 없고 상태는
        # 부모 outfit_goldenset 포인트가 소유한다. 부모 코디를 승인 상태로
        # 검색한 뒤 전달된 item_point_id이므로 여기서는 버전만 다시 검증한다.
        candidates = self._retrieve_collection(
            collection_name=GOLDEN_ITEM_COLLECTION,
            source_type=ItemSource.GOLDENSET_ITEM,
            conditions=conditions,
            vector_name=vector_name,
            vector=vector,
            limit=request.limit_per_source + 1,
            must_not=_avoided_conditions(request),
        )
        return [
            candidate
            for candidate in candidates
            if candidate.point_id != request.template_item_point_id
        ][: request.limit_per_source]

    def _retrieve_products(
        self,
        request: ItemRetrievalRequest,
        common_conditions: list[qm.Condition],
        vector_name: str,
        vector: list[float] | None,
        *,
        max_price: int | None,
    ) -> list[ItemCandidate]:
        conditions = [
            *common_conditions,
            _match_value("tagging_status", "tagged"),
        ]
        if max_price is not None:
            conditions.append(
                qm.FieldCondition(
                    key="price",
                    range=qm.Range(lte=max_price),
                )
            )

        candidates: list[ItemCandidate] = []
        for collection_name in product_collection_names():
            candidates.extend(
                self._retrieve_collection(
                    collection_name=collection_name,
                    source_type=ItemSource.PRODUCT,
                    conditions=conditions,
                    vector_name=vector_name,
                    vector=vector,
                    limit=request.limit_per_source,
                    must_not=_avoided_conditions(request),
                )
            )
        candidates.sort(
            key=lambda candidate: (
                candidate.score is not None,
                candidate.score if candidate.score is not None else 0.0,
            ),
            reverse=True,
        )
        return candidates[: request.limit_per_source]

    def _retrieve_collection(
        self,
        *,
        collection_name: str,
        source_type: ItemSource,
        conditions: list[qm.Condition],
        vector_name: str,
        vector: list[float] | None,
        limit: int,
        must_not: list[qm.Condition] | None = None,
    ) -> list[ItemCandidate]:
        query_filter = qm.Filter(must=conditions or None, must_not=must_not or None)
        if vector is None:
            points, _ = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=query_filter,
                with_payload=True,
                with_vectors=False,
                limit=limit,
            )
            records = [(str(point.id), None, point.payload or {}) for point in points]
        elif hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=collection_name,
                query=vector,
                using=vector_name,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            records = [
                (str(point.id), float(point.score), point.payload or {})
                for point in response.points
            ]
        else:  # qdrant-client 구버전 호환
            points = self.client.search(
                collection_name=collection_name,
                query_vector=(vector_name, vector),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            records = [
                (str(point.id), float(point.score), point.payload or {})
                for point in points
            ]

        return [
            ItemCandidate(
                point_id=point_id,
                source_type=source_type,
                source_id=self._source_id(source_type, point_id, payload),
                source_collection=collection_name,
                score=round(score, 4) if score is not None else None,
                reasons=self._reasons(payload, score),
                payload=payload,
            )
            for point_id, score, payload in records
        ]

    @staticmethod
    def _source_id(
        source_type: ItemSource,
        point_id: str,
        payload: dict[str, Any],
    ) -> str:
        if source_type is ItemSource.WARDROBE:
            return str(payload.get("item_id") or point_id)
        if source_type is ItemSource.PRODUCT:
            return str(payload.get("external_product_id") or point_id)
        return point_id

    @staticmethod
    def _reasons(payload: dict[str, Any], score: float | None) -> tuple[str, ...]:
        reasons = [f"대분류 일치: {payload.get('category_large')}"]
        if layer_role := payload.get("layer_role"):
            reasons.append(f"레이어 역할 일치: {layer_role}")
        if score is not None:
            reasons.append(f"템플릿 아이템 유사도: {score:.4f}")
        else:
            reasons.append("벡터 없음: 태그 조건으로 검색")
        return tuple(reasons)
