import boto3
import json

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")
s3 = session.client("s3", region_name="ap-southeast-2")

def main():
    base_prefix = "20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/라벨링데이터/TL_F009toF108/TL_F009/json/"
    
    print("=== F009 라벨링 파일 카메라 분석 (1~32번) ===")
    for zz in range(1, 33):
        json_key = f"{base_prefix}01_01_F009_{zz:02d}.json"
        try:
            obj = s3.get_object(Bucket=BUCKET_NAME, Key=json_key)
            data = json.loads(obj["Body"].read().decode("utf-8"))
            
            cam_num = data.get("camera_number")
            pos = data.get("position")
            cloth = data.get("cloth")
            img_info = data.get("images", {})
            img_name = img_info.get("identifier")
            
            print(f"File: 01_01_F009_{zz:02d}.json | Cam: {cam_num} | Pos: {pos} | Cloth: {cloth} | Img: {img_name}")
        except Exception as e:
            print(f"Error loading {zz}: {e}")

if __name__ == "__main__":
    main()
