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

# 정답값이 있어 오차를 계산할 수 있는 부위.
CORE_TARGETS = ["chest", "waist", "hip"]
# --prompt-set full 로 돌리면 예측값은 나오지만 정답이 없어 채점은 못 한다.
# 응답률(coverage)만 지표에 남긴다.
EXTRA_TARGETS = ["thigh", "calf", "arm", "shoulder"]


MEASUREMENT_COLUMNS = [
    "subject_id",
    *[f"predicted_{target}_cm" for target in [*CORE_TARGETS, *EXTRA_TARGETS]],
    *CORE_TARGETS,
    *[f"{target}_absolute_error_cm" for target in CORE_TARGETS],
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
    labels = pd.read_csv(labels_path)[["subject_id", "chest", "waist", "hip"]]
    predictions = pd.read_csv(args.predictions)

    evaluated = labels.merge(
        predictions,
        on="subject_id",
        how="left",
        validate="one_to_one",
    )

    for measurement in CORE_TARGETS:
        prediction_column = f"predicted_{measurement}_cm"
        error_column = f"{measurement}_absolute_error_cm"
        evaluated[prediction_column] = pd.to_numeric(
            evaluated[prediction_column],
            errors="coerce",
        )
        evaluated[error_column] = (
            evaluated[measurement] - evaluated[prediction_column]
        ).abs()

    success_rows = evaluated[evaluated["status"] == "success"].copy()
    metrics = {
        "total_count": int(len(evaluated)),
        "success_count": int(len(success_rows)),
        "success_rate": round(len(success_rows) / len(evaluated), 4),
        "chest_mae_cm": round(success_rows["chest_absolute_error_cm"].mean(), 3),
        "waist_mae_cm": round(success_rows["waist_absolute_error_cm"].mean(), 3),
        "hip_mae_cm": round(success_rows["hip_absolute_error_cm"].mean(), 3),
        "mean_latency_seconds": round(success_rows["latency_seconds"].mean(), 3),
    }

    # 정답이 없어 MAE를 못 내는 부위는 "모델이 값을 주기는 했는지"만 기록한다.
    # 이 숫자는 정확도가 아니라 응답률이므로 성능 근거로 쓰면 안 된다.
    coverage = {}
    for target in EXTRA_TARGETS:
        column = f"predicted_{target}_cm"
        if column in success_rows.columns:
            filled = int(
                pd.to_numeric(success_rows[column], errors="coerce").notna().sum()
            )
            coverage[target] = round(filled / len(success_rows), 4) if len(success_rows) else 0.0
    if coverage:
        metrics["extra_target_coverage_no_ground_truth"] = coverage

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



