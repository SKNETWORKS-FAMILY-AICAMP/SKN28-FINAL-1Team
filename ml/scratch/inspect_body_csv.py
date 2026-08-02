import os
import pandas as pd
from huggingface_hub import hf_hub_download

def main():
    print("=== Hugging Face 'body.csv' 다운로드 및 검사 ===")
    try:
        # body.csv 파일 다운로드
        local_path = hf_hub_download(
            repo_id="UniqueData/body-measurements-dataset",
            filename="body.csv",
            repo_type="dataset"
        )
        print(f"다운로드 완료 -> {local_path}")
        
        df = pd.read_csv(local_path)
        print(f"\n[전체 데이터 행/열 수]: {df.shape}")
        print("\n[처음 5행 열람]")
        print(df.head().to_string())
        
        # 나이대, 성별 등의 컬럼 분포가 있는지 확인
        print("\n[컬럼 목록]")
        print(df.columns.tolist())
        
    except Exception as e:
        print(f"body.csv 분석 에러: {e}")

if __name__ == "__main__":
    main()
