"""검색된 아이템 후보를 최종 코디로 구성하는 결정적 Composer.

Retriever는 출처별 후보를 찾고, Composer는 추천 모드의 출처 우선순위·전체
예산·중복·이미지 사용 가능 여부를 적용해 각 슬롯에 하나의 아이템을 선택한다.
LLM과 이미지 생성은 이 단계의 책임이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from apps.recommend.services.item_retriever import (
    ItemCandidate,
    ItemRetrievalResult,
    ItemSource,
    TemplateItem,
)
from apps.recommend.services.qdrant import GOLDEN_ITEM_COLLECTION


class CompositionError(RuntimeError):
    """코디 구성 요청을 안전하게 처리할 수 없는 경우."""


class RecommendationMode(StrEnum):
    """아이템을 고르는 정책이 다른 두 가지 추천 모드."""

    WARDROBE_BASED = "WARDROBE_BASED"
    PURSUIT_BASED = "PURSUIT_BASED"


SOURCE_PRIORITY: dict[RecommendationMode, tuple[ItemSource, ...]] = {
    RecommendationMode.WARDROBE_BASED: (
        ItemSource.WARDROBE,
        ItemSource.GOLDENSET_ITEM,
        ItemSource.PRODUCT,
    ),
    RecommendationMode.PURSUIT_BASED: (
        ItemSource.PRODUCT,
        ItemSource.WARDROBE,
        ItemSource.GOLDENSET_ITEM,
    ),
}


@dataclass(frozen=True)
class CompositionRequest:
    mode: RecommendationMode
    slot_results: tuple[ItemRetrievalResult, ...]
    total_budget: int | None = None
    require_image: bool = True


@dataclass(frozen=True)
class ComposedItem:
    slot_id: str
    template_point_id: str
    category_large: str
    layer_role: str
    source_type: ItemSource
    source_id: str
    source_collection: str
    point_id: str
    image_ref: str
    price: int | None
    score: float | None
    reasons: tuple[str, ...]
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_owned(self) -> bool:
        return self.source_type is ItemSource.WARDROBE

    @property
    def is_purchasable(self) -> bool:
        return self.source_type is ItemSource.PRODUCT


@dataclass(frozen=True)
class CompositionResult:
    mode: RecommendationMode
    items: tuple[ComposedItem, ...]
    missing_slot_ids: tuple[str, ...]
    total_product_price: int
    warnings: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing_slot_ids

    @property
    def owned_count(self) -> int:
        return sum(item.is_owned for item in self.items)

    @property
    def purchasable_count(self) -> int:
        return sum(item.is_purchasable for item in self.items)

    @property
    def goldenset_count(self) -> int:
        return sum(item.source_type is ItemSource.GOLDENSET_ITEM for item in self.items)


def _payload_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _image_ref(payload: dict[str, Any]) -> str:
    for key in ("s3_key", "image_s3_key", "image_url"):
        if value := payload.get(key):
            return str(value)
    return ""


def _slot_id(template: TemplateItem) -> str:
    explicit = _payload_text(template.payload, "slot_id")
    if explicit:
        return explicit
    layer_role = _payload_text(template.payload, "layer_role")
    return f"{layer_role}:{template.point_id}" if layer_role else template.point_id


def _template_candidate(template: TemplateItem) -> ItemCandidate:
    """대체 후보가 없을 때 사용할 원본 골든셋 아이템을 만든다."""

    return ItemCandidate(
        point_id=template.point_id,
        source_type=ItemSource.GOLDENSET_ITEM,
        source_id=template.point_id,
        source_collection=GOLDEN_ITEM_COLLECTION,
        score=1.0,
        reasons=("선정된 골든 코디의 원본 아이템",),
        payload=template.payload,
    )


def _identity(candidate: ItemCandidate) -> tuple[str, str, str]:
    """쇼핑몰 간 우연한 외부 ID 충돌도 피하는 중복 판별 키."""

    return (
        candidate.source_type.value,
        candidate.source_collection,
        candidate.source_id,
    )


def _priority_reason(mode: RecommendationMode, source_type: ItemSource) -> str:
    if mode is RecommendationMode.WARDROBE_BASED:
        labels = {
            ItemSource.WARDROBE: "옷장 기반: 보유 아이템 우선",
            ItemSource.GOLDENSET_ITEM: "옷장 부족: 골든셋 아이템으로 보완",
            ItemSource.PRODUCT: "옷장·골든셋 후보 부족: 상품으로 보완",
        }
    else:
        labels = {
            ItemSource.PRODUCT: "추구미 기반: 새 상품 우선",
            ItemSource.WARDROBE: "상품 후보 부족: 보유 아이템으로 대체",
            ItemSource.GOLDENSET_ITEM: "구매·옷장 후보 부족: 골든셋 원본 유지",
        }
    return labels[source_type]


class OutfitComposer:
    """하나의 골든 코디에 대한 슬롯별 검색 결과를 최종 아이템으로 선택한다."""

    def compose(self, request: CompositionRequest) -> CompositionResult:
        self._validate_request(request)
        priority = SOURCE_PRIORITY[request.mode]
        used: set[tuple[str, str, str]] = set()
        selected: list[ComposedItem] = []
        missing: list[str] = []
        warnings: list[str] = []
        total_product_price = 0

        for slot_result in request.slot_results:
            template = slot_result.template
            slot_id = _slot_id(template)
            pool = self._ordered_candidates(slot_result, priority)
            chosen = None
            for candidate in pool:
                if _identity(candidate) in used:
                    continue
                image_ref = candidate.image_ref
                if request.require_image and not image_ref:
                    continue
                if candidate.source_type is ItemSource.PRODUCT:
                    price = candidate.price
                    if request.total_budget is not None:
                        if price is None:
                            continue
                        if total_product_price + price > request.total_budget:
                            continue
                chosen = candidate
                break

            if chosen is None:
                missing.append(slot_id)
                warnings.append(
                    f"{slot_id}: 이미지·중복·예산 조건을 만족하는 후보 없음"
                )
                continue

            used.add(_identity(chosen))
            if chosen.source_type is ItemSource.PRODUCT and chosen.price is not None:
                total_product_price += chosen.price
            selected.append(
                self._composed_item(
                    template=template,
                    candidate=chosen,
                    mode=request.mode,
                )
            )

        return CompositionResult(
            mode=request.mode,
            items=tuple(selected),
            missing_slot_ids=tuple(missing),
            total_product_price=total_product_price,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _validate_request(request: CompositionRequest) -> None:
        if not isinstance(request.mode, RecommendationMode):
            raise TypeError("유효한 추천 모드가 필요합니다.")
        if not request.slot_results:
            raise ValueError("최소 하나의 아이템 슬롯이 필요합니다.")
        if request.total_budget is not None and (
            not isinstance(request.total_budget, int)
            or isinstance(request.total_budget, bool)
            or request.total_budget < 0
        ):
            raise ValueError("total_budget은 0 이상의 정수여야 합니다.")

        template_ids = [result.template.point_id for result in request.slot_results]
        if len(template_ids) != len(set(template_ids)):
            raise CompositionError("같은 템플릿 아이템 슬롯이 중복되었습니다.")

    @staticmethod
    def _ordered_candidates(
        slot_result: ItemRetrievalResult,
        priority: tuple[ItemSource, ...],
    ) -> list[ItemCandidate]:
        # 원본 골든 아이템도 fallback 후보로 포함한다. 같은 출처 안에서는
        # 원본(1.0)과 Retriever 유사도를 함께 비교한다.
        candidates = [
            *slot_result.candidates,
            _template_candidate(slot_result.template),
        ]
        rank = {source_type: index for index, source_type in enumerate(priority)}
        return sorted(
            candidates,
            key=lambda candidate: (
                rank[candidate.source_type],
                -(candidate.score if candidate.score is not None else -1.0),
                candidate.source_collection,
                candidate.source_id,
            ),
        )

    @staticmethod
    def _composed_item(
        *,
        template: TemplateItem,
        candidate: ItemCandidate,
        mode: RecommendationMode,
    ) -> ComposedItem:
        payload = candidate.payload
        return ComposedItem(
            slot_id=_slot_id(template),
            template_point_id=template.point_id,
            category_large=_payload_text(template.payload, "category_large"),
            layer_role=_payload_text(template.payload, "layer_role"),
            source_type=candidate.source_type,
            source_id=candidate.source_id,
            source_collection=candidate.source_collection,
            point_id=candidate.point_id,
            image_ref=_image_ref(payload),
            price=candidate.price,
            score=candidate.score,
            reasons=(_priority_reason(mode, candidate.source_type), *candidate.reasons),
            payload=payload,
        )
