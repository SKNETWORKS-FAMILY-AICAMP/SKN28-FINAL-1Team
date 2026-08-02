import os
import re
import json
import shutil
import pandas as pd
from huggingface_hub import hf_hub_download

# 저장 위치 정의 (정면+측면 모델 데이터 통합 폴더)
TARGET_DIR = "ml/body_measurement/data/external_samples"
os.makedirs(TARGET_DIR, exist_ok=True)

def clean_value(val):
    if pd.isna(val) or val is None:
        return 0.0
    val_str = str(val).strip()
    match = re.search(r"^[0-9.]+", val_str)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return 0.0
    return 0.0

def main():
    print("=== 외부 모델 21명 [정면 + 측면 + 치수] 일괄 다운로드 시작 ===")
    
    results = []
    
    for i in range(21):
        subject_id = f"EXT_{i:02d}"
        print(f"[{subject_id}] 정면/측면/치수 다운로드 중...")
        
        # 1. 정면 이미지 다운로드
        img_front_filename = f"files/{i}/front_img.jpg"
        local_front_path = None
        try:
            local_front_path = hf_hub_download(
                repo_id="UniqueData/body-measurements-dataset",
                filename=img_front_filename,
                repo_type="dataset"
            )
        except Exception as e:
            print(f"-> 정면 이미지 다운로드 실패: {e}")
            continue
            
        # 2. 측면 이미지 다운로드
        img_side_filename = f"files/{i}/side_img.jpg"
        local_side_path = None
        try:
            local_side_path = hf_hub_download(
                repo_id="UniqueData/body-measurements-dataset",
                filename=img_side_filename,
                repo_type="dataset"
            )
        except Exception as e:
            print(f"-> 측면 이미지 다운로드 실패: {e}")
            continue
            
        # 3. 신체 치수 JSON 다운로드
        json_filename = f"files/{i}/measurements.json"
        local_json_path = None
        try:
            local_json_path = hf_hub_download(
                repo_id="UniqueData/body-measurements-dataset",
                filename=json_filename,
                repo_type="dataset"
            )
        except Exception as e:
            print(f"-> JSON 다운로드 실패: {e}")
            continue
            
        # 파일 이관 및 이름 매핑
        target_front_name = f"{subject_id}_front.jpg"
        target_front_path = os.path.join(TARGET_DIR, target_front_name)
        shutil.copy(local_front_path, target_front_path)
        
        target_side_name = f"{subject_id}_side.jpg"
        target_side_path = os.path.join(TARGET_DIR, target_side_name)
        shutil.copy(local_side_path, target_side_path)
        
        target_json_name = f"{subject_id}_measurements.json"
        target_json_path = os.path.join(TARGET_DIR, target_json_name)
        shutil.copy(local_json_path, target_json_path)
        
        # JSON 데이터 수치 파싱 및 정밀 클리닝
        try:
            with open(target_json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                
            metrics = {
                "subject_id": subject_id,
                "gender": str(raw_data.get("gender", "female")).strip().upper(),
                "age": int(clean_value(raw_data.get("age"))),
                "height": clean_value(raw_data.get("height")),
                "weight": clean_value(raw_data.get("weight")),
                "chest": clean_value(raw_data.get("chest_circumference_cm")),
                "waist": clean_value(raw_data.get("waist_circumference_cm")),
                "hip": clean_value(raw_data.get("hips_circumference_cm")),
                "front_image": f"ml/body_measurement/data/external_samples/{target_front_name}",
                "side_image": f"ml/body_measurement/data/external_samples/{target_side_name}"
            }
            results.append(metrics)
            print(f"-> {subject_id} 성공: 성별={metrics['gender']}, 나이={metrics['age']}, 키={metrics['height']}cm")
        except Exception as e:
            print(f"-> 데이터 정제 중 에러: {e}")
            
    # 파싱 완료된 메타데이터 저장
    if results:
        summary_df = pd.DataFrame(results)
        summary_df.to_csv(os.path.join(TARGET_DIR, "summary_external_samples.csv"), index=False, encoding="utf-8-sig")
        print(f"\n=== 외부 모델 정면+측면 데이터셋 빌드 완료 ===")
        print(f"저장 위치: {TARGET_DIR}")
        print(f"총 성공: {len(summary_df)}명")
    else:
        print("데이터를 가져오지 못했습니다.")

if __name__ == "__main__":
    main()
