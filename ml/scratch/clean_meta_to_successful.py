import os
import pandas as pd

META_FILE = "data/golden_200_meta.csv"
BLURRED_DIR = "data/golden_200_front_blurred"
OUTPUT_FILE = "data/golden_182_meta.csv"

def main():
    if not os.path.exists(META_FILE):
        print("골든셋 메타가 없습니다.")
        return
        
    df = pd.read_csv(META_FILE)
    
    # 실제 블러 처리된 정면 이미지가 생성되어 존재하는 피측정자만 필터링
    valid_rows = []
    for _, row in df.iterrows():
        subject = row["subject_id"]
        blurred_img_path = os.path.join(BLURRED_DIR, f"{subject}_front_blurred.jpg")
        if os.path.exists(blurred_img_path):
            valid_rows.append(row)
            
    valid_df = pd.DataFrame(valid_rows)
    valid_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    
    print("\n=== 최종 골든셋 동기화 완료 ===")
    print(f"최종 생성된 골든셋 메타: {OUTPUT_FILE}")
    print(f"유효 피측정자 수: {len(valid_df)}명 (182명 확인)")
    print("\n[최종 182명 연령대별 통계]")
    valid_df["age_group"] = pd.cut(
        valid_df["age"],
        bins=[0, 19, 29, 39, 49, 59, 100],
        labels=["10대", "20대", "30대", "40대", "50대", "60대이상"]
    )
    print(valid_df["age_group"].value_counts().sort_index())

if __name__ == "__main__":
    main()
