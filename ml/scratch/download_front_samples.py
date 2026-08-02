import os
import boto3
import pandas as pd
from botocore.exceptions import ClientError

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")
s3 = session.client("s3", region_name="ap-southeast-2")

OUTPUT_DIR = "data/samples_10_front"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUBJECTS = [f"F{num:03d}" for num in range(9, 19)]
print(f"중단 정면 카메라(Cam 03) 데이터 수집 대상: {SUBJECTS}")

def download_front_data(subject):
    print(f"\n--- [{subject}] 정면 수평 데이터 수집 ---")
    base_prefix = f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/원천데이터/TS_F009toF108/{subject}/"
    
    # 1. CSV 검색 및 다운로드
    csv_dir_prefix = f"{base_prefix}csv/"
    csv_key = None
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=csv_dir_prefix)
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].lower().endswith(".csv"):
                    csv_key = obj["Key"]
                    break
    except Exception as e:
        print(f"[{subject}] CSV 리스팅 실패: {e}")
        return None

    if not csv_key:
        # 상위 폴더 검색 시도
        try:
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=base_prefix)
            for obj in response["Contents"]:
                if obj["Key"].lower().endswith(".csv"):
                    csv_key = obj["Key"]
                    break
        except Exception:
            pass

    if not csv_key:
        print(f"[{subject}] CSV를 식별할 수 없습니다.")
        return None

    local_csv_path = os.path.join(OUTPUT_DIR, f"{subject}.csv")
    try:
        s3.download_file(BUCKET_NAME, csv_key, local_csv_path)
    except Exception as e:
        print(f"[{subject}] CSV 다운로드 실패: {e}")
        return None

    # 2. 정면 수평 중단 카메라 이미지 (01_01_{subject}_03.jpg 또는 01_01_{subject}_03.png) 다운로드
    # 대소문자 폴더 Image/ vs image/ 둘 다 대응
    img_key = None
    for img_folder in ["Image/", "image/"]:
        # 파일명 규격: XX_YY_actorID_ZZ -> 차렷(01)_측정복(01)_subject_Cam03(03).jpg
        test_key = f"{base_prefix}{img_folder}01_01_{subject}_03.jpg"
        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=test_key)
            img_key = test_key
            break
        except ClientError:
            # 대문자/소문자 파일 확장자 대응 및 파일명 다양성 예외 처리
            try:
                test_key_png = f"{base_prefix}{img_folder}01_01_{subject}_03.png"
                s3.head_object(Bucket=BUCKET_NAME, Key=test_key_png)
                img_key = test_key_png
                break
            except ClientError:
                continue

    if not img_key:
        print(f"[{subject}] 중단 정면 이미지(01_01_{subject}_03.jpg)를 S3에서 찾을 수 없습니다.")
        return None

    local_img_path = os.path.join(OUTPUT_DIR, f"{subject}_front_cam03.jpg")
    try:
        print(f"S3에서 {img_key} 다운로드 중...")
        s3.download_file(BUCKET_NAME, img_key, local_img_path)
        print(f"[{subject}] 정면 이미지 다운로드 성공 -> {local_img_path}")
    except Exception as e:
        print(f"[{subject}] 이미지 다운로드 실패: {e}")
        return None

    # 3. CSV 파싱 및 매핑
    parsed_df = None
    for enc in ["utf-8", "cp949", "euc-kr"]:
        try:
            df = pd.read_csv(local_csv_path, encoding=enc, header=1)
            df.columns = df.columns.str.strip()
            if "키" in df.columns:
                parsed_df = df
                break
        except Exception:
            continue

    if parsed_df is None:
        print(f"[{subject}] CSV 파싱 에러")
        return None

    try:
        row = parsed_df.iloc[0]
        body_metrics = {
            "subject_id": subject,
            "gender": row.get("성별", "F"),
            "age": int(row.get("나이", 0)),
            "height": float(row.get("키", 0.0)),
            "weight": float(row.get("몸무게", 0.0)),
            "chest": float(row.get("젖가슴둘레", 0.0)),
            "waist": float(row.get("허리둘레", 0.0)),
            "hip": float(row.get("엉덩이둘레", 0.0)),
            "front_image_path": local_img_path
        }
        return body_metrics
    except Exception as e:
        print(f"[{subject}] 치수 파싱 에러: {e}")
        return None

def main():
    results = []
    for sub in SUBJECTS:
        res = download_front_data(sub)
        if res:
            results.append(res)
            
    if results:
        summary_df = pd.DataFrame(results)
        summary_df.to_csv(os.path.join(OUTPUT_DIR, "summary_10_front_samples.csv"), index=False, encoding="utf-8-sig")
        print("\n=== 중단 정면 카메라(Cam 03) 다운로드 완료 요약 ===")
        print(summary_df.to_string(index=False))
    else:
        print("정면 샘플 데이터를 수집하지 못했습니다.")

if __name__ == "__main__":
    main()
