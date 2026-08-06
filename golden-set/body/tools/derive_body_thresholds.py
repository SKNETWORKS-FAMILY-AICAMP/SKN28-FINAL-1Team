"""사이즈코리아 실측 182명에서 체형 분류 임계값을 산출한다.

체형 규칙의 숫자를 사람이 감으로 정하면 "왜 어깨/엉덩이 0.44가 넓은 건가"에
답할 수 없다. 임계값을 **표본 백분위(tertile)**로 정의하면 근거가 데이터가 되고,
표본이 늘어나면 같은 스크립트로 갱신된다 — 이것이 이 파일이 존재하는 이유다.

출력: golden-set/body/rules/body_shape_thresholds.json

실행:
    python golden-set/body/tools/derive_body_thresholds.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "ml/body_measurement/data/labels/sizekorea_vlm_182_labels.csv"
OUT = ROOT / "golden-set/body/rules/body_shape_thresholds.json"

# 분류에 쓰는 두 축. 둘 다 "키에 무관한 비율"이라 성별 내에서 바로 비교 가능하다.
RATIOS = {
    "shoulder_hip": ("shoulder", "hip"),  # 상·하체 폭 균형 → 역삼각/삼각
    "waist_hip": ("waist", "hip"),        # 허리 굴곡 → 모래시계/라운드
}
# 둘레 컬럼의 물리적 하한(cm). 원본에 chest=8.2 같은 입력 오류가 섞여 있어,
# 이 값 미만은 결측으로 보고 제외한다. shoulder는 둘레가 아니라 너비(30~43cm)라
# 이 검사 대상이 아니다.
CIRCUMFERENCE_COLS = ["chest", "waist", "hip"]
MIN_CIRCUMFERENCE = 40.0


def load() -> pd.DataFrame:
    df = pd.read_csv(SRC)
    bad = (df[CIRCUMFERENCE_COLS] < MIN_CIRCUMFERENCE).any(axis=1)
    if bad.any():
        print(f"[warn] 이상치 {int(bad.sum())}행 제외: {df.loc[bad, 'subject_id'].tolist()}")
    df = df.loc[~bad].copy()
    for name, (a, b) in RATIOS.items():
        df[name] = df[a] / df[b]
    df["bmi"] = df["weight"] / (df["height"] / 100) ** 2
    return df


def classify(row, th: dict) -> str:
    """분류 순서가 곧 정의다. 위에서부터 먼저 걸리는 규칙이 이긴다.

    허리를 먼저 보는 이유: 허리가 엉덩이 대비 두꺼우면 어깨 폭과 무관하게
    실루엣 과제가 '허리 라인 분산'으로 바뀌기 때문이다.
    """
    g = th[row["gender"]]
    if row["waist_hip"] >= g["waist_hip"]["p67"]:
        return "round"
    if row["shoulder_hip"] >= g["shoulder_hip"]["p67"]:
        return "inverted_triangle"
    if row["shoulder_hip"] <= g["shoulder_hip"]["p33"]:
        return "triangle"
    if row["waist_hip"] <= g["waist_hip"]["p33"]:
        return "hourglass"
    return "rectangle"


def main() -> None:
    df = load()
    thresholds = {
        gender: {
            name: {
                "p33": round(sub[name].quantile(1 / 3), 4),
                "p50": round(sub[name].median(), 4),
                "p67": round(sub[name].quantile(2 / 3), 4),
            }
            for name in RATIOS
        }
        for gender, sub in df.groupby("gender")
    }

    df["body_shape"] = df.apply(classify, axis=1, th=thresholds)
    dist = {
        gender: sub["body_shape"].value_counts().to_dict()
        for gender, sub in df.groupby("gender")
    }

    payload = {
        "source": str(SRC.relative_to(ROOT)).replace("\\", "/"),
        "sample_size": {g: int(len(s)) for g, s in df.groupby("gender")},
        "method": "성별 내 tertile(p33/p67). 임계값은 절대 기준이 아니라 표본 상대 위치다.",
        "ratios": {k: f"{a}/{b}" for k, (a, b) in RATIOS.items()},
        "priority": ["round", "inverted_triangle", "triangle", "hourglass", "rectangle"],
        "thresholds": thresholds,
        "distribution": dist,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
