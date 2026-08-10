"""추구미 UI 코드와 Qdrant 패션 태그를 연결하는 공통 어휘."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranslatedPreferences:
    tags: dict[str, set[str]] = field(default_factory=dict)
    unmapped: tuple[str, ...] = ()


_CATEGORY_FIELDS = {
    "seasons": "season",
    "styles": "style",
    "colors": "color",
    "necklines": "neckline",
    "top_fits": "fit",
    "pants_fits": "fit",
    "top_lengths": "length",
    "pants_lengths": "length",
    "skirt_lengths": "length",
    "sleeves": "sleeve",
    "skirt_types": "fit",
}

_LABELS = {
    # 계절
    "spring": "봄",
    "summer": "여름",
    "autumn": "가을",
    "winter": "겨울",
    # 스타일
    "minimal": "미니멀",
    "casual": "캐주얼",
    "street": "스트릿",
    "classic": "클래식",
    "lovely": "러블리",
    "chic": "시크",
    "sporty": "스포티",
    "vintage": "빈티지",
    "romantic": "로맨틱",
    "elegance": "엘레강스",
    "retro": "레트로",
    "modern": "모던",
    "business": "비즈니스",
    "business_casual": "비즈니스 캐주얼",
    "americasual": "아메카지",
    "boyish": "보이시",
    # 색상
    "black": "블랙",
    "ivory": "아이보리",
    "white": "화이트",
    "gray": "그레이",
    "charcoal": "차콜",
    "navy": "네이비",
    "beige": "베이지",
    "brown": "브라운",
    "olive": "올리브",
    "khaki": "카키",
    "carmel": "카멜",
    "denim_blue": "데님블루",
    "light_pink": "라이트 핑크",
    "pink": "핑크",
    "rose": "로즈",
    "mauve": "모브",
    "peach": "피치",
    "coral": "코럴",
    "light_blue": "라이트 블루",
    "blue": "블루",
    "mint": "민트",
    "green": "그린",
    "red": "레드",
    "burgundy": "버건디",
    "yellow": "옐로우",
    "purple": "퍼플",
    "orange": "오렌지",
    "silver": "실버",
    "gold": "골드",
    # 핏·기장·소매·넥라인
    "normal": "노멀핏",
    "slim": "슬림핏",
    "loose": "루즈핏",
    "oversized": "오버핏",
    "wide": "와이드",
    "jogger": "조거",
    "straight": "스트레이트",
    "skinny": "스키니",
    "bootcut": "부츠컷",
    "slacks": "슬랙스",
    "semi_wide": "세미와이드",
    "crop": "크롭",
    "short": "숏",
    "regular": "레귤러",
    "long": "롱",
    "short_shorts": "3부",
    "shorts": "5부",
    "seven_part": "7부",
    "long_pants": "긴바지",
    "mini": "미니",
    "midi": "미디",
    "maxi": "맥시",
    "three_quarter": "7부소매",
    "sleeveless": "민소매",
    "round": "라운드넥",
    "vneck": "브이넥",
    "uneck": "유넥",
    "hood": "후드",
    "square": "스퀘어넥",
    "off_shoulder": "오프숄더",
    "half_high": "반하이넥",
    "one_shoulder": "원숄더",
    "halter": "홀터넥",
    "boat": "보트넥",
    "heart": "하트넥",
    "turtle": "터틀넥",
    "high": "하이넥",
    "half_zip": "반집업",
    "aline": "A라인",
    "pleats": "플리츠",
    "flare": "플레어 라인",
    "hline": "H라인",
    "mermaid": "머메이드",
    "balloon": "벌룬",
}


def _variants(value: str) -> set[str]:
    normalized = value.strip()
    if not normalized:
        return set()
    variants = {normalized, normalized.lower()}
    if label := _LABELS.get(normalized.lower()):
        variants.add(label)
    return variants


def translate(payload: Any) -> TranslatedPreferences:
    """preferred/avoided의 카테고리별 코드 배열을 Qdrant 필드 태그로 바꾼다."""
    if not isinstance(payload, dict):
        return TranslatedPreferences()

    tags: dict[str, set[str]] = {}
    unmapped: list[str] = []
    for category, raw_values in payload.items():
        field_name = _CATEGORY_FIELDS.get(str(category))
        if field_name is None:
            unmapped.append(str(category))
            continue
        if not isinstance(raw_values, (list, tuple, set)):
            unmapped.append(str(category))
            continue
        for raw_value in raw_values:
            if not isinstance(raw_value, str):
                unmapped.append(f"{category}:{raw_value}")
                continue
            tags.setdefault(field_name, set()).update(_variants(raw_value))
    return TranslatedPreferences(tags=tags, unmapped=tuple(sorted(set(unmapped))))
