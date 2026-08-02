import os
import io
import pandas as pd
from PIL import Image
from huggingface_hub import hf_hub_download
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ID = "Yuanhao-Harry-Wang/fitvto-100k"
TARGET_DIR = "ml/body_measurement/data/external_samples"
os.makedirs(TARGET_DIR, exist_ok=True)
TARGET_SIZE = (768, 1024)

def save_image_worker(img_bytes, target_path):
    try:
        # 바이트 스트림으로부터 이미지 오픈
        img = Image.open(io.BytesIO(img_bytes))
        # 고품질 Lanczos 리사이징 적용 및 JPG 무손실 저장
        resized_img = img.convert("RGB").resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        resized_img.save(target_path, "JPEG", quality=95)
        return True
    except Exception as e:
        print(f"이미지 리사이즈 저장 실패 ({target_path}): {e}")
        return False

def main():
    print("=== fitvto-100k Robust Local 파싱 수집 시작 ===")
    
    local_files = []
    # 500명 이상의 모수를 확보하기 위해 2개의 train parquet 파편을 다운로드
    for i in range(2):
        filename = f"data/train-{i:05d}-of-00406.parquet"
        print(f"[{filename}] 로컬 캐시로 안전 다운로드 중...")
        try:
            local_path = hf_hub_download(
                repo_id=REPO_ID,
                filename=filename,
                repo_type="dataset"
            )
            local_files.append(local_path)
            print(f"-> 다운로드 완료: {local_path}")
        except Exception as e:
            print(f"-> 다운로드 실패: {e}")
            return

    results = []
    images_to_save = []
    
    count = 0
    # 다운로드된 로컬 Parquet 파일 순차 파싱
    for local_path in local_files:
        if count >= 400:
            break
            
        print(f"Parquet 로컬 처리 시작: {local_path}")
        df = pd.read_parquet(local_path)
        
        # 건너뛰기 없이 전체 데이터를 순차 파싱
        for idx in range(len(df)):
            if count >= 400:
                break
                
            row = df.iloc[idx]
            
            subject_id = f"EXT_{count:03d}"
            height = float(row.get("body_height", 0.0))
            bust = float(row.get("body_bust", 0.0))
            waist = float(row.get("body_waist", 0.0))
            hips = float(row.get("body_hips", 0.0))
            
            if height < 100 or bust < 50:
                continue
                
            # 이미지 컬럼 포맷 파싱 (Parquet에서는 dict 형태 {'bytes': b'...'} 또는 raw bytes로 보관됨)
            person_col = row.get("person")
            img_bytes = None
            if isinstance(person_col, dict) and "bytes" in person_col:
                img_bytes = person_col["bytes"]
            elif isinstance(person_col, bytes):
                img_bytes = person_col
            else:
                # PIL Image 객체 형태로 직접 로드된 경우 바이너리로 역변환
                try:
                    img_io = io.BytesIO()
                    person_col.save(img_io, format="PNG")
                    img_bytes = img_io.getvalue()
                except Exception:
                    continue
            
            if img_bytes is None:
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
            
            images_to_save.append((img_bytes, target_path))
            count += 1
            
            if count % 50 == 0:
                print(f"표본 로컬 적재 진행: {count}/400명...")

    # 병렬 이미지 저장 실행 (15개 스레드로 리사이징 병목 해결)
    print(f"\n[총 {len(images_to_save)}장 병렬 리사이즈/저장 시작...]")
    success_count = 0
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(save_image_worker, img_bytes, path): path 
            for img_bytes, path in images_to_save
        }
        for future in as_completed(futures):
            if future.result():
                success_count += 1
                
    # 메타데이터 CSV 저장
    summary_df = pd.DataFrame(results)
    summary_df.to_csv(os.path.join(TARGET_DIR, "summary_external_samples.csv"), index=False, encoding="utf-8-sig")
    
    print("\n=== Robust 다운로드 및 가공 최종 완료 ===")
    print(f"최종 전신 이미지 확보 수: {success_count}명 / 400명")
    print(f"메타데이터 위치: {TARGET_DIR}/summary_external_samples.csv")

if __name__ == "__main__":
    main()
