import os
import glob
import pandas as pd

RAW_DIR = "ml/body_measurement/data/raw_test_data"
OUTPUT_PATH = os.path.join(RAW_DIR, "summary_raw_test_data.csv")

def main():
    print("=== 사이즈코리아 182명 개별 프로필 CSV 병합 시작 ===")
    
    csv_files = glob.glob(os.path.join(RAW_DIR, "*_profile.csv"))
    if not csv_files:
        print(f"오류: '{RAW_DIR}' 하위에 개별 프로필 CSV가 없습니다.")
        return
        
    results = []
    
    for csv_path in csv_files:
        filename = os.path.basename(csv_path)
        subject_id = filename.replace("_profile.csv", "")
        
        try:
            # 헤더 없이 표준 로드
            df = pd.read_csv(csv_path, header=None)
            
            # 행 개수가 최소 3개여야 함 (헤더 2줄 + 데이터 1줄)
            if len(df) < 3:
                print(f"-> [{subject_id}] 데이터 행 부족")
                continue
                
            # 1번 인덱스 행: 한글 헤더 목록 (키, 몸무게, 젖가슴둘레 등)
            headers = df.iloc[1].astype(str).tolist()
            # 2번 인덱스 행: 실측 수치 데이터
            values = df.iloc[2].tolist()
            
            # 사전으로 맵핑
            record = dict(zip(headers, values))
            
            height = float(record.get("키", 0.0))
            weight = float(record.get("몸무게", 0.0))
            age = int(float(record.get("나이", 0.0)))
            gender = str(record.get("성별", "F")).strip().upper()
            
            chest = float(record.get("젖가슴둘레", 0.0))
            waist = float(record.get("허리둘레", 0.0))
            hip = float(record.get("엉덩이둘레", 0.0))
            
            # 원본 20번 데이터셋 검증 결과: 03=정면 눈높이, 12=측면.
            # image_path는 기존 단일-이미지 소비 코드와의 호환성을 위해 유지한다.
            front_filename = f"{subject_id}_front.jpg"
            side_filename = f"{subject_id}_side.jpg"
            
            results.append({
                "subject_id": subject_id,
                "gender": gender,
                "age": age,
                "height": height,
                "weight": weight,
                "chest": chest,
                "waist": waist,
                "hip": hip,
                "image_path": f"ml/body_measurement/data/raw_test_data/{front_filename}",
                "front_image_path": f"ml/body_measurement/data/raw_test_data/{front_filename}",
                "side_image_path": f"ml/body_measurement/data/raw_test_data/{side_filename}",
                "front_camera_number": 3,
                "side_camera_number": 12,
            })
            
        except Exception as e:
            print(f"-> [{subject_id}] 파싱 중 오류 발생: {e}")
            
    if results:
        summary_df = pd.DataFrame(results)
        summary_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print("\n=== 사이즈코리아 메타 병합 완료 ===")
        print(f"성공적으로 병합된 피측정자 수: {len(summary_df)}명 / 182명")
        print(f"저장 경로: {OUTPUT_PATH}")
        print(summary_df.head().to_string(index=False))
    else:
        print("병합된 데이터가 없습니다.")

if __name__ == "__main__":
    main()
