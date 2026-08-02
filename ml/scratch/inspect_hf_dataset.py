from datasets import load_dataset
import pandas as pd

def main():
    print("=== Hugging Face 'UniqueData/body-measurements-dataset' 메타 분석 ===")
    try:
        # metadata_only 또는 split 등을 지정하여 가볍게 메타 정보만 확인 시도
        # imagefolder 형식은 로드 시 이미지를 다운로드하므로, 스트리밍(streaming=True)으로 첫 행 몇 개만 로드해 봅니다.
        ds = load_dataset("UniqueData/body-measurements-dataset", streaming=True)
        
        # train 또는 default 스플릿의 첫 번째 피처 확인
        split_name = list(ds.keys())[0]
        print(f"Detected Split: {split_name}")
        
        iterator = iter(ds[split_name])
        sample_rows = []
        for i in range(5):
            try:
                row = next(iterator)
                # 이미지는 바이트 스트림 형태로 들어있으므로 메타데이터 컬럼들만 요약
                meta_row = {k: v for k, v in row.items() if k != "image"}
                meta_row["has_image"] = "image" in row
                sample_rows.append(meta_row)
            except StopIteration:
                break
                
        if sample_rows:
            sample_df = pd.DataFrame(sample_rows)
            print("\n[샘플 메타데이터 컬럼 구조]")
            print(sample_df.to_string())
        else:
            print("데이터셋에서 레코드를 읽어오지 못했습니다.")
            
    except Exception as e:
        print(f"허깅페이스 로드 오류: {e}")

if __name__ == "__main__":
    main()
