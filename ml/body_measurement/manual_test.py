"""22. SizeKorean 신체치수 모델"""

from pathlib import Path
import boto3
import pandas as pd

SHEET_NAME = "(1~2차년도) 직접측정"

S3_BUCKET = "skn28-cozy"
S3_KEY = (
    "22.사이즈코리아/"
    "8차 인체치수조사(2020~24)_치수데이터(공개용).xlsx"
)
LOCAL_PATH = Path("local/sizekorea/sizekorea_8th.xlsx")
COLUMN_MAP = {
    "002. 키":"height",
    "125. 몸무게":"weight",
    "041. 가슴둘레":"chest",
    "045. 허리둘레":"waist",
    "048. 엉덩이둘레":"hip",
    "051. 넙다리둘레":"thigh",
    "055. 장딴지둘레":"calf",
    "036. 편위팔둘레":"arm",
    "088. 어깨사이너비":"shoulder",
}
MM_COLUMNS = [
    "height",
    "chest",
    "waist",
    "hip",
    "thigh",
    "calf",
    "arm",
    "shoulder",
]

VALID_RANGES = {
    "height" : (100, 230),
    "weight" : (25, 300),
    "chest" : (40, 200),
    "waist" : (40, 200),
    "hip" : (40, 200),
    "thigh" : (20, 120),
    "calf" : (15, 80),
    "arm" : (10, 80),
    "shoulder" : (20, 80),
}

OUTPUT_PATH = Path(
    "local/sizekorea/sizekorea_measurements_clean.csv"
)

def download_excel() -> Path:
    """S3에서 SizeKorea Excel을 다운로드하고 로컬 경로를 반환한다."""      
    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    if LOCAL_PATH.exists():
        print(f"캐시 파일 사용 : {LOCAL_PATH}")
        return LOCAL_PATH
    
    # 로컬 PC의 AWS credential 사용해 S3 client 생성
    s3_client = boto3.client("s3")
    
    print("SizeKorea Excel 다운로드 중...")
    
    s3_client.download_file(
        S3_BUCKET,
        S3_KEY,
        str(LOCAL_PATH),
    )
    
    print(f"다운로드 완료 : {LOCAL_PATH}")
    return LOCAL_PATH

def clean_measurements(dataframe: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataframe.copy()
    
    cleaned.columns = [
        str(column).strip()
        for column in cleaned.columns
    ]
    
    missing_columns = [
        column
        for column in COLUMN_MAP
        if column not in cleaned.columns
    ]
    
    if missing_columns:
        raise ValueError(
            f"엑셀에서 찾을 수 없는 컬럼 : {missing_columns}"
        )
    cleaned = cleaned[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    
    for column in cleaned.columns:
        cleaned[column] = pd.to_numeric(
            cleaned[column],
            errors="coerce",
        )
    
    cleaned = cleaned.replace(9999, pd.NA)
    
    return cleaned

def convert_units(dataframe: pd.DataFrame) -> pd.DataFrame:
    converted = dataframe.copy()
    
    converted[MM_COLUMNS] = converted[MM_COLUMNS] / 10
    
    return converted

def remove_outliers(dataframe : pd.DataFrame) -> pd.DataFrame:
    """허용 범위를 벗어난 측정값을 결측값으로 변경한다."""
    
    cleaned = dataframe.copy()
    
    for column, (minimum, maximum) in VALID_RANGES.items():
        # 현재 컬럼에서 정상 범위에 포함되는 행 찾기
        valid_mask = cleaned[column].between(
            minimum,
            maximum,
        )
        
        # 기존 결측값 제외하고, 실제 이상치 개수 계산
        outlier_count = (
            ~valid_mask & cleaned[column].notna()
        ).sum()
        
        print(f"{column} 이상치: {outlier_count}개")
        
        cleaned.loc[~valid_mask, column] = pd.NA
    
    return cleaned

def create_training_data(
    dataframe:  pd.DataFrame,
) -> pd.DataFrame:
    """입력값과 모든 예측값이 존재하는 행만 남긴다."""
    
    # 사용자가 모델에 입력할 값
    input_columns = [
        "height",
        "weight",
    ]
    
    # 모델이 예측할 신체 치수
    target_columns = [
        "chest",
        "waist",
        "hip",
        "thigh",
        "calf",
        "arm",
        "shoulder",
    ]

    required_columns = input_columns + target_columns
    before_count = len(dataframe)

    # 필수 컬럼 중 하나라도 비어있는 행은 제외
    training_data = dataframe.dropna(
        subset = required_columns,
    ).copy()
    
    # 기존 행 번호 제거하고 0부터 다시 부여
    training_data = training_data.reset_index(drop=True)
    
    print(f"\n정제 전 데이터: {before_count}행")
    print(f"학습 가능 데이터: {len(training_data)}행")
    print(f"제외된 데이터: {before_count - len(training_data)}행")
    
    return training_data

def save_training_data(
    dataframe : pd.DataFrame,
    output_path : Path,
) -> None:
    """정제된 학습 데이터를 CSV파일로 저장한다."""
    
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    
    dataframe.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )
    
    print(f"\nCSV저장 완료 : {output_path}")
    
def inspect_excel(file_path: Path) -> None:
    dataframe = pd.read_excel(
        file_path,
        sheet_name = SHEET_NAME,
        header=6,
    )
    
    cleaned = clean_measurements(dataframe)
    converted = convert_units(cleaned)
    without_outliers = remove_outliers(converted)
    training_data = create_training_data(without_outliers)
    
    print("\n학습 데이터 첫 번째 행")
    print(training_data.head(1).to_string(index=False))
    
    print("\n컬럼별 결측값 개수")
    print(training_data.isna().sum().to_string())
    
    print("\n학습 데이터 기초 통계")
    print(training_data.describe().round(2).to_string())
    
    save_training_data(
        training_data,
        OUTPUT_PATH,
    )
    
def main() -> None:
    excel_path = download_excel()
    inspect_excel(excel_path)


if __name__ ==  "__main__":
    main()