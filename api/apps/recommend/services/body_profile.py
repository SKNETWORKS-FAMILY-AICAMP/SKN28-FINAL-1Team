"""신체 실측값을 추천 규칙에 사용할 수 있는 체형 프로필로 변환한다.

상세 둘레는 선택 입력이므로 확인할 수 없는 축은 추정하지 않는다. 잘못 채운
기본값으로 추천을 왜곡하는 것보다 해당 규칙을 적용하지 않는 편이 안전하다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UNKNOWN = "unknown"

HOURGLASS = "hourglass"
INVERTED_TRIANGLE = "inverted"
TRIANGLE = "triangle"
RECTANGLE = "rectangle"
ROUND = "round"

UNDERWEIGHT = "underweight"
NORMAL = "normal"
OVERWEIGHT = "overweight"
OBESE = "obese"

SILHOUETTE_LABELS = {
    HOURGLASS: "모래시계형",
    INVERTED_TRIANGLE: "역삼각형",
    TRIANGLE: "삼각형",
    RECTANGLE: "직사각형",
    ROUND: "라운드형",
    UNKNOWN: "미판정",
}
BMI_LABELS = {
    UNDERWEIGHT: "저체중",
    NORMAL: "표준",
    OVERWEIGHT: "과체중",
    OBESE: "비만",
    UNKNOWN: "미판정",
}

_BALANCE_TOLERANCE = 0.05
_WAIST_DEFINED = 0.75
_WAIST_DOMINANT = 0.95


@dataclass(frozen=True)
class BodyProfile:
    silhouette: str = UNKNOWN
    bmi_band: str = UNKNOWN
    bmi: float | None = None
    ratios: dict[str, str] = field(default_factory=dict)
    known: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return (
            self.silhouette == UNKNOWN and self.bmi_band == UNKNOWN and not self.ratios
        )

    def describe(self) -> str:
        parts = [SILHOUETTE_LABELS.get(self.silhouette, "미판정")]
        if self.bmi_band != UNKNOWN:
            parts.append(BMI_LABELS.get(self.bmi_band, "미판정"))
        parts.extend(f"{axis}:{value}" for axis, value in sorted(self.ratios.items()))
        return " · ".join(parts)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _bmi_band(bmi: float) -> str:
    if bmi < 18.5:
        return UNDERWEIGHT
    if bmi < 23.0:
        return NORMAL
    if bmi < 25.0:
        return OVERWEIGHT
    return OBESE


def _silhouette(shoulder: float, waist: float | None, hip: float) -> str:
    spread = (shoulder - hip) / max(shoulder, hip)
    if spread > _BALANCE_TOLERANCE:
        return INVERTED_TRIANGLE
    if spread < -_BALANCE_TOLERANCE:
        return TRIANGLE
    if waist is None:
        return UNKNOWN

    reference = (shoulder + hip) / 2
    ratio = waist / reference
    if ratio >= _WAIST_DOMINANT:
        return ROUND
    if ratio <= _WAIST_DEFINED:
        return HOURGLASS
    return RECTANGLE


def _ratios(measurement: dict[str, float]) -> dict[str, str]:
    thigh = measurement.get("thigh")
    calf = measurement.get("calf")
    if not thigh or not calf:
        return {}
    ratio = thigh / calf
    if ratio >= 1.55:
        value = "thigh_dominant"
    elif ratio >= 1.35:
        value = "balanced"
    else:
        value = "calf_dominant"
    return {"leg_volume": value}


def build_profile(measurement: dict[str, Any] | None) -> BodyProfile:
    """채팅 컨텍스트의 신체 측정 dict를 부분 정보에 안전하게 변환한다."""
    wanted = ("height", "weight", "shoulder", "waist", "hip", "thigh", "calf")
    if not measurement:
        return BodyProfile(missing=wanted)

    values = {
        name: number
        for name in (*wanted, "chest", "arm")
        if (number := _number(measurement.get(name))) is not None
    }
    bmi = None
    bmi_band = UNKNOWN
    if "height" in values and "weight" in values:
        bmi = round(values["weight"] / (values["height"] / 100) ** 2, 1)
        bmi_band = _bmi_band(bmi)

    silhouette = UNKNOWN
    if "shoulder" in values and "hip" in values:
        silhouette = _silhouette(
            values["shoulder"],
            values.get("waist"),
            values["hip"],
        )

    return BodyProfile(
        silhouette=silhouette,
        bmi_band=bmi_band,
        bmi=bmi,
        ratios=_ratios(values),
        known=tuple(name for name in wanted if name in values),
        missing=tuple(name for name in wanted if name not in values),
    )
