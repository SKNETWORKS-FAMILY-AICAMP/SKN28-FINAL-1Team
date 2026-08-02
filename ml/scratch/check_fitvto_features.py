from datasets import load_dataset
import pandas as pd

def main():
    print("=== Yuanhao-Harry-Wang/fitvto-100k 데이터 상세 분석 ===")
    try:
        # 스트리밍 모드로 evaluation 세트 가볍게 로드
        ds = load_dataset("Yuanhao-Harry-Wang/fitvto-100k", streaming=True)
        split_name = list(ds.keys())[0]
        print(f"Detected Split: {split_name}")
        
        iterator = iter(ds[split_name])
        sample_rows = []
        for i in range(3):
            try:
                row = next(iterator)
                # 이미지나 바이너리 데이터는 용량 상 생략하고 텍스트/수치 치수 필드만 필터링
                meta_row = {
                    k: v for k, v in row.items() 
                    if not hasattr(v, "save") and not isinstance(v, bytes) and k not in ["person_image", "garment_image"]
                }
                meta_row["has_person_image"] = "person_image" in row
                meta_row["has_garment_image"] = "garment_image" in row
                sample_rows.append(meta_row)
            except StopIteration:
                break
                
        if sample_rows:
            sample_df = pd.DataFrame(sample_rows)
            print("\n[메타데이터 세부 피처 구조]")
            print(sample_df.to_string())
        else:
            print("데이터를 성공적으로 파싱하지 못했습니다.")
            
    except Exception as e:
        print(f"로드 실패: {e}")

if __name__ == "__main__":
    main()
