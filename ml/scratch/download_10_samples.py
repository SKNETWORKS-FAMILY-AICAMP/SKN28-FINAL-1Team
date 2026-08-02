import os
import boto3
import pandas as pd
from botocore.exceptions import ClientError

BUCKET_NAME = "skn28-cozy"
# AWS Profile 'cozy'를 사용해 세션 생성
session = boto3.Session(profile_name="cozy")
s3 = session.client("s3", region_name="ap-southeast-2")

OUTPUT_DIR = "data/samples_10"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 10명의 피측정자 ID 정의
SUBJECTS = [f"F{num:03d}" for num in range(9, 19)]
print(f"다운로드 대상 피측정자: {SUBJECTS}")

def download_subject_data(subject):
    print(f"\n--- [{subject}] 데이터 수집 시작 ---")
    base_prefix = f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/원천데이터/TS_F009toF108/{subject}/"
    
    # 1. CSV 폴더 리스팅하여 실제 존재하는 CSV 파일 찾기
    csv_dir_prefix = f"{base_prefix}csv/"
    csv_key = None
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=csv_dir_prefix)
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].lower().endswith(".csv"):
                    csv_key = obj["Key"]
                    break
        if not csv_key:
            print(f"[{subject}] csv/ 폴더에서 CSV 파일을 찾지 못해 상위 폴더 검색 시도...")
            # 상위 폴더에서 검색 시도
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=base_prefix)
            for obj in response["Contents"]:
                if obj["Key"].lower().endswith(".csv"):
                    csv_key = obj["Key"]
                    break
    except Exception as e:
        print(f"[{subject}] CSV 리스팅 오류: {e}")
        return None

    if not csv_key:
        print(f"[{subject}] S3에서 CSV 파일을 식별할 수 없습니다.")
        return None

    local_csv_path = os.path.join(OUTPUT_DIR, f"{subject}.csv")
    
    # CSV 다운로드
    try:
        print(f"S3에서 {csv_key} 다운로드 중...")
        s3.download_file(BUCKET_NAME, csv_key, local_csv_path)
    except ClientError as e:
        print(f"[{subject}] CSV 다운로드 실패: {e}")
        return None

    # 2. 이미지 대소문자(Image/ vs image/) 대응하여 첫 번째 이미지 다운로드
    img_key = None
    for img_folder in ["Image/", "image/"]:
        img_dir_prefix = f"{base_prefix}{img_folder}"
        try:
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=img_dir_prefix, MaxKeys=10)
            if "Contents" in response:
                for obj in response["Contents"]:
                    if obj["Key"].lower().endswith(".jpg") or obj["Key"].lower().endswith(".png"):
                        img_key = obj["Key"]
                        break
            if img_key:
                break
        except Exception:
            continue

    if not img_key:
        print(f"[{subject}] 이미지를 찾을 수 없습니다.")
        return None

    ext = os.path.splitext(img_key)[1]
    local_img_path = os.path.join(OUTPUT_DIR, f"{subject}_img{ext}")
    
    # 이미지 다운로드
    try:
        print(f"S3에서 {img_key} 다운로드 중...")
        s3.download_file(BUCKET_NAME, img_key, local_img_path)
        print(f"[{subject}] 이미지 다운로드 성공 -> {local_img_path}")
    except ClientError as e:
        print(f"[{subject}] 이미지 다운로드 실패: {e}")
        return None

    # 3. CSV 데이터 인코딩 대응 및 파싱 (UTF-8, CP949 순차 시도)
    parsed_df = None
    for enc in ["utf-8", "cp949", "euc-kr"]:
        try:
            df = pd.read_csv(local_csv_path, encoding=enc, header=1)
            df.columns = df.columns.str.strip()
            if "키" in df.columns:
                parsed_df = df
                print(f"[{subject}] {enc} 코덱으로 성공적으로 파싱 완료.")
                break
        except Exception:
            continue

    if parsed_df is None:
        print(f"[{subject}] CSV를 파싱하지 못했습니다. (인코딩 에러)")
        return None

    try:
        row = parsed_df.iloc[0]
        # 관심 치수 매핑
        body_metrics = {
            "subject_id": subject,
            "gender": row.get("성별", "F"),
            "age": int(row.get("나이", 0)),
            "height": float(row.get("키", 0.0)),
            "weight": float(row.get("몸무게", 0.0)),
            "chest": float(row.get("젖가슴둘레", 0.0)),
            "waist": float(row.get("허리둘레", 0.0)),
            "hip": float(row.get("엉덩이둘레", 0.0)),
            "local_image": local_img_path
        }
        return body_metrics
    except Exception as e:
        print(f"[{subject}] CSV 메타 매핑 에러: {e}")
        return None

def main():
    results = []
    for sub in SUBJECTS:
        res = download_subject_data(sub)
        if res:
            results.append(res)
            
    # 전체 결과 요약 출력
    if results:
        summary_df = pd.DataFrame(results)
        summary_df.to_csv(os.path.join(OUTPUT_DIR, "summary_10_samples.csv"), index=False, encoding="utf-8-sig")
        print("\n=== 10개 샘플 치수 정보 요약 ===")
        print(summary_df.to_string(index=False))
    else:
        print("샘플 데이터를 수집하지 못했습니다.")

if __name__ == "__main__":
    main()
