import argparse
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "splits"

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
FULL_TARGETS = [*CORE_TARGETS, *EXTRA_TARGETS]


MEASUREMENT_COLUMNS = [
    "subject_id",
    *[f"predicted_{target}_cm" for target in FULL_TARGETS],
    *FULL_TARGETS,
    *[f"{target}_absolute_error_cm" for target in FULL_TARGETS],
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

    labels_path = DATA_DIR / f"vlm_{args.split}_set.csv"
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
        prediction_column = f"predicted_{measurement}_cm"
        error_column = f"{measurement}_absolute_error_cm"
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
        metrics[f"{target}_mae_cm"] = round(
            success_rows[f"{target}_absolute_error_cm"].mean(), 3
        )

    # 정답이 비어 있는 부위는 "모델이 값을 주기는 했는지"만 기록한다.
    # 이 숫자는 정확도가 아니라 응답률이다.
    coverage = {}
    for target in FULL_TARGETS:
        column = f"predicted_{target}_cm"
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



