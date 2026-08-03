import os
import json
import pandas as pd
from PIL import Image
from huggingface_hub import hf_hub_download
import io

REPO_ID = "UniqueData/body-measurements-dataset"
TARGET_DIR = "ml/body_measurement/data/external_samples"
os.makedirs(TARGET_DIR, exist_ok=True)
TARGET_SIZE = (768, 1024)

def clean_measurement_value(val):
    if val is None:
        return 0.0
    val_str = str(val).strip()
    # "70.0_tbr" 등 문자열 찌꺼기 제거
    if "_tbr" in val_str:
        val_str = val_str.replace("_tbr", "")
    try:
        return round(float(val_str), 2)
    except Exception:
        return 0.0

def clean_gender(val):
    if val is None:
        return "Unknown"
    val_str = str(val).strip().lower()
    if val_str.startswith("f"):
        return "F"
    elif val_str.startswith("m"):
        return "M"
    return val_str.upper()

def main():
    print("=== UniqueData 외부 실제 인물 21명 데이터셋 수집 시작 ===")
    
    # body.csv 파일 다운로드
    try:
        body_csv_path = hf_hub_download(repo_id=REPO_ID, filename="body.csv", repo_type="dataset")
        df_body = pd.read_csv(body_csv_path)
    except Exception as e:
        print(f"body.csv 로드 실패: {e}")
        return

    results = []
    
    for idx, row in df_body.iterrows():
        # JSON 경로 및 이미지 경로 획득
        json_rel_path = row["measurements"]
        front_rel_path = row["front"]
        
        subject_id = f"REAL_{idx:03d}"
        print(f"[{subject_id}] 데이터 처리 중...")
        
        # 파일 다운로드
        try:
            json_local = hf_hub_download(repo_id=REPO_ID, filename=json_rel_path, repo_type="dataset")
            front_local = hf_hub_download(repo_id=REPO_ID, filename=front_rel_path, repo_type="dataset")
        except Exception as e:
            print(f"-> [{subject_id}] 파일 다운로드 실패: {e}")
            continue
            
        # JSON 치수 파싱
        try:
            with open(json_local, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"-> [{subject_id}] JSON 파싱 실패: {e}")
            continue
            
        height = clean_measurement_value(data.get("height"))
        weight = clean_measurement_value(data.get("weight"))
        age = int(float(data.get("age", 0)))
        gender = clean_gender(data.get("gender"))
        
        chest = clean_measurement_value(data.get("chest_circumference_cm"))
        waist = clean_measurement_value(data.get("waist_circumference_cm"))
        hips = clean_measurement_value(data.get("hips_circumference_cm"))
        
        # 가슴/허리/엉덩이가 없는 레코드는 필터링 제외
        if chest <= 0 or waist <= 0 or hips <= 0:
            print(f"-> [{subject_id}] 3대 치수 누락으로 제외")
            continue
            
        # 정면 이미지 리사이즈 및 저장
        target_img_filename = f"{subject_id}_front.jpg"
        target_img_path = os.path.join(TARGET_DIR, target_img_filename)
        
        try:
            img = Image.open(front_local)
            resized_img = img.convert("RGB").resize(TARGET_SIZE, Image.Resampling.LANCZOS)
            resized_img.save(target_img_path, "JPEG", quality=95)
        except Exception as e:
            print(f"-> [{subject_id}] 이미지 전처리 및 저장 실패: {e}")
            continue
            
        results.append({
            "subject_id": subject_id,
            "gender": gender,
            "age": age,
            "height": height,
            "weight": weight,
            "chest": chest,
            "waist": waist,
            "hip": hips,
            "image_path": f"ml/body_measurement/data/external_samples/{target_img_filename}"
        })
        print(f"-> [{subject_id}] 가공 완료 | 키: {height}cm, 몸무게: {weight}kg, 가슴: {chest}cm, 허리: {waist}cm, 엉덩이: {hips}cm")

    # 메타데이터 CSV 최종 보관
    summary_df = pd.DataFrame(results)
    summary_df.to_csv(os.path.join(TARGET_DIR, "summary_external_samples.csv"), index=False, encoding="utf-8-sig")
    
    print("\n=== 외부 실제 사람 21명 데이터셋 구축 완료 ===")
    print(f"수집 대상 수: {len(results)}명")
    print(f"메타데이터 파일: {TARGET_DIR}/summary_external_samples.csv")
    print(summary_df.head().to_string(index=False))

if __name__ == "__main__":
    main()
