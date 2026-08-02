from datasets import load_dataset
import pandas as pd

def main():
    print("=== ud-biometrics/body-measurements-image-dataset 로드 및 데이터 구조 진단 ===")
    try:
        # 스트리밍 모드로 데이터셋 로드하여 첫 행 구조 분석
        ds = load_dataset("ud-biometrics/body-measurements-image-dataset", streaming=True)
        split_name = list(ds.keys())[0]
        print(f"Detected Split: {split_name}")
        
        iterator = iter(ds[split_name])
        sample_rows = []
        for i in range(5):
            try:
                row = next(iterator)
                # 이미지는 상세 출력에서 생략
                meta_row = {k: v for k, v in row.items() if k != "image"}
                meta_row["has_image"] = "image" in row
                sample_rows.append(meta_row)
            except StopIteration:
                break
                
        if sample_rows:
            sample_df = pd.DataFrame(sample_rows)
            print("\n[메타데이터 구조]")
            print(sample_df.to_string())
        else:
            print("데이터를 성공적으로 읽어오지 못했습니다.")
            
    except Exception as e:
        print(f"데이터셋 로드 중 에러: {e}")

if __name__ == "__main__":
    main()
