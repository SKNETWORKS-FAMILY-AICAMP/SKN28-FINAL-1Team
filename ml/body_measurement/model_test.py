"""신체 치수 예측 모델의 학습 데이터를 분리하고 검증한다."""

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neighbors import KNeighborsRegressor

DATA_PATH = Path(
    "local/sizekorea/sizekorea_measurements_clean.csv"
)

# 사용자가 모델에 입력할 값
INPUT_COLUMNS = [
    "height",
    "weight",
]

# 모델이 예측해야 하는 값
TARGET_COLUMNS = [
    "chest",
    "waist",
    "hip",
    "thigh",
    "calf",
    "arm",
    "shoulder",
]

# 동일한 결과를 재현하기 위해 고정
RANDOM_STATE = 42

def load_training_data(
    data_path : Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """CSV를 읽어 입력값 X와 정답값 y로 분리한다."""
    
    dataframe = pd.read_csv(data_path)
    
    required_columns = INPUT_COLUMNS + TARGET_COLUMNS
    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]
    
    if missing_columns:
        raise ValueError(
            f"CSV에서 찾을 수 없는 컬럼 : {missing_columns}"
        )
        
    features = dataframe[INPUT_COLUMNS].copy()
    targets = dataframe[TARGET_COLUMNS].copy()
    
    return features, targets

def split_data(
    features : pd.DataFrame,
    targets : pd.DataFrame,
) -> tuple:
    """전체 데이터를 학습, 검증, 테스트 세트로 분리한다."""
    
    (
        features_train_valid,
        features_test,
        targets_train_valid,
        targets_test,
    ) = train_test_split(
        features,
        targets,
        test_size = 0.2,
        random_state = RANDOM_STATE,
    )
    
    (
        features_train,
        features_valid,
        targets_train,
        targets_valid,
    ) = train_test_split(
        features_train_valid,
        targets_train_valid,
        test_size = 0.25,
        random_state = RANDOM_STATE,
    )
    
    return(
        features_train,
        features_valid,
        features_test,
        targets_train,
        targets_valid,
        targets_test,
    )
    
def evaluate_predictions(
    targets_true : pd.DataFrame,
    predictions,
    target_columns : list[str],
) -> pd.DataFrame:
    """예측 결과를 신체 치수별로 평가한다."""
    
    prediction_dataframe = pd.DataFrame(
        predictions,
        columns=target_columns,
        index=targets_true.index,
    )
    
    rows = []
    
    for column in target_columns:
        mae = mean_absolute_error(
            targets_true[column],
            prediction_dataframe[column],
        )
        
        rmse = mean_squared_error(
            targets_true[column],
            prediction_dataframe[column],
        ) ** 0.5
        
        r2 = r2_score(
            targets_true[column],
            prediction_dataframe[column],
        )
        
        rows.append(
            {
                "target" : column,
                "mae" : mae,
                "rmse" : rmse,
                "r2" : r2,
            }
        )
    
    return  pd.DataFrame(rows)
        
def train_baseline_model(
    features_train: pd.DataFrame,
    targets_train: pd.DataFrame,
) -> DummyRegressor:
    """평균값만 예측하는 기준 모델을 학습한다."""
    
    model = DummyRegressor(strategy="mean")
    
    model.fit(
        features_train,
        targets_train,
    )
    
    return model

def train_random_forest_model(
    features_train: pd.DataFrame,
    targets_train: pd.DataFrame,
) -> RandomForestRegressor:
    """RandomForest 모델을 학습한다."""
    
    model = RandomForestRegressor(
        n_estimators=200,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    
    model.fit(
        features_train,
        targets_train,
    )
    
    return model

def train_hist_gradient_boosting_model(
    features_train : pd.DataFrame,
    targets_train : pd.DataFrame,
) -> MultiOutputRegressor:
    """HistGradientBoosting 모델을 학습한다."""
    
    base_model = HistGradientBoostingRegressor(
        random_state = RANDOM_STATE,
    )
    
    model = MultiOutputRegressor(base_model)
    
    model.fit(
        features_train,
        targets_train,
    )
    
    return model

def train_knn_model(
    features_train: pd.DataFrame,
    targets_train: pd.DataFrame,
) -> KNeighborsRegressor:
    """KNN 모델을 학습한다."""
    
    model = KNeighborsRegressor(
        n_neighbors=10,
        weights="distance",
    )

    model.fit(
        features_train,
        targets_train,
    )
    
    return model
    
def predict_body_measurements(
    model,
    height: float,
    weight: float,
) -> pd.Series:
    """키와 몸무게를 입력받아 신체 치수를 예측한다."""
    
    input_dataframe = pd.DataFrame(
        [
            {
                "height" : height,
                "weight" : weight,
            }
        ]
    )
    
    prediction = model.predict(input_dataframe)
    
    return pd.Series(
        prediction[0],
        index=TARGET_COLUMNS,
    )

def main() -> None:
    features, targets = load_training_data(DATA_PATH)
    
    (
        features_train,
        features_valid,
        features_test,
        targets_train,
        targets_valid,
        targets_test,
    ) = split_data(features, targets)
    
    print(f"전체 데이터 : {len(features)}행")
    print(f"학습 데이터 : {len(features_train)}행")
    print(f"검증 데이터 : {len(features_valid)}행")
    print(f"테스트 데이터 : {len(features_test)}행")
    
    print("\n입력 컬럼")
    print(features_train.columns.tolist())
    
    print("\n예측 컬럼")
    print(targets_train.columns.tolist())

    baseline_model = train_baseline_model(
        features_train,
        targets_train,
    )

    baseline_predictions = baseline_model.predict(features_valid)

    baseline_metrics = evaluate_predictions(
        targets_valid,
        baseline_predictions,
        TARGET_COLUMNS,
    )

    print("\nBaseline 검증 성능")
    print(baseline_metrics.round(3).to_string(index=False))

    print("\nBaseline 평균 성능")
    print(
        baseline_metrics[
            ["mae", "rmse", "r2"]
        ].mean().round(3).to_string()
    )
    
    random_forest_model = train_random_forest_model(
        features_train,
        targets_train,
    )
    
    random_forest_predictions = random_forest_model.predict(features_valid)
    
    random_forest_metrics = evaluate_predictions(
        targets_valid,
        random_forest_predictions,
        TARGET_COLUMNS,
    )

    print("\nRandomForest 검증 성능")
    print(random_forest_metrics.round(3).to_string(index=False))

    print("\nRandomForest 평균 성능")
    print(
        random_forest_metrics[
            ["mae", "rmse", "r2"]
        ].mean().round(3).to_string()
    )
    
    hist_gradient_boosting_model = train_hist_gradient_boosting_model(
        features_train,
        targets_train,
    )
    
    hist_gradient_boosting_predictions = (
        hist_gradient_boosting_model.predict(features_valid)
    )
    
    hist_gradient_boosting_metrics = evaluate_predictions(
        targets_valid,
        hist_gradient_boosting_predictions,
        TARGET_COLUMNS,
    )

    print("\nHistGradientBoosting 검증 성능")
    print(hist_gradient_boosting_metrics.round(3).to_string(index=False))
    
    print("\nHistGradientBoosting 평균 성능")
    print(
        hist_gradient_boosting_metrics[
            ["mae", "rmse", "r2"]
        ].mean().round(3).to_string()
    )
    
    knn_model = train_knn_model(
        features_train,
        targets_train,
    )
    
    knn_predictions = knn_model.predict(features_valid)
    
    knn_metrics = evaluate_predictions(
        targets_valid,
        knn_predictions,
        TARGET_COLUMNS,
    )
    
    print("\nKNN 검증 성능")
    print(knn_metrics.round(3).to_string(index=False))
    
    print("\nKNN 평균 성능")
    print(
        knn_metrics[
            ["mae", "rmse", "r2"]
        ].mean().round(3).to_string()
    )
    
    sample_prediction = predict_body_measurements(
        hist_gradient_boosting_model,
        height=170,
        weight=65,
    )
    
    print("\n샘플 입력 예측 결과")
    print("키 : 170cm, 몸무게 : 65kg")
    print(sample_prediction.round(1).to_string())

    

if __name__ == "__main__":
    main()
