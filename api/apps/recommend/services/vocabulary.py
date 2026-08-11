"""추구미 UI 코드와 Qdrant 패션 태그를 연결하는 공통 어휘."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranslatedPreferences:
    tags: dict[str, set[str]] = field(default_factory=dict)
    unmapped: tuple[str, ...] = ()


SEASON = {
    "spring": "봄",
    "summer": "여름",
    "autumn": "가을",
    "winter": "겨울",
}
STYLE = {
    "minimal": "미니멀",
    "casual": "캐주얼",
    "street": "스트릿",
    "lovely": "러블리",
    "chic": "시크",
    "sporty": "스포티",
    "vintage": "빈티지",
    "americasual": "아메카지",
}
COLOR = {
    "black": "블랙",
    "ivory": "아이보리",
    "white": "화이트",
    "gray": "그레이",
    "charcoal": "그레이",
    "navy": "네이비",
    "beige": "베이지",
    "brown": "브라운",
    "olive": "카키",
    "khaki": "카키",
    "carmel": "브라운",
    "denim_blue": "블루",
    "light_pink": "핑크",
    "pink": "핑크",
    "rose": "핑크",
    "mauve": "퍼플",
    "peach": "오렌지",
    "coral": "오렌지",
    "light_blue": "스카이블루",
    "blue": "블루",
    "mint": "그린",
    "green": "그린",
    "red": "레드",
    "burgundy": "레드",
    "yellow": "옐로우",
    "purple": "퍼플",
    "orange": "오렌지",
    "silver": "그레이",
    "gold": "베이지",
}
TOP_FIT = {
    "normal": "레귤러핏",
    "slim": "슬림핏",
    "loose": "오버핏",
    "oversized": "오버핏",
}
PANTS_FIT = {
    "wide": "와이드핏",
    "semi_wide": "와이드핏",
    "straight": "레귤러핏",
    "slacks": "레귤러핏",
    "bootcut": "레귤러핏",
    "jogger": "레귤러핏",
    "skinny": "슬림핏",
}
TOP_LENGTH = {
    "crop": "크롭",
    "regular": "기본",
    "short": "기본",
    "long": "롱",
}
SLEEVE = {
    "long": "긴팔",
    "short": "반팔",
    "sleeveless": "민소매",
}

_TABLES = {
    "seasons": SEASON,
    "styles": STYLE,
    "colors": COLOR,
    "top_fits": TOP_FIT,
    "pants_fits": PANTS_FIT,
    "top_lengths": TOP_LENGTH,
    "sleeves": SLEEVE,
    "fits": {**TOP_FIT, **PANTS_FIT},
}
_CATEGORY_FIELDS = {
    "seasons": "season",
    "styles": "style",
    "colors": "color",
    "top_fits": "fit",
    "pants_fits": "fit",
    "top_lengths": "length",
    "sleeves": "sleeve",
    "fits": "fit",
}
_DIRECT_VALUES = {
    "season": frozenset({"봄", "여름", "가을", "겨울", "간절기"}),
    "style": frozenset(
        {
            "캐주얼",
            "포멀",
            "미니멀",
            "스트릿",
            "스포티",
            "러블리",
            "페미닌",
            "시크",
            "빈티지",
            "아웃도어",
            "댄디",
            "아메카지",
            "트렌디",
            "리조트",
            "베이직",
        }
    ),
    "color": frozenset(
        {
            "화이트",
            "블랙",
            "그레이",
            "네이비",
            "블루",
            "스카이블루",
            "레드",
            "핑크",
            "오렌지",
            "옐로우",
            "그린",
            "카키",
            "브라운",
            "베이지",
            "아이보리",
            "퍼플",
            "멀티",
        }
    ),
    "fit": frozenset({"오버핏", "레귤러핏", "슬림핏", "와이드핏"}),
    "length": frozenset({"크롭", "기본", "롱"}),
    "sleeve": frozenset({"반팔", "긴팔", "민소매"}),
}


def translate(payload: Any) -> TranslatedPreferences:
    """선호/기피 코드를 실제 Qdrant taxonomy 값으로 변환한다."""
    if not isinstance(payload, dict):
        return TranslatedPreferences()

    tags: dict[str, set[str]] = {}
    unmapped: list[str] = []
    for raw_category, raw_values in payload.items():
        category = str(raw_category)
        field_name = _CATEGORY_FIELDS.get(category)
        table = _TABLES.get(category)
        if field_name is None or table is None:
            unmapped.append(category)
            continue
        if not isinstance(raw_values, (list, tuple, set)):
            unmapped.append(category)
            continue

        for raw_value in raw_values:
            if not isinstance(raw_value, str):
                unmapped.append(f"{category}:{raw_value}")
                continue
            value = raw_value.strip()
            if not value:
                continue
            label = table.get(value.casefold())
            if label is None and value in _DIRECT_VALUES[field_name]:
                label = value
            if label is None:
                unmapped.append(f"{category}:{value}")
                continue
            tags.setdefault(field_name, set()).add(label)

    return TranslatedPreferences(tags=tags, unmapped=tuple(sorted(set(unmapped))))
