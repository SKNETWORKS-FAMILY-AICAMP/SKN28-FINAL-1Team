"""검증 완료 후보에서 사용자가 체감할 수 있는 코디 차이만 남긴다."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Protocol, TypeVar

from apps.recommend.services.outfit_types import (
    OutfitComposition,
    OutfitItem,
)
from apps.recommend.services.focus_slots import (
    canonical_focus_slot,
    focus_slot_from_snapshot,
)

DEFAULT_CORE_DIVERSITY_SLOTS = frozenset({"TOP", "BOTTOM", "OUTER"})

class CandidateWithComposition(Protocol):
    composition: OutfitComposition


CandidateT = TypeVar("CandidateT", bound=CandidateWithComposition)


def _item_slot(item: OutfitItem) -> str | None:
    """레이어 역할을 우선하고 카테고리·슬롯 접두사를 안전망으로 쓴다."""

    return focus_slot_from_snapshot(
        slot=item.slot_id,
        category_large=item.category_large,
        layer_role=item.layer_role,
        snapshot=item.payload,
    )


def _core_fingerprint(
    candidate: CandidateWithComposition,
    *,
    diversity_slots: frozenset[str],
) -> tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]:
    identities: dict[str, list[tuple[str, str, str]]] = {
        slot: [] for slot in diversity_slots
    }
    for item in candidate.composition.items:
        slot = _item_slot(item)
        if slot in identities:
            identities[slot].append(item.identity)
    return tuple(
        (slot, tuple(sorted(identities[slot]))) for slot in sorted(diversity_slots)
    )


def select_diverse_candidates(
    candidates: Sequence[CandidateT],
    *,
    diversity_slots: Collection[str] = DEFAULT_CORE_DIVERSITY_SLOTS,
    limit: int = 3,
) -> tuple[CandidateT, ...]:
    """순위를 보존하며 핵심 슬롯 구성이 겹치지 않는 후보를 최대 ``limit``개 남긴다.

    첫 후보는 핵심 슬롯을 분류하지 못한 경우에도 항상 남긴다. ``diversity_slots``는
    후속 초점 추천에서 아우터처럼 특정 슬롯 집합을 주입할 수 있는 경계다.
    """

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit은 1 이상의 정수여야 합니다.")
    if not candidates:
        return ()

    normalized_slots = frozenset(
        slot
        for raw_slot in diversity_slots
        if (slot := canonical_focus_slot(raw_slot)) is not None
    )
    if not normalized_slots:
        raise ValueError("다양성 판정 슬롯이 하나 이상 필요합니다.")

    selected = [candidates[0]]
    seen = {
        _core_fingerprint(
            candidates[0],
            diversity_slots=normalized_slots,
        )
    }
    for candidate in candidates[1:]:
        if len(selected) >= limit:
            break
        fingerprint = _core_fingerprint(
            candidate,
            diversity_slots=normalized_slots,
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        selected.append(candidate)
    return tuple(selected)
