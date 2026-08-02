import os
import boto3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")

META_FILE = "data/golden_200_meta.csv"
OUTPUT_DIR = "data/golden_200_front"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_subject_assets(row):
    """지정된 피측정자의 정면 수평 사진과 실측 CSV 파일을 다운로드합니다."""
    s3_client = session.client("s3", region_name="ap-southeast-2")
    subject = row["subject_id"]
    chunk = row["chunk"]
    
    base_prefix = f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/원천데이터/{chunk}/{subject}/"
    
    # 1. 이미지 다운로드 (차렷_측정복_03번 수평정면 카메라)
    # Image/ 또는 image/ 폴더 대응
    img_key = None
    for img_folder in ["Image/", "image/"]:
        test_key = f"{base_prefix}{img_folder}01_01_{subject}_03.jpg"
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=test_key)
            img_key = test_key
            break
        except Exception:
            continue
            
    if not img_key:
        return subject, False, "정면 이미지(Cam 03) 없음"
        
    local_img_path = os.path.join(OUTPUT_DIR, f"{subject}_front.jpg")
    try:
        s3_client.download_file(BUCKET_NAME, img_key, local_img_path)
    except Exception as e:
        return subject, False, f"이미지 다운로드 실패: {e}"
        
    # 2. CSV 다운로드
    # csv_key는 메타 테이블에 이미 등록되어 있으므로 바로 활용
    csv_key = row["s3_csv_key"]
    local_csv_path = os.path.join(OUTPUT_DIR, f"{subject}.csv")
    try:
        s3_client.download_file(BUCKET_NAME, csv_key, local_csv_path)
    except Exception as e:
        return subject, False, f"CSV 다운로드 실패: {e}"
        
    return subject, True, local_img_path

def main():
    if not os.path.exists(META_FILE):
        print("골든셋 메타 데이터가 없습니다.")
        return
        
    df = pd.read_csv(META_FILE)
    print(f"골든셋 200명 데이터 수집 및 다운로드 시작 -> {OUTPUT_DIR}")
    
    success_count = 0
    failures = []
    
    max_workers = 30
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_subject_assets, row): row["subject_id"] for _, row in df.iterrows()}
        
        for future in as_completed(futures):
            subject_id = futures[future]
            try:
                sub, success, path_or_msg = future.result()
                if success:
                    success_count += 1
                else:
                    failures.append((sub, path_or_msg))
            except Exception as e:
                failures.append((subject_id, str(e)))
                
            completed = success_count + len(failures)
            if completed % 20 == 0:
                print(f"진행 상황: {completed}/200 완료 (성공: {success_count}, 실패: {len(failures)})...")
                
    print("\n=== 다운로드 프로세스 종료 ===")
    print(f"총 성공 피측정자: {success_count} / 200")
    if failures:
        print(f"실패 피측정자 수: {len(failures)}")
        for sub, msg in failures[:5]:
            print(f"- {sub}: {msg}")
            
if __name__ == "__main__":
    main()
