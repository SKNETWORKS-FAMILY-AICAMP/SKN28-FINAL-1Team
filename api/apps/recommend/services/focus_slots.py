"""사용자 초점 추천과 후보 다양성이 공유하는 표준 슬롯 계약."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

FOCUS_SLOT_ORDER = (
    "TOP",
    "BOTTOM",
    "OUTER",
    "DRESS",
    "SHOES",
    "ACCESSORY",
)
FOCUS_SLOT_LABELS = {
    "TOP": "상의",
    "BOTTOM": "하의",
    "OUTER": "아우터",
    "DRESS": "원피스",
    "SHOES": "신발",
    "ACCESSORY": "액세서리",
}

_SLOT_ALIASES = {
    "TOP": "TOP",
    "UPPER": "TOP",
    "INNER": "TOP",
    "MID": "TOP",
    "LAYER": "TOP",
    "상의": "TOP",
    "기본상의": "TOP",
    "기본_상의": "TOP",
    "레이어드상의": "TOP",
    "레이어드_상의": "TOP",
    "이너": "TOP",
    "BOTTOM": "BOTTOM",
    "LOWER": "BOTTOM",
    "하의": "BOTTOM",
    "OUTER": "OUTER",
    "OUTERWEAR": "OUTER",
    "아우터": "OUTER",
    "겉옷": "OUTER",
    "DRESS": "DRESS",
    "원피스": "DRESS",
    "SHOES": "SHOES",
    "FOOTWEAR": "SHOES",
    "신발": "SHOES",
    "ACCESSORY": "ACCESSORY",
    "ACCESSORIES": "ACCESSORY",
    "액세서리": "ACCESSORY",
    "BAG": "ACCESSORY",
    "가방": "ACCESSORY",
    "모자": "ACCESSORY",
    "주얼리": "ACCESSORY",
}


def canonical_focus_slot(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("-", "_").replace(" ", "_").upper()
    if not normalized:
        return None
    return _SLOT_ALIASES.get(normalized)


def normalize_focus_slots(values: Iterable[object]) -> tuple[str, ...]:
    normalized = {
        slot for value in values if (slot := canonical_focus_slot(value)) is not None
    }
    return tuple(slot for slot in FOCUS_SLOT_ORDER if slot in normalized)


def focus_slot_from_values(*values: object) -> str | None:
    for value in values:
        if slot := canonical_focus_slot(value):
            return slot
    return None


def focus_slot_from_snapshot(
    *,
    slot: object = "",
    category_large: object = "",
    layer_role: object = "",
    snapshot: Mapping[str, Any] | None = None,
) -> str | None:
    data = snapshot or {}
    slot_prefix = slot.split(":", 1)[0] if isinstance(slot, str) else ""
    return focus_slot_from_values(
        layer_role,
        data.get("layer_role"),
        category_large,
        data.get("category_large"),
        slot_prefix,
    )


def focus_slot_labels(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(FOCUS_SLOT_LABELS[value] for value in normalize_focus_slots(values))

