import os
import io
import pandas as pd
from PIL import Image
from datasets import load_dataset
from concurrent.futures import ThreadPoolExecutor, as_completed

TARGET_DIR = "ml/body_measurement/data/external_samples"
os.makedirs(TARGET_DIR, exist_ok=True)
TARGET_SIZE = (768, 1024)

def save_image_worker(img_data, target_path):
    try:
        # 고품질 Lanczos 필터로 768x1024 리사이즈 적용 및 JPG 저장
        resized_img = img_data.convert("RGB").resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        resized_img.save(target_path, "JPEG", quality=95)
        return True
    except Exception as e:
        print(f"이미지 리사이즈 및 저장 실패 ({target_path}): {e}")
        return False

def main():
    print("=== fitvto-100k 기반 외부 모델 400명 (768x1024 리사이즈) 병렬 수집 시작 ===")
    
    # 데이터셋 스트리밍 로드
    ds = load_dataset("Yuanhao-Harry-Wang/fitvto-100k", streaming=True)
    split = list(ds.keys())[0]
    iterator = iter(ds[split])
    
    results = []
    images_to_save = []
    
    count = 0
    # 체형 다양화 샘플링 (건너뛰기 스킵 적용)
    step_skip = 10  # 10개씩 건너뛰며 다양성 확보
    
    while count < 400:
        try:
            row = next(iterator)
            for _ in range(step_skip):
                next(iterator)
        except StopIteration:
            break
            
        subject_id = f"EXT_{count:03d}"
        
        # 신체 치수 로드
        height = float(row.get("body_height", 0.0))
        bust = float(row.get("body_bust", 0.0))
        waist = float(row.get("body_waist", 0.0))
        hips = float(row.get("body_hips", 0.0))
        
        # 값이 유효한지 검사
        if height < 100 or bust < 50:
            continue
            
        img_filename = f"{subject_id}_front.jpg"
        target_path = os.path.join(TARGET_DIR, img_filename)
        
        results.append({
            "subject_id": subject_id,
            "height": round(height, 2),
            "bust": round(bust, 2),
            "waist": round(waist, 2),
            "hip": round(hips, 2),
            "image_path": f"ml/body_measurement/data/external_samples/{img_filename}"
        })
        
        images_to_save.append((row["person"], target_path))
        count += 1
        
        if count % 50 == 0:
            print(f"표본 추출 진행: {count}/400명 완료...")

    # 병렬 이미지 저장 실행 (15개 스레드로 디스크 쓰기 가속)
    print("\n[병렬 이미지 디바이스 고속 리사이즈/저장 개시...]")
    success_count = 0
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(save_image_worker, img, path): path 
            for img, path in images_to_save
        }
        for future in as_completed(futures):
            if future.result():
                success_count += 1
                
    # 메타데이터 CSV 저장
    df = pd.DataFrame(results)
    df.to_csv(os.path.join(TARGET_DIR, "summary_external_samples.csv"), index=False, encoding="utf-8-sig")
    
    print("\n=== 다운로드 및 가공 최종 완료 ===")
    print(f"성공적으로 확보된 모델 수: {success_count}명 / 400명")
    print(f"메타데이터 위치: {TARGET_DIR}/summary_external_samples.csv")

if __name__ == "__main__":
    main()
