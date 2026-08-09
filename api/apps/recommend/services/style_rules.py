"""체형·색상 규칙표 로딩과 조회.

가이드 7장 Q3이 규칙 JSON을 "시스템의 유일한 판단 원천"으로 못박았다. 그래서
규칙은 코드가 아니라 `apps/recommend/rules/*.json`에 있고, 이 모듈은 그것을 읽어
쓰기 좋은 모양으로 바꾸는 일만 한다. 판단 기준을 바꾸려면 JSON만 고치면 된다.

읽을 때 값을 검증하는 이유가 있다. 규칙의 `fit: "레귤귤핏"` 같은 오타는 예외를
내지 않는다 — 그냥 어떤 아이템과도 매칭되지 않아 '규칙이 없는 것'처럼 조용히
동작한다. 실제로 이 파일을 처음 쓸 때 그 오타를 냈다. 그래서 기동 시 태그 어휘와
대조해 알려지지 않은 라벨을 찾아낸다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: 규칙 JSON 위치. 가이드는 golden-set/body/rules/ 를 적었지만, 요청 시점에
#: Django가 읽는 파일이라 소비자(recommend) 옆에 두어 로딩 경로를 단순하게 했다.
RULES_DIR = Path(__file__).resolve().parent.parent / "rules"

#: 규칙에 쓸 수 있는 태그 값. image-processor/pipeline/taxonomy.py와 같아야 한다.
#: golden_set은 Django 없이 도는 패키지라 그쪽을 import할 수 없어 복제한다 —
#: point_ids.POINT_NAMESPACE와 같은 이유다. 한쪽을 바꾸면 다른 쪽도 바꿔야 한다.
KNOWN_VALUES: dict[str, frozenset[str]] = {
    "category_large": frozenset({
        "상의", "하의", "아우터", "원피스/세트",
        "신발", "가방", "액세서리", "언더웨어/이너웨어",
    }),
    "fit": frozenset({"오버핏", "레귤러핏", "슬림핏", "와이드핏"}),
    "length": frozenset({"크롭", "기본", "롱"}),
    "sleeve": frozenset({"반팔", "긴팔", "민소매"}),
    "pattern": frozenset({
        "무지", "체크", "스트라이프", "도트", "플로럴", "그래픽/로고", "카모", "애니멀",
    }),
    "material": frozenset({
        "코튼", "데님", "니트", "울", "린넨", "레더", "나일론", "폴리에스터",
        "시폰", "코듀로이", "트위드", "퍼/무스탕", "패딩충전재",
    }),
    "color": frozenset({
        "화이트", "블랙", "그레이", "네이비", "블루", "스카이블루", "레드", "핑크",
        "오렌지", "옐로우", "그린", "카키", "브라운", "베이지", "아이보리", "퍼플", "멀티",
    }),
}

#: 규칙 한 줄에서 조건이 아닌 키 (설명·강도)
_META_KEYS = frozenset({"reason", "hard", "score", "rule", "label", "note"})


@dataclass(frozen=True)
class Rule:
    """규칙 한 줄. `match`가 전부 일치하면 발동한다."""

    match: dict[str, str]
    reason: str
    hard: bool = False

    def matches(self, tags: dict[str, object]) -> bool:
        """아이템 태그가 이 규칙의 조건을 전부 만족하는가."""
        for field, expected in self.match.items():
            value = tags.get(field)
            if isinstance(value, (list, tuple, set)):
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


class RuleError(ValueError):
    """규칙 파일이 태그 어휘와 맞지 않는다."""


def _parse_rules(rows: list[dict], *, where: str) -> tuple[Rule, ...]:
    parsed: list[Rule] = []
    for row in rows or []:
        match = {k: v for k, v in row.items() if k not in _META_KEYS}
        if not match:
            # 조건이 없으면 모든 아이템에 발동한다. 색상 조합 규칙처럼 이름으로만
            # 식별되는 항목(`rule`)은 여기 오지 않는다 — 별도 경로로 읽는다.
            continue
        parsed.append(
            Rule(
                match=match,
                reason=str(row.get("reason", "")),
                hard=bool(row.get("hard", False)),
            )
        )
    return tuple(parsed)


def validate_rules(document: dict) -> list[str]:
    """알려지지 않은 태그 필드·값을 찾아 사람이 읽을 문장으로 돌려준다.

    빈 리스트면 정상. 예외를 던지지 않고 목록을 주는 이유는, 호출부가 기동을
    막을지 로그만 남길지 고를 수 있게 하기 위해서다.
    """
    problems: list[str] = []

    def check(rows: list[dict], where: str) -> None:
        for index, row in enumerate(rows or []):
            for field, value in row.items():
                if field in _META_KEYS:
                    continue
                allowed = KNOWN_VALUES.get(field)
                if allowed is None:
                    problems.append(f"{where}[{index}]: 알 수 없는 태그 필드 '{field}'")
                elif value not in allowed:
                    problems.append(
                        f"{where}[{index}]: '{field}'에 없는 값 '{value}' "
                        f"(가능: {', '.join(sorted(allowed))})"
                    )

    for axis in ("silhouette", "bmi_band"):
        for key, block in (document.get(axis) or {}).items():
            check(block.get("prefer"), f"{axis}.{key}.prefer")
            check(block.get("avoid"), f"{axis}.{key}.avoid")

    for ratio_axis, values in (document.get("ratios") or {}).items():
        for key, block in values.items():
            check(block.get("prefer"), f"ratios.{ratio_axis}.{key}.prefer")
            check(block.get("avoid"), f"ratios.{ratio_axis}.{key}.avoid")

    return problems


@lru_cache(maxsize=1)
def load_body_rules() -> "BodyRules":
    path = RULES_DIR / "body_fit_rules.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    problems = validate_rules(document)
    if problems:
        raise RuleError(
            f"{path.name}이 태그 어휘와 맞지 않습니다:\n  " + "\n  ".join(problems)
        )
    return BodyRules.from_document(document)


@lru_cache(maxsize=1)
def load_color_rules() -> dict:
    return json.loads((RULES_DIR / "color_rules.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class BodyRules:
    schema_version: str
    weights: Weights
    silhouette: dict[str, AxisRules]
    bmi_band: dict[str, AxisRules]
    ratios: dict[str, dict[str, AxisRules]]

    @classmethod
    def from_document(cls, document: dict) -> "BodyRules":
        def axis(block: dict, where: str) -> AxisRules:
            return AxisRules(
                prefer=_parse_rules(block.get("prefer"), where=f"{where}.prefer"),
                avoid=_parse_rules(block.get("avoid"), where=f"{where}.avoid"),
            )

        weights_raw = {
            k: v for k, v in (document.get("weights") or {}).items() if k != "note"
        }
        return cls(
            schema_version=str(document.get("schema_version", "")),
            weights=Weights(**weights_raw),
            silhouette={
                key: axis(block, f"silhouette.{key}")
                for key, block in (document.get("silhouette") or {}).items()
            },
            bmi_band={
                key: axis(block, f"bmi_band.{key}")
                for key, block in (document.get("bmi_band") or {}).items()
            },
            ratios={
                ratio_axis: {
                    key: axis(block, f"ratios.{ratio_axis}.{key}")
                    for key, block in values.items()
                }
                for ratio_axis, values in (document.get("ratios") or {}).items()
            },
        )

    def for_profile(self, profile) -> AxisRules:
        """프로파일에 해당하는 규칙만 모아 하나로 합친다.

        판정하지 못한 축(UNKNOWN)은 통째로 건너뛴다 — 모르는 값을 기본값으로
        메우면 사용자는 '추천 없음'이 아니라 '틀린 추천'을 받는다.
        """
        prefer: list[Rule] = []
        avoid: list[Rule] = []

        for block in (
            self.silhouette.get(profile.silhouette),
            self.bmi_band.get(profile.bmi_band),
            *(
                self.ratios.get(axis, {}).get(value)
                for axis, value in profile.ratios.items()
            ),
        ):
            if block is None:
                continue
            prefer.extend(block.prefer)
            avoid.extend(block.avoid)

        return AxisRules(prefer=tuple(prefer), avoid=tuple(avoid))
