import os
import boto3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")
META_FILE = "ml/body_measurement/data/golden_182_meta.csv"
OUTPUT_DIR = "ml/body_measurement/data/raw_test_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_s3_file(s3_client, key, local_path):
    try:
        s3_client.download_file(BUCKET_NAME, key, local_path)
        return True
    except Exception as e:
        return False

def process_subject(row):
    s3_client = session.client("s3", region_name="ap-southeast-2")
    subject = row["subject_id"]
    chunk = row["chunk"]
    
    base_prefix = f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/원천데이터/{chunk}/{subject}/"
    
    # 1. 정면 이미지 (Cam 03) 다운로드 시 대소문자 폴더 대응
    front_key = None
    for folder in ["Image/", "image/"]:
        test_key = f"{base_prefix}{folder}01_01_{subject}_03.jpg"
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=test_key)
            front_key = test_key
            break
        except Exception:
            continue
            
    # 2. 측면 이미지 (Cam 12) 다운로드 시 대소문자 폴더 대응
    side_key = None
    for folder in ["Image/", "image/"]:
        test_key = f"{base_prefix}{folder}01_01_{subject}_12.jpg"
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=test_key)
            side_key = test_key
            break
        except Exception:
            continue
            
    if not front_key or not side_key:
        return subject, False
        
    front_local = os.path.join(OUTPUT_DIR, f"{subject}_front.jpg")
    side_local = os.path.join(OUTPUT_DIR, f"{subject}_side.jpg")
    csv_local = os.path.join(OUTPUT_DIR, f"{subject}_profile.csv")
    csv_key = row["s3_csv_key"]
    
    # 다운로드 수행
    s1 = download_s3_file(s3_client, front_key, front_local)
    s2 = download_s3_file(s3_client, side_key, side_local)
    s3 = download_s3_file(s3_client, csv_key, csv_local)
    
    return subject, (s1 and s2 and s3)

def main():
    if not os.path.exists(META_FILE):
        print(f"메타데이터 파일이 없습니다: {META_FILE}")
        return
        
    df = pd.read_csv(META_FILE)
    print(f"총 {len(df)}명의 피측정자 원본 정면/측면/치수 다운로드 시작...")
    
    success_count = 0
    failures = []
    
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(process_subject, row): row["subject_id"] for _, row in df.iterrows()}
        
        for future in as_completed(futures):
            sub = futures[future]
            try:
                sub_id, success = future.result()
                if success:
                    success_count += 1
                else:
                    failures.append(sub_id)
            except Exception as e:
                failures.append(f"{sub} (에러: {e})")
                
            completed = success_count + len(failures)
            if completed % 25 == 0:
                print(f"진행도: {completed}/{len(df)} 완료 (성공: {success_count}, 실패: {len(failures)})")
                
    print("\n=== 최종 다운로드 결과 ===")
    print(f"전체 다운로드 성공: {success_count} / {len(df)}")
    if failures:
        print(f"일부 실패 피측정자: {failures[:10]}")

if __name__ == "__main__":
    main()
