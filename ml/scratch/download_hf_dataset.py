import os
import re
import json
import shutil
import pandas as pd
from huggingface_hub import hf_hub_download

# 저장 위치 정의
TARGET_DIR = "ml/body_measurement/data/samples_10_front"
os.makedirs(TARGET_DIR, exist_ok=True)

# 20번 데이터 하이앵글 기존 폴더 제거 대상
OLD_DIR = "ml/body_measurement/data/samples_10"

def clean_value(val):
    """'70.0_tbr' 등 불필요한 후치 텍스트를 제거하고 순수 숫자(float)로 정제합니다."""
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
    # 1. 20번 데이터 중 기존 하이앵글 samples_10 폴더 제거 (정돈 요청 반영)
    if os.path.exists(OLD_DIR):
        print(f"기존 하이앵글 디렉터리 제거 중: {OLD_DIR}")
        shutil.rmtree(OLD_DIR)
        print("기존 하이앵글 디렉터리 제거 완료.")
        
    print("\n=== Hugging Face 외부 모델 21명 데이터 다운로드 및 통합 시작 ===")
    
    results = []
    
    # 21명의 데이터 순차 다운로드
    for i in range(21):
        subject_id = f"EXT_{i:02d}"
        print(f"[{subject_id}] 자산 다운로드 중...")
        
        # 정면 수평 이미지 다운로드
        img_filename = f"files/{i}/front_img.jpg"
        local_img_path = None
        try:
            local_img_path = hf_hub_download(
                repo_id="UniqueData/body-measurements-dataset",
                filename=img_filename,
                repo_type="dataset"
            )
        except Exception as e:
            print(f"-> 이미지 다운로드 실패: {e}")
            continue
            
        # 신체 치수 JSON 다운로드
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
        target_img_name = f"{subject_id}_front.jpg"
        target_img_path = os.path.join(TARGET_DIR, target_img_name)
        shutil.copy(local_img_path, target_img_path)
        
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
                "source": "HuggingFace_UniqueData",
                "image_path": f"ml/body_measurement/data/samples_10_front/{target_img_name}"
            }
            results.append(metrics)
            print(f"-> 수집 성공 (성별: {metrics['gender']}, 키: {metrics['height']}cm, 가슴: {metrics['chest']}cm)")
        except Exception as e:
            print(f"-> 데이터 정제 중 에러: {e}")
            
    # 2. 파싱 완료된 메타데이터 저장
    if results:
        summary_df = pd.DataFrame(results)
        summary_df.to_csv(os.path.join(TARGET_DIR, "summary_external_samples.csv"), index=False, encoding="utf-8-sig")
        print("\n=== 외부 모델 데이터 다운로드 및 통합 완료 ===")
        print(f"총 성공: {len(summary_df)}명")
        print(summary_df.to_string(index=False))
    else:
        print("데이터를 가져오지 못했습니다.")

if __name__ == "__main__":
    main()
