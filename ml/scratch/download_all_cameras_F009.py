import os
import boto3

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")
s3 = session.client("s3", region_name="ap-southeast-2")

OUTPUT_DIR = "data/samples_10/F009_angles"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    base_prefix = "20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/원천데이터/TS_F009toF108/F009/Image/"
    
    # 1번부터 8번 카메라 이미지 다운로드 (수직 타워 1라인의 카메라 세트 추정)
    print("=== F009 (차렷 + 측정복) 카메라 1~8번 다운로드 테스트 ===")
    for zz in range(1, 9):
        img_key = f"{base_prefix}01_01_F009_{zz:02d}.jpg"
        local_path = os.path.join(OUTPUT_DIR, f"F009_cam_{zz:02d}.jpg")
        try:
            print(f"S3에서 {img_key} -> {local_path} 다운로드 중...")
            s3.download_file(BUCKET_NAME, img_key, local_path)
            print(f"-> 다운로드 성공: cam_{zz:02d}")
        except Exception as e:
            print(f"-> cam_{zz:02d} 다운로드 실패: {e}")

if __name__ == "__main__":
    main()
