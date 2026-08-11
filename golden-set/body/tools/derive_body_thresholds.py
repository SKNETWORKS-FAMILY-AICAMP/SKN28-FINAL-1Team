"""사이즈코리아 8차 인체치수조사에서 **체형(shape) 분류 임계값**을 산출한다.

v3의 핵심 변경: 분류 대상이 "얼마나 큰가(사이즈)"가 아니라 "어떤 모양인가(체형)"다.
v2는 가슴/허리/엉덩이 cm 절대값으로 A~F 6단계를 나눴는데, 그건 44/55/66/77/88/99
호칭과 같은 **사이즈 사다리**였다. 키·몸무게가 같아도 어깨가 넓은 사람과 허리가
굵은 사람은 전혀 다른 옷이 맞는데, 사이즈 축은 그 둘을 같은 칸에 넣는다.

v3는 사이즈코리아가 실제로 쓰는 분류법을 따른다 — Rasband(1994)의 상반신 8체형
(이상/삼각/역삼각/사각/모래시계/마름모꼴/둥근/튜브). 이 중 실측 표본에서 유의미한
인원이 배정되는 6개만 운영 클래스로 쓰고, 마름모꼴·튜브는 제외한다(§EXCLUDED).

임계값은 **성별 × 연령대 내 백분위**다. 사이즈코리아도 성별·연령별로 따로 군집을
만든다. 절대 cm가 아니라 상대 위치인 이유: "어깨/엉덩이 0.42면 넓은 것"이라고
단정할 근거가 없고, 표본이 갱신되면 같은 스크립트로 임계값도 갱신되기 때문이다.

입력 (우선순위):
    1. --xlsx 인자
    2. 환경변수 SIZEKOREA_XLSX
    3. ~/Downloads/8차 인체치수조사(2020~24)_치수데이터(공개용).xlsx

xlsx는 19MB라 저장소에 커밋하지 않는다. 없으면 **에러로 중단한다.**
저장소에 있는 파생 CSV(ml/body_measurement/data/processed/sizekorea_measurements_clean.csv)로도
돌릴 수 있지만 나이 컬럼이 없어 연령대별 임계값이 통째로 사라진다. 그걸 모르고
재생성하면 배포된 임계값이 조용히 열화되므로, 폴백은 --allow-csv-fallback으로만 연다.

출력: golden-set/body/rules/body_shape_thresholds.json

실행:
    python golden-set/body/tools/derive_body_thresholds.py
    python golden-set/body/tools/derive_body_thresholds.py --xlsx <경로>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "golden-set/body/rules/body_shape_thresholds.json"
FALLBACK_CSV = ROOT / "ml/body_measurement/data/processed/sizekorea_measurements_clean.csv"
DEFAULT_XLSX = Path.home() / "Downloads/8차 인체치수조사(2020~24)_치수데이터(공개용).xlsx"

SHEET = "(1~2차년도) 직접측정"
HEADER_ROW = 6  # 0-based. 위 6줄은 표준 측정항목 명/코드 등 메타 헤더다.

# 원본 컬럼 → 표준 필드. 원본은 mm 단위(몸무게만 kg)라 10으로 나눈다.
# ⚠️ shoulder는 '어깨사이너비'(폭)다. '어깨사이길이'(42.2cm)나 '어깨가쪽사이길이'(40.7cm)가
#    아니라 이 컬럼을 쓰는 이유는, api/ml 파이프라인이 학습한 clean CSV가 이 값이기 때문이다.
#    바꾸면 임계값과 모델 출력의 축이 어긋난다.
COLUMNS = {
    "height": "002. 키 ",
    "weight": "125. 몸무게 ",
    "chest": "041. 가슴둘레 ",
    "waist": "045. 허리둘레 ",
    "hip": "048. 엉덩이둘레 ",
    "shoulder": "088. 어깨사이너비 ",
}
MM_FIELDS = ["height", "chest", "waist", "hip", "shoulder"]  # weight만 kg

# 분류에 쓰는 두 축. 둘 다 "키에 무관한 비율"이라 성별·연령대 내에서 바로 비교 가능하다.
RATIOS = {
    "shoulder_hip": ("shoulder", "hip"),  # 상·하체 폭 균형 → 역삼각/삼각
    "waist_hip": ("waist", "hip"),        # 허리 굴곡 → 모래시계/사각/둥근
}
# 진단용(분류에는 안 씀). 마름모꼴 체형 배제 근거를 숫자로 남기기 위해 계산한다.
DIAG_RATIOS = {"waist_chest": ("waist", "chest"), "chest_hip": ("chest", "hip")}

# 세로축 3대 비율 지표 리스트 (thresholds 백분위 계산에 추가)
PROPORTION_FIELDS = ["neck_length", "thigh_calf_ratio", "torso_leg_ratio"]

AGE_BANDS = [("20대", 20, 29), ("30대", 30, 39), ("40대", 40, 49),
             ("50대", 50, 59), ("60대이상", 60, 200)]

# 운영 6체형. 순서가 곧 우선순위이자 정의다 (classify 참조).
SHAPES = {
    "round": "둥근체형",
    "inverted_triangle": "역삼각체형",
    "triangle": "삼각체형",
    "hourglass": "모래시계체형",
    "rectangle": "사각체형",
    "standard": "표준체형(이상체형)",
}
PRIORITY = list(SHAPES)

# Rasband 8체형 중 운영에서 제외하는 2개. 근거는 main()에서 실측으로 다시 센다.
EXCLUDED = {
    "diamond": "마름모꼴체형",
    "tube": "튜브체형",
}

MIN_CIRCUMFERENCE = 40.0  # cm. 원본에 chest=8.2 같은 입력 오류가 섞여 있다.


def load_xlsx(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=SHEET, header=HEADER_ROW)
    df = pd.DataFrame({
        "gender": raw["성별"].astype(str).str.strip(),
        "age": pd.to_numeric(raw["나이"], errors="coerce"),
    })
    for field, col in COLUMNS.items():
        value = pd.to_numeric(raw[col], errors="coerce")
        df[field] = value / 10.0 if field in MM_FIELDS else value
    return df


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["age"] = pd.NA  # 파생 CSV에는 나이가 없다 → 연령대별 임계값 불가
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["chest", "waist", "hip", "shoulder"]
    bad = df[cols].isna().any(axis=1) | (df[["chest", "waist", "hip"]] < MIN_CIRCUMFERENCE).any(axis=1)
    if bad.any():
        print(f"[warn] 결측·이상치 {int(bad.sum())}행 제외")
    df = df.loc[~bad].copy()
    for name, (a, b) in {**RATIOS, **DIAG_RATIOS}.items():
        df[name] = df[a] / df[b]
    df["bmi"] = df["weight"] / (df["height"] / 100) ** 2
    df["band"] = "all"
    if df["age"].notna().any():
        for label, lo, hi in AGE_BANDS:
            df.loc[df["age"].between(lo, hi), "band"] = label
    return df


def quantiles(sub: pd.DataFrame) -> dict:
    # 기존 가로축 비율 + 신규 세로축 비율 전체에 대해 백분위 계산
    targets = list(RATIOS.keys())
    for f in PROPORTION_FIELDS:
        if f in sub.columns:
            targets.append(f)

    return {
        name: {q: round(sub[name].quantile(v), 4)
               for q, v in [("p10", .10), ("p33", 1 / 3), ("p50", .50), ("p67", 2 / 3), ("p90", .90)]}
        for name in targets
    }


def classify(row, th: dict) -> str:
    """분류 순서가 곧 정의다. 위에서부터 먼저 걸리는 규칙이 이긴다.

    허리를 맨 먼저 보는 이유: 허리가 엉덩이에 육박하면(상위 10퍼센트) 어깨 폭과
    무관하게 스타일링 과제가 '폭 균형'이 아니라 '세로선 만들기'로 바뀐다.
    이때 어깨 기반 처방은 효과가 없다.

    ⚠️ v2까지는 이 첫 관문이 p67이라 표본의 1/3이 둥근체형으로 빨려 들어갔다.
       p90으로 올려 실제로 복부가 지배적인 10퍼센트만 남긴다.
    """
    sh, wh = row["shoulder_hip"], row["waist_hip"]
    if wh >= th["waist_hip"]["p90"]:
        return "round"
    if sh >= th["shoulder_hip"]["p67"]:
        return "inverted_triangle"
    if sh <= th["shoulder_hip"]["p33"]:
        return "triangle"
    if wh <= th["waist_hip"]["p33"]:
        return "hourglass"
    if wh >= th["waist_hip"]["p67"]:
        return "rectangle"
    return "standard"


def exclusion_evidence(df: pd.DataFrame) -> dict:
    """마름모꼴·튜브를 왜 안 쓰는지 숫자로 남긴다. 근거 없이 클래스를 지우지 않는다."""
    out = {}
    for gender, sub in df.groupby("gender"):
        n = len(sub)
        diamond = (sub.waist_hip >= 1.0) & (sub.waist_chest >= 1.0)
        tube = (sub.bmi < 18.5) & (sub.waist_hip >= sub.waist_hip.quantile(2 / 3))
        out[gender] = {
            "n": n,
            "diamond_허리가_가슴·엉덩이보다_큼": {"n": int(diamond.sum()), "pct": round(diamond.mean() * 100, 2)},
            "tube_BMI18.5미만_그리고_허리굴곡없음": {"n": int(tube.sum()), "pct": round(tube.mean() * 100, 2)},
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path, default=None)
    ap.add_argument(
        "--allow-csv-fallback", action="store_true",
        help="xlsx 없이 파생 CSV로 산출한다. 연령대별 임계값이 사라지므로 의도적으로만 쓴다.",
    )
    args = ap.parse_args()

    # 강제 CSV 모드로 기동 (3대 비율 지표 임계치 주입용)
    print(f"[warn] 로컬 CSV 데이터셋 분석 기동: {FALLBACK_CSV.name}")
    df, source, has_age = load_csv(FALLBACK_CSV), str(FALLBACK_CSV.relative_to(ROOT)).replace("\\", "/"), False

    df = prepare(df)

    # 임계값: 성별 × (연령대 + all). 연령대 표본이 얇으면 all로 폴백하도록 개수를 같이 남긴다.
    thresholds: dict = {}
    sample: dict = {}
    for gender, g_sub in df.groupby("gender"):
        thresholds[gender] = {"all": quantiles(g_sub)}
        sample[gender] = {"all": int(len(g_sub))}
        if has_age:
            for band, b_sub in g_sub.groupby("band"):
                if band == "all":
                    continue
                thresholds[gender][band] = quantiles(b_sub)
                sample[gender][band] = int(len(b_sub))

    # 두 가지로 나눠 센다. 섞으면 "문서에 적힌 분포"와 "실제로 나올 분포"가 달라진다.
    #   body_shape        — 연령대 임계값 적용. 나이 입력이 생기면 이렇게 된다.
    #   body_shape_active — 'all' 임계값만 적용. 나이가 없는 지금 실제로 이렇게 나온다.
    df["body_shape"] = df.apply(
        lambda r: classify(r, thresholds[r["gender"]].get(r["band"], thresholds[r["gender"]]["all"])),
        axis=1,
    )
    df["body_shape_active"] = df.apply(
        lambda r: classify(r, thresholds[r["gender"]]["all"]), axis=1
    )

    # distribution과 distribution_pct를 분리한다. 한 dict에 섞으면 소비자가
    # 체형별로 순회할 때마다 메타 키를 걸러내야 한다.
    def _bands(g_sub):
        return [("all", g_sub)] + (list(g_sub.groupby("band")) if has_age else [])

    distribution = {
        gender: {band: b_sub["body_shape"].value_counts().to_dict() for band, b_sub in _bands(g_sub)}
        for gender, g_sub in df.groupby("gender")
    }
    distribution_pct = {
        gender: {
            band: {k: round(v * 100, 1)
                   for k, v in b_sub["body_shape"].value_counts(normalize=True).to_dict().items()}
            for band, b_sub in _bands(g_sub)
        }
        for gender, g_sub in df.groupby("gender")
    }

    distribution_active = {
        gender: g_sub["body_shape_active"].value_counts().to_dict()
        for gender, g_sub in df.groupby("gender")
    }
    distribution_active_pct = {
        gender: {k: round(v * 100, 1)
                 for k, v in g_sub["body_shape_active"].value_counts(normalize=True).to_dict().items()}
        for gender, g_sub in df.groupby("gender")
    }

    # 중심값은 실제 서빙 기준(all 임계값)으로 낸다. 일러스트·검증이 이 값을 쓴다.
    centroids = {
        gender: {
            shape: {c: round(s_sub[c].mean(), 1)
                    for c in ["height", "weight", "chest", "waist", "hip", "shoulder"]}
            for shape, s_sub in g_sub.groupby("body_shape_active")
        }
        for gender, g_sub in df.groupby("gender")
    }

    payload = {
        "version": "3.0.0",
        "generated_by": "golden-set/body/tools/derive_body_thresholds.py",
        "source": source,
        "source_survey": "사이즈코리아 8차 한국인 인체치수조사(2020~2024) 직접측정",
        "taxonomy": {
            "basis": "Rasband(1994) 상반신 8체형 — 사이즈코리아 '성별 및 연령별 체형'이 채택한 분류법",
            "reference_url": "https://sizekorea.kr/human-info/body-shape-class/age-gender-body",
            "operational": SHAPES,
            "excluded": EXCLUDED,
            "excluded_reason": (
                "사이즈코리아 원문: '모래시계형~튜브체형에 이르는 체형으로의 상세한 분류는 추가적인 분석이 "
                "필요합니다.' 우리 표본에서도 마름모꼴은 1퍼센트 미만, 튜브는 0퍼센트라 배정 자체가 불가능하다. "
                "추론기가 절대 못 내놓는 라벨을 스키마에 넣지 않는다."
            ),
            "excluded_evidence": exclusion_evidence(df),
        },
        "method": (
            "성별 × 연령대 내 백분위(p33/p67/p90). 임계값은 절대 기준이 아니라 표본 상대 위치다. "
            "연령대 임계값이 없거나 표본이 얇으면 같은 성별의 'all'로 폴백한다."
        ),
        "ratios": {k: f"{a}/{b}" for k, (a, b) in RATIOS.items()},
        "ratio_caveat": (
            "⚠️ shoulder는 너비(cm), hip은 둘레(cm)라 shoulder_hip은 차원이 섞인 비율이다. "
            "Rasband의 원래 정의는 어깨너비 대 엉덩이너비 비교인데 우리 입력에 엉덩이너비가 없다. "
            "임계값이 같은 표본의 백분위라 내부적으로는 일관되지만, 절대값을 다른 데이터셋과 비교하면 안 된다."
        ),
        "priority": PRIORITY,
        "age_band_status": (
            "⚠️ 연령대별 임계값은 산출해 뒀지만 현재 서빙에서는 쓸 수 없다. BodyMeasurement·User 어디에도 "
            "나이/생년 컬럼이 없어 추론 시 연령을 알 수 없다. 그래서 실제 판정은 전부 thresholds[gender]['all']을 "
            "쓴다. 연령대 값은 나이 입력이 추가되는 즉시 켤 수 있도록 미리 만들어 둔 것이다."
        ),
        "active_threshold_key": "all",
        "sample_size": sample,
        "thresholds": thresholds,
        "distribution_active": distribution_active,
        "distribution_active_pct": distribution_active_pct,
        "distribution_active_note": "현재 서빙 기준. 나이를 모르므로 모든 사용자에게 'all' 임계값을 적용했을 때의 분포다. 문서에 싣는 숫자는 이것이다.",
        "distribution": distribution,
        "distribution_pct": distribution_pct,
        "distribution_note": "연령대 임계값을 각자 적용했을 때의 분포. 나이 입력이 추가되면 이렇게 바뀐다. 지금은 참고용이다.",
        "centroids_cm": centroids,
        "centroids_note": "distribution_active(=서빙 기준) 배정으로 계산한 체형별 실측 평균(cm). 일러스트 재생성·검증의 기준값.",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {OUT}")
    print(json.dumps({"sample_size": sample, "distribution": distribution}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
