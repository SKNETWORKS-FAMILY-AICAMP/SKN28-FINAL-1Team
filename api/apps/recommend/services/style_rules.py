"""체형·기온 추천 규칙 파일을 검증하고 로드한다."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

KNOWN_VALUES: dict[str, frozenset[str]] = {
    "category_large": frozenset(
        {
            "상의",
            "하의",
            "아우터",
            "원피스/세트",
            "신발",
            "가방",
            "액세서리",
            "언더웨어/이너웨어",
        }
    ),
    "fit": frozenset({"오버핏", "레귤러핏", "슬림핏", "와이드핏"}),
    "length": frozenset({"크롭", "기본", "롱"}),
    "sleeve": frozenset({"반팔", "긴팔", "민소매"}),
    "pattern": frozenset(
        {
            "무지",
            "체크",
            "스트라이프",
            "도트",
            "플로럴",
            "그래픽/로고",
            "카모",
            "애니멀",
        }
    ),
    "material": frozenset(
        {
            "코튼",
            "데님",
            "니트",
            "울",
            "린넨",
            "레더",
            "나일론",
            "폴리에스터",
            "시폰",
            "코듀로이",
            "트위드",
            "퍼/무스탕",
            "패딩충전재",
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
}
_META_KEYS = frozenset({"reason", "hard", "score", "rule", "label", "note"})


@dataclass(frozen=True)
class Rule:
    match: dict[str, str]
    reason: str
    hard: bool = False

    def matches(self, tags: dict[str, Any]) -> bool:
        for field_name, expected in self.match.items():
            value = tags.get(field_name)
            if isinstance(value, (list, tuple, set, frozenset)):
                if expected not in value:
                    return False
            elif value != expected:
                return False
        return True


@dataclass(frozen=True)
class AxisRules:
    prefer: tuple[Rule, ...] = ()
    avoid: tuple[Rule, ...] = ()


@dataclass(frozen=True)
class Weights:
    preference_match: int = 30
    preference_avoid: int = -60
    rule_prefer: int = 15
    rule_avoid: int = -20
    context_match: int = 10


class RuleError(ValueError):
    pass


def _parse_rules(rows: list[dict[str, Any]] | None) -> tuple[Rule, ...]:
    parsed: list[Rule] = []
    for row in rows or []:
        match = {key: value for key, value in row.items() if key not in _META_KEYS}
        if match:
            parsed.append(
                Rule(
                    match=match,
                    reason=str(row.get("reason") or ""),
                    hard=bool(row.get("hard", False)),
                )
            )
    return tuple(parsed)


def _validate_rows(rows: list[dict[str, Any]] | None, where: str) -> list[str]:
    problems: list[str] = []
    for index, row in enumerate(rows or []):
        for field_name, value in row.items():
            if field_name in _META_KEYS:
                continue
            allowed = KNOWN_VALUES.get(field_name)
            if allowed is None:
                problems.append(
                    f"{where}[{index}]: 알 수 없는 태그 필드 '{field_name}'"
                )
            elif value not in allowed:
                problems.append(f"{where}[{index}]: '{field_name}'에 없는 값 '{value}'")
    return problems


def validate_body_rules(document: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for axis in ("silhouette", "bmi_band"):
        for key, block in (document.get(axis) or {}).items():
            problems.extend(_validate_rows(block.get("prefer"), f"{axis}.{key}.prefer"))
            problems.extend(_validate_rows(block.get("avoid"), f"{axis}.{key}.avoid"))
    for ratio_axis, values in (document.get("ratios") or {}).items():
        for key, block in values.items():
            where = f"ratios.{ratio_axis}.{key}"
            problems.extend(_validate_rows(block.get("prefer"), f"{where}.prefer"))
            problems.extend(_validate_rows(block.get("avoid"), f"{where}.avoid"))
    return problems


@dataclass(frozen=True)
class BodyRules:
    schema_version: str
    weights: Weights
    silhouette: dict[str, AxisRules]
    bmi_band: dict[str, AxisRules]
    ratios: dict[str, dict[str, AxisRules]]

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> BodyRules:
        def axis(block: dict[str, Any]) -> AxisRules:
            return AxisRules(
                prefer=_parse_rules(block.get("prefer")),
                avoid=_parse_rules(block.get("avoid")),
            )

        raw_weights = {
            key: value
            for key, value in (document.get("weights") or {}).items()
            if key != "note"
        }
        return cls(
            schema_version=str(document.get("schema_version") or ""),
            weights=Weights(**raw_weights),
            silhouette={
                key: axis(block)
                for key, block in (document.get("silhouette") or {}).items()
            },
            bmi_band={
                key: axis(block)
                for key, block in (document.get("bmi_band") or {}).items()
            },
            ratios={
                ratio_axis: {key: axis(block) for key, block in values.items()}
                for ratio_axis, values in (document.get("ratios") or {}).items()
            },
        )

    def for_profile(self, profile: Any) -> AxisRules:
        prefer: list[Rule] = []
        avoid: list[Rule] = []
        blocks = [
            self.silhouette.get(profile.silhouette),
            self.bmi_band.get(profile.bmi_band),
            *(
                self.ratios.get(axis, {}).get(value)
                for axis, value in profile.ratios.items()
            ),
        ]
        for block in blocks:
            if block is not None:
                prefer.extend(block.prefer)
                avoid.extend(block.avoid)
        return AxisRules(prefer=tuple(prefer), avoid=tuple(avoid))


@lru_cache(maxsize=1)
def load_body_rules() -> BodyRules:
    path = RULES_DIR / "body_fit_rules.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_body_rules(document)
    if problems:
        raise RuleError(f"{path.name} 규칙 오류:\n  " + "\n  ".join(problems))
    return BodyRules.from_document(document)


@dataclass(frozen=True)
class WeatherWeights:
    discourage: int = -40
    encourage: int = 12


@dataclass(frozen=True)
class WeatherBand:
    label: str
    hint: str = ""
    minimum: float | None = None
    maximum: float | None = None
    discourage: tuple[Rule, ...] = ()
    encourage: tuple[Rule, ...] = ()

    def contains(self, celsius: float) -> bool:
        if self.minimum is not None and celsius < self.minimum:
            return False
        return self.maximum is None or celsius < self.maximum


@dataclass(frozen=True)
class WeatherRules:
    schema_version: str
    weights: WeatherWeights
    bands: tuple[WeatherBand, ...]

    def band_for(self, celsius: float | None) -> WeatherBand | None:
        if celsius is None:
            return None
        return next((band for band in self.bands if band.contains(celsius)), None)

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> WeatherRules:
        raw_weights = {
            key: value
            for key, value in (document.get("weights") or {}).items()
            if key != "note"
        }
        return cls(
            schema_version=str(document.get("schema_version") or ""),
            weights=WeatherWeights(**raw_weights),
            bands=tuple(
                WeatherBand(
                    label=str(row.get("label") or ""),
                    hint=str(row.get("hint") or ""),
                    minimum=row.get("min"),
                    maximum=row.get("max"),
                    discourage=_parse_rules(row.get("discourage")),
                    encourage=_parse_rules(row.get("encourage")),
                )
                for row in document.get("bands") or []
            ),
        )


def validate_weather_rules(document: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    bands = document.get("bands") or []
    for index, band in enumerate(bands):
        where = f"bands[{index}]({band.get('label', '?')})"
        problems.extend(_validate_rows(band.get("discourage"), f"{where}.discourage"))
        problems.extend(_validate_rows(band.get("encourage"), f"{where}.encourage"))
        if band.get("min") is None and band.get("max") is None:
            problems.append(f"{where}: min/max가 모두 없어 모든 기온에 걸린다")

    bounded = sorted(
        (band for band in bands if band.get("min") is not None),
        key=lambda band: band["min"],
    )
    for lower, upper in pairwise(bounded):
        if lower.get("max") is not None and lower["max"] != upper["min"]:
            problems.append(
                f"기온 구간 사이에 틈: {lower.get('label')} max={lower['max']} "
                f"vs {upper.get('label')} min={upper['min']}"
            )
    return problems


@lru_cache(maxsize=1)
def load_weather_rules() -> WeatherRules:
    path = RULES_DIR / "weather_rules.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_weather_rules(document)
    if problems:
        raise RuleError(f"{path.name} 규칙 오류:\n  " + "\n  ".join(problems))
    return WeatherRules.from_document(document)
