"""모드별 Composer가 공유하는 결정적 조합 엔진.

이 모듈은 슬롯별 후보를 출처 정책에 따라 조합하는 기계적 책임만
담당한다. 옷장 기반과 추구미 기반의 상세 정책은 각 전용 Composer가
결정하고, 완성된 조합의 적합성은 OutfitValidator가 다시 검사한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.recommend.services.item_retriever import (
    ItemCandidate,
    ItemRetrievalResult,
    ItemSource,
    TemplateItem,
)
from apps.recommend.services.outfit_types import (
    OutfitComposition,
    OutfitItem,
    OutfitSlot,
    RecommendationMode,
)
from apps.recommend.services.qdrant import GOLDEN_ITEM_COLLECTION


class CompositionError(RuntimeError):
    """코디 구성 요청을 안전하게 처리할 수 없는 경우."""


@dataclass(frozen=True)
class CompositionPolicy:
    mode: RecommendationMode
    source_priority: tuple[ItemSource, ...]
    composition_count: int = 3
    total_budget: int | None = None
    require_image: bool = True
    candidates_per_slot: int = 6


@dataclass(frozen=True)
class CompositionRequest:
    """기존 단일 조합 호출부를 위한 호환 요청."""

    mode: RecommendationMode
    slot_results: tuple[ItemRetrievalResult, ...]
    total_budget: int | None = None
    require_image: bool = True


@dataclass(frozen=True)
class _PartialComposition:
    items: tuple[OutfitItem, ...] = ()
    used: frozenset[tuple[str, str, str]] = frozenset()
    missing_slot_ids: tuple[str, ...] = ()
    total_product_price: int = 0
    priority_cost: int = 0
    similarity_sum: float = 0.0


# 이전 호출부가 단계적 마이그레이션 할 수 있도록 이름을 유지한다.
ComposedItem = OutfitItem
CompositionResult = OutfitComposition


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


def _outfit_slot(template: TemplateItem) -> OutfitSlot:
    return OutfitSlot(
        slot_id=_slot_id(template),
        template_point_id=template.point_id,
        category_large=_payload_text(template.payload, "category_large"),
        category_small=_payload_text(template.payload, "category_small"),
        layer_role=_payload_text(template.payload, "layer_role"),
    )


def _template_candidate(template: TemplateItem) -> ItemCandidate:
    """대체 후보가 없을 때만 사용할 원본 골든셋 아이템."""

    return ItemCandidate(
        point_id=template.point_id,
        source_type=ItemSource.GOLDENSET_ITEM,
        source_id=template.point_id,
        source_collection=GOLDEN_ITEM_COLLECTION,
        score=1.0,
        reasons=("선정된 골든 코디의 원본 아이템",),
        payload=template.payload,
    )


def _candidate_identity(candidate: ItemCandidate) -> tuple[str, str, str]:
    return (
        candidate.source_type.value,
        candidate.source_collection,
        candidate.source_id,
    )


def _selection_reason(mode: RecommendationMode, source: ItemSource) -> str:
    if mode is RecommendationMode.WARDROBE_BASED:
        return {
            ItemSource.WARDROBE: "옷장 기반: 보유 아이템 우선",
            ItemSource.GOLDENSET_ITEM: "옷장 부족: 골든셋 참고 아이템으로 보완",
            ItemSource.PRODUCT: "옷장 기반 정책 외 상품 선택",
        }[source]
    return {
        ItemSource.WARDROBE: "추구미 기반: 보유 아이템으로 교체",
        ItemSource.PRODUCT: "추구미 기반: 구매 가능한 상품으로 교체",
        ItemSource.GOLDENSET_ITEM: "대체 후보 부족: 골든셋 참고 아이템 유지",
    }[source]


class CompositionEngine:
    """슬롯 후보를 beam search로 조합해 서로 다른 코디를 반환한다."""

    def compose(
        self,
        slot_results: tuple[ItemRetrievalResult, ...],
        *,
        policy: CompositionPolicy,
    ) -> tuple[OutfitComposition, ...]:
        self._validate(slot_results, policy)
        source_rank = {
            source: rank for rank, source in enumerate(policy.source_priority)
        }
        slots = tuple(_outfit_slot(result.template) for result in slot_results)
        states = [_PartialComposition()]
        beam_width = max(policy.composition_count * 12, 24)

        for slot_result in slot_results:
            candidates = self._ordered_candidates(
                slot_result,
                source_rank=source_rank,
                limit=policy.candidates_per_slot,
            )
            expanded: list[_PartialComposition] = []
            for state in states:
                additions = self._add_slot_candidates(
                    state,
                    slot_result=slot_result,
                    candidates=candidates,
                    source_rank=source_rank,
                    policy=policy,
                )
                if additions:
                    expanded.extend(additions)
                else:
                    expanded.append(
                        _PartialComposition(
                            items=state.items,
                            used=state.used,
                            missing_slot_ids=(
                                *state.missing_slot_ids,
                                _slot_id(slot_result.template),
                            ),
                            total_product_price=state.total_product_price,
                            priority_cost=state.priority_cost,
                            similarity_sum=state.similarity_sum,
                        )
                    )
            states = sorted(expanded, key=self._state_sort_key)[:beam_width]

        compositions: list[OutfitComposition] = []
        seen: set[tuple[tuple[str, str, str], ...]] = set()
        for state in sorted(states, key=self._state_sort_key):
            fingerprint = tuple(item.identity for item in state.items)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            compositions.append(
                OutfitComposition(
                    mode=policy.mode,
                    items=state.items,
                    missing_slot_ids=state.missing_slot_ids,
                    total_product_price=state.total_product_price,
                    warnings=tuple(
                        f"{slot_id}: 조건을 만족하는 후보 없음"
                        for slot_id in state.missing_slot_ids
                    ),
                    slots=slots,
                )
            )
            if len(compositions) >= policy.composition_count:
                break
        return tuple(compositions)

    @staticmethod
    def _validate(
        slot_results: tuple[ItemRetrievalResult, ...],
        policy: CompositionPolicy,
    ) -> None:
        if not slot_results:
            raise ValueError("최소 하나의 아이템 슬롯이 필요합니다.")
        if not 1 <= policy.composition_count <= 3:
            raise ValueError("composition_count는 1 이상 3 이하여야 합니다.")
        if not 1 <= policy.candidates_per_slot <= 20:
            raise ValueError("candidates_per_slot은 1 이상 20 이하여야 합니다.")
        if not policy.source_priority:
            raise ValueError("최소 하나의 아이템 출처가 필요합니다.")
        if len(policy.source_priority) != len(set(policy.source_priority)):
            raise ValueError("아이템 출처 우선순위가 중복되었습니다.")
        if policy.total_budget is not None and (
            not isinstance(policy.total_budget, int)
            or isinstance(policy.total_budget, bool)
            or policy.total_budget < 0
        ):
            raise ValueError("total_budget은 0 이상의 정수여야 합니다.")
        template_ids = [result.template.point_id for result in slot_results]
        if len(template_ids) != len(set(template_ids)):
            raise CompositionError("같은 템플릿 아이템 슬롯이 중복되었습니다.")

    @staticmethod
    def _ordered_candidates(
        slot_result: ItemRetrievalResult,
        *,
        source_rank: dict[ItemSource, int],
        limit: int,
    ) -> list[ItemCandidate]:
        unique: dict[tuple[str, str, str], ItemCandidate] = {}
        for candidate in (
            *slot_result.candidates,
            _template_candidate(slot_result.template),
        ):
            if candidate.source_type not in source_rank:
                continue
            identity = _candidate_identity(candidate)
            previous = unique.get(identity)
            previous_score = (
                previous.score
                if previous is not None and previous.score is not None
                else -1.0
            )
            current_score = candidate.score if candidate.score is not None else -1.0
            if previous is None or current_score > previous_score:
                unique[identity] = candidate
        return sorted(
            unique.values(),
            key=lambda candidate: (
                source_rank[candidate.source_type],
                -(candidate.score if candidate.score is not None else -1.0),
                candidate.source_collection,
                candidate.source_id,
            ),
        )[:limit]

    def _add_slot_candidates(
        self,
        state: _PartialComposition,
        *,
        slot_result: ItemRetrievalResult,
        candidates: list[ItemCandidate],
        source_rank: dict[ItemSource, int],
        policy: CompositionPolicy,
    ) -> list[_PartialComposition]:
        additions: list[_PartialComposition] = []
        for candidate in candidates:
            identity = _candidate_identity(candidate)
            if identity in state.used:
                continue
            image_ref = candidate.image_ref
            if policy.require_image and not image_ref:
                continue
            next_price = state.total_product_price
            if candidate.source_type is ItemSource.PRODUCT:
                if policy.total_budget is not None and candidate.price is None:
                    continue
                next_price += candidate.price or 0
                if policy.total_budget is not None and next_price > policy.total_budget:
                    continue
            additions.append(
                _PartialComposition(
                    items=(
                        *state.items,
                        self._to_item(
                            template=slot_result.template,
                            candidate=candidate,
                            mode=policy.mode,
                        ),
                    ),
                    used=state.used | {identity},
                    missing_slot_ids=state.missing_slot_ids,
                    total_product_price=next_price,
                    priority_cost=(
                        state.priority_cost + source_rank[candidate.source_type]
                    ),
                    similarity_sum=(
                        state.similarity_sum
                        + (candidate.score if candidate.score is not None else -1.0)
                    ),
                )
            )
        return additions

    @staticmethod
    def _to_item(
        *,
        template: TemplateItem,
        candidate: ItemCandidate,
        mode: RecommendationMode,
    ) -> OutfitItem:
        return OutfitItem(
            slot_id=_slot_id(template),
            template_point_id=template.point_id,
            category_large=_payload_text(template.payload, "category_large"),
            layer_role=_payload_text(template.payload, "layer_role"),
            source_type=candidate.source_type,
            source_id=candidate.source_id,
            source_collection=candidate.source_collection,
            point_id=candidate.point_id,
            image_ref=_image_ref(candidate.payload),
            price=candidate.price,
            score=candidate.score,
            reasons=(
                _selection_reason(mode, candidate.source_type),
                *candidate.reasons,
            ),
            payload=candidate.payload,
        )

    @staticmethod
    def _state_sort_key(state: _PartialComposition) -> tuple:
        return (
            len(state.missing_slot_ids),
            state.priority_cost,
            -state.similarity_sum,
            tuple(item.identity for item in state.items),
        )


class OutfitComposer:
    """기존 단일 조합 인터페이스. 신규 코드는 모드별 Composer를 사용한다."""

    def __init__(self, *, engine: CompositionEngine | None = None) -> None:
        self.engine = engine or CompositionEngine()

    def compose(self, request: CompositionRequest) -> OutfitComposition:
        if not isinstance(request.mode, RecommendationMode):
            raise TypeError("유효한 추천 모드가 필요합니다.")
        priority = {
            RecommendationMode.WARDROBE_BASED: (ItemSource.WARDROBE,),
            RecommendationMode.PURSUIT_BASED: (
                ItemSource.PRODUCT,
                ItemSource.WARDROBE,
                ItemSource.GOLDENSET_ITEM,
            ),
        }[request.mode]
        return self.engine.compose(
            request.slot_results,
            policy=CompositionPolicy(
                mode=request.mode,
                source_priority=priority,
                composition_count=1,
                total_budget=request.total_budget,
                require_image=request.require_image,
            ),
        )[0]
