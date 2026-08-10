import argparse
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "splits" / "vlm"

TRAILING_METADATA_COLUMNS = [
    "front_image_path",
    "side_image_path",
    "model",
    "run_name",
    "prompt_set",
    "status",
]

CORE_TARGETS = ["chest", "waist", "hip"]
EXTRA_TARGETS = ["thigh", "calf", "arm", "shoulder"]
RATIO_TARGETS = ["neck_length", "thigh_calf_ratio", "torso_leg_ratio"]
FULL_TARGETS = [*CORE_TARGETS, *EXTRA_TARGETS, *RATIO_TARGETS]


def get_column_names(target: str):
    """지표 형태에 맞춰 예측 컬럼명과 오차 컬럼명을 반환합니다."""
    if target in RATIO_TARGETS:
        if target == "neck_length":
            # 목길이는 cm 단위
            return f"predicted_{target}_cm", f"{target}_absolute_error_cm"
        else:
            # 비율 지표
            return f"predicted_{target}", f"{target}_absolute_error"
    return f"predicted_{target}_cm", f"{target}_absolute_error_cm"


# 동적으로 10개 부위 컬럼 세트 생성
PRED_COLS = []
ERR_COLS = []
for target in FULL_TARGETS:
    p_col, e_col = get_column_names(target)
    PRED_COLS.append(p_col)
    ERR_COLS.append(e_col)

MEASUREMENT_COLUMNS = [
    "subject_id",
    *PRED_COLS,
    *FULL_TARGETS,
    *ERR_COLS,
]


def order_result_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    preferred = [column for column in MEASUREMENT_COLUMNS if column in dataframe.columns]
    trailing = [
        column for column in TRAILING_METADATA_COLUMNS if column in dataframe.columns
    ]
    middle = [
        column
        for column in dataframe.columns
        if column not in preferred and column not in trailing
    ]
    return dataframe[preferred + middle + trailing]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    args = parser.parse_args()

    labels_path = DATA_DIR / f"{args.split}_set.csv"
    label_source = pd.read_csv(labels_path)
    available_targets = [
        target for target in FULL_TARGETS if target in label_source.columns
    ]
    labels = label_source[["subject_id", *available_targets]]
    predictions = pd.read_csv(args.predictions)

    evaluated = labels.merge(
        predictions,
        on="subject_id",
        how="left",
        validate="one_to_one",
    )

    scored_targets = []
    for measurement in available_targets:
        prediction_column, error_column = get_column_names(measurement)
        if prediction_column not in evaluated.columns:
            continue
        evaluated[prediction_column] = pd.to_numeric(
            evaluated[prediction_column],
            errors="coerce",
        )
        evaluated[measurement] = pd.to_numeric(
            evaluated[measurement],
            errors="coerce",
        )
        evaluated[error_column] = (
            evaluated[measurement] - evaluated[prediction_column]
        ).abs()
        if evaluated[measurement].notna().any():
            scored_targets.append(measurement)

    success_rows = evaluated[evaluated["status"] == "success"].copy()
    metrics = {
        "total_count": int(len(evaluated)),
        "success_count": int(len(success_rows)),
        "success_rate": round(len(success_rows) / len(evaluated), 4),
        "mean_latency_seconds": round(success_rows["latency_seconds"].mean(), 3),
    }
    for target in scored_targets:
        _, error_column = get_column_names(target)
        # 비율인지 cm인지에 맞추어 키값 지정
        unit_suffix = "_ratio" if target.endswith("_ratio") else "_mae_cm"
        metrics[f"{target}{unit_suffix}"] = round(
            success_rows[error_column].mean(), 3
        )

    # 정답이 비어 있는 부위는 "모델이 값을 주기는 했는지"만 기록한다.
    # 이 숫자는 정확도가 아니라 응답률이다.
    coverage = {}
    for target in FULL_TARGETS:
        column, _ = get_column_names(target)
        if column in success_rows.columns and target not in scored_targets:
            filled = int(
                pd.to_numeric(success_rows[column], errors="coerce").notna().sum()
            )
            coverage[target] = round(filled / len(success_rows), 4) if len(success_rows) else 0.0
    if coverage:
        metrics["extra_target_coverage_no_ground_truth"] = coverage

    if args.predictions.name == "predictions.csv":
        output_path = args.predictions.with_name("evaluated.csv")
        metrics_path = args.predictions.with_name("metrics.json")
    else:
        output_path = args.predictions.with_name(
            args.predictions.stem.replace("_predictions_", "_evaluated_") + ".csv"
        )
        metrics_path = args.predictions.with_name(
            args.predictions.stem.replace("_predictions_", "_metrics_") + ".json"
        )

    order_result_columns(evaluated).to_csv(output_path, index=False)
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"평가 결과 저장 완료: {output_path}")
    print(f"지표 저장 완료: {metrics_path}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()



