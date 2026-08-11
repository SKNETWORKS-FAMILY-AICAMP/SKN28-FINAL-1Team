"""신체 실측 → 체형 프로파일 (골든셋 가이드 3장의 3축 판정).

가이드는 세 축을 동시에 판정하고 교집합을 취하라고 한다.

    ➊ 가로축  5대 실루엣 (모래시계 / 역삼각 / 삼각 / 직사각 / 라운드)
    ➋ 체격    BMI 밴드 (저체중 / 표준 / 과체중 / 비만)
    ➌ 세로축  3대 세부 비율 (목길이 · 허벅지종아리 · 상하체)

현실의 제약이 하나 있다. `BodyMeasurement`의 상세 둘레는 **전부 선택 입력**이라
대부분의 사용자에게 어깨·허리·엉덩이가 없다. 그래서 판정은 "가능한 만큼만" 하고,
무엇을 근거로 무엇을 판정했는지 `known`/`missing`에 남긴다. 판정하지 못한 축은
`UNKNOWN`이며, 규칙 적용 단계에서 그 축의 규칙은 통째로 건너뛴다 — 모르는 값을
기본값으로 메우면 사용자가 겪는 건 '틀린 추천'이지 '추천 없음'이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

UNKNOWN = "unknown"

# ── 실루엣 ──────────────────────────────────────────────
HOURGLASS = "hourglass"          # 모래시계형
INVERTED_TRIANGLE = "inverted"   # 역삼각형 (어깨 발달)
TRIANGLE = "triangle"            # 삼각형 (하체 발달)
RECTANGLE = "rectangle"          # 직사각형
ROUND = "round"                  # 라운드형 (허리 발달)

SILHOUETTE_LABELS = {
    HOURGLASS: "모래시계형",
    INVERTED_TRIANGLE: "역삼각형",
    TRIANGLE: "삼각형",
    RECTANGLE: "직사각형",
    ROUND: "라운드형",
    UNKNOWN: "미판정",
}

# ── BMI 밴드 (대한비만학회 기준) ────────────────────────
UNDERWEIGHT, NORMAL, OVERWEIGHT, OBESE = "underweight", "normal", "overweight", "obese"
BMI_LABELS = {
    UNDERWEIGHT: "저체중",
    NORMAL: "표준",
    OVERWEIGHT: "과체중",
    OBESE: "비만",
    UNKNOWN: "미판정",
}

#: 가슴/엉덩이 **둘레** 차이가 이 비율 안이면 '균형'으로 본다. 실측 오차와 옷
#: 위에서 재는 현실을 감안한 폭이다. 좁히면 대부분이 역삼각/삼각으로 갈린다.
#:
#: 예전에는 여기에 어깨너비를 넣었다. 어깨너비(44cm)와 엉덩이둘레(98cm)는
#: 애초에 비교할 수 있는 값이 아니라 spread가 언제나 -0.4~-0.6이 나왔고,
#: **모든 사용자가 삼각형으로 판정**됐다. 체형을 바꿔도 추천이 그대로이던
#: 원인 중 하나다. 표준 체형 분류가 쓰는 축도 가슴·허리·엉덩이 둘레 3개다.
_BALANCE_TOLERANCE = 0.05
#: 허리가 가슴·엉덩이 평균 대비 이 비율보다 작으면 '잘록'으로 본다.
_WAIST_DEFINED = 0.75
#: 허리가 이 비율을 넘으면 허리 발달(라운드형)로 본다.
_WAIST_DOMINANT = 0.95
#: 어깨너비 / 가슴둘레. 어깨는 실루엣 판정에서 빠졌지만 버리지는 않는다 —
#: 어깨 발달은 실제로 다른 축이라 ratios의 보조 신호로 남긴다.
_SHOULDER_BROAD = 0.46
_SHOULDER_NARROW = 0.40


@dataclass(frozen=True)
class BodyProfile:
    silhouette: str = UNKNOWN
    bmi_band: str = UNKNOWN
    bmi: float | None = None
    #: 세부 비율 축 → "long" / "average" / "short" 등. 판정 못 한 축은 아예 없다.
    ratios: dict[str, str] = field(default_factory=dict)
    #: 판정에 실제로 쓴 치수 이름
    known: tuple[str, ...] = ()
    #: 있었으면 더 정확했을 치수 이름
    missing: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """세 축 모두 판정하지 못했는가. 규칙을 아예 적용할 수 없는 상태."""
        return (
            self.silhouette == UNKNOWN
            and self.bmi_band == UNKNOWN
            and not self.ratios
        )

    def describe(self) -> str:
        """사람이 읽는 한 줄. Agent 설명 생성의 입력으로도 쓴다."""
        parts = [SILHOUETTE_LABELS.get(self.silhouette, "미판정")]
        if self.bmi_band != UNKNOWN:
            parts.append(BMI_LABELS[self.bmi_band])
        for axis, value in sorted(self.ratios.items()):
            parts.append(f"{axis}:{value}")
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


def _silhouette(chest: float, waist: float | None, hip: float) -> str:
    """가슴·허리·엉덩이 **둘레**로 5대 실루엣을 가른다.

    순서가 중요하다. **허리 우세를 먼저** 본다. 예전에는 가슴-엉덩이 균형을
    먼저 봐서, 허리 108cm에 가슴 110 / 엉덩이 100인 사람이 명백한 라운드형인데
    역삼각형으로 빠졌다. 라운드형은 상하 균형과 무관하게 성립하는 축이다.
    """
    reference = (chest + hip) / 2
    if waist is not None and waist / reference >= _WAIST_DOMINANT:
        return ROUND

    spread = (chest - hip) / max(chest, hip)
    if spread > _BALANCE_TOLERANCE:
        return INVERTED_TRIANGLE
    if spread < -_BALANCE_TOLERANCE:
        return TRIANGLE

    if waist is None:
        # 가슴과 엉덩이가 균형이라는 것까지만 안다. 허리를 모르면 모래시계와
        # 직사각형을 가를 수 없어 더 흔한 쪽(직사각형)으로 두지 않고 미판정한다.
        return UNKNOWN

    if waist / reference <= _WAIST_DEFINED:
        return HOURGLASS
    return RECTANGLE


def _ratios(measure: dict[str, float]) -> dict[str, str]:
    """세부 비율 3축. 각 축은 필요한 치수가 다 있을 때만 판정한다."""
    result: dict[str, str] = {}

    # 허벅지/종아리 — 팬츠 핏 결정에 개입한다.
    thigh, calf = measure.get("thigh"), measure.get("calf")
    if thigh and calf:
        ratio = thigh / calf
        result["leg_volume"] = (
            "thigh_dominant" if ratio >= 1.55
            else "balanced" if ratio >= 1.35
            else "calf_dominant"
        )

    # 어깨 — 실루엣 판정에서는 뺐지만(가슴둘레와 단위가 다르다) 어깨 발달은
    # 실제로 다른 축이다. 같은 둘레 체형이라도 어깨가 넓으면 오버핏 상의가
    # 다르게 앉는다. 가슴둘레 대비 비율로 남겨 규칙 쪽에서 쓸 수 있게 한다.
    shoulder, chest = measure.get("shoulder"), measure.get("chest")
    if shoulder and chest:
        ratio = shoulder / chest
        result["shoulder_width"] = (
            "broad" if ratio >= _SHOULDER_BROAD
            else "narrow" if ratio <= _SHOULDER_NARROW
            else "balanced"
        )

    # 상하체 — 하이웨이스트 등 분할선 조절에 개입한다.
    height, hip = measure.get("height"), measure.get("hip")
    if height and hip:
        # 엉덩이둘레만으로 다리 길이를 알 수는 없다. 가이드가 요구하는 축이지만
        # 지금 스키마로는 대용치가 없어 판정하지 않는다.
        pass

    # 목길이 — 카라·넥라인 필터에 개입해야 하지만, 목길이를 잴 컬럼도
    # 넥라인 태그도 없다. 축을 비워 두고 규칙 쪽에서 건너뛴다.
    return result


def build_profile(measurement: dict[str, Any] | None) -> BodyProfile:
    """`outfit_context._serialize_measurement()`가 만든 dict를 그대로 받는다."""
    if not measurement:
        return BodyProfile(missing=("height", "weight", "chest", "waist", "hip"))

    measure = {
        name: value
        for name in ("height", "weight", "shoulder", "chest", "waist", "hip",
                     "thigh", "calf", "arm")
        if (value := _number(measurement.get(name))) is not None
    }

    bmi = None
    bmi_band = UNKNOWN
    if "height" in measure and "weight" in measure:
        bmi = round(measure["weight"] / (measure["height"] / 100) ** 2, 1)
        bmi_band = _bmi_band(bmi)

    silhouette = UNKNOWN
    if "chest" in measure and "hip" in measure:
        silhouette = _silhouette(
            measure["chest"], measure.get("waist"), measure["hip"]
        )

    ratios = _ratios(measure)

    # chest가 빠지면 실루엣이 통째로 미판정이 된다. 프론트가 "가슴둘레를
    # 입력하면 더 정확해져요"를 띄울 수 있도록 목록 앞쪽에 둔다.
    wanted = ("height", "weight", "chest", "waist", "hip", "shoulder", "thigh", "calf")
    return BodyProfile(
        silhouette=silhouette,
        bmi_band=bmi_band,
        bmi=bmi,
        ratios=ratios,
        known=tuple(name for name in wanted if name in measure),
        missing=tuple(name for name in wanted if name not in measure),
    )
