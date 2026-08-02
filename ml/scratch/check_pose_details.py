import boto3
import json

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")
s3 = session.client("s3", region_name="ap-southeast-2")

def main():
    base_prefix = "20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/라벨링데이터/TL_F009toF108/TL_F009/json/"
    
    print("=== 촬영 컨텍스트(자세/의상) 조합 분석 (XX_YY_F009_01) ===")
    # XX: 01~06, YY: 01~06 조합에서 첫 번째 카메라(01)의 자세 정보를 조회
    for xx in range(1, 7):
        for yy in range(1, 7):
            json_key = f"{base_prefix}{xx:02d}_{yy:02d}_F009_01.json"
            try:
                obj = s3.get_object(Bucket=BUCKET_NAME, Key=json_key)
                data = json.loads(obj["Body"].read().decode("utf-8"))
                
                pos = data.get("position")
                cloth = data.get("cloth")
                cam = data.get("camera_number")
                
                print(f"Context: {xx:02d}_{yy:02d} | Pos: {pos} | Cloth: {cloth} | Cam: {cam}")
            except Exception as e:
                # 존재하지 않는 조합은 생략
                continue

if __name__ == "__main__":
    main()
