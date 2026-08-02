import boto3
import json

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")
s3 = session.client("s3", region_name="ap-southeast-2")

def main():
    base_prefix = "20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/라벨링데이터/TL_F009toF108/TL_F009/json/"
    
    print("=== 1~32번 카메라 정면 대칭성 및 뷰 분류 분석 ===")
    
    # 4개의 카메라 칼럼(타워) 군으로 추정되는 단위별 정렬을 위해 루프 실행
    for zz in range(1, 33):
        json_key = f"{base_prefix}01_01_F009_{zz:02d}.json"
        try:
            obj = s3.get_object(Bucket=BUCKET_NAME, Key=json_key)
            data = json.loads(obj["Body"].read().decode("utf-8"))
            
            labels = []
            for item in data.get("labelingInfo", []):
                poly = item.get("polygon", {})
                label = poly.get("label", "")
                if label:
                    labels.append(label)
            
            left_count = sum(1 for l in labels if "왼" in l)
            right_count = sum(1 for l in labels if "오른" in l)
            
            # 머리, 몸통 등의 위치로부터 키가 얼마로 추정되는지
            all_ys = []
            for item in data.get("labelingInfo", []):
                poly = item.get("polygon", {})
                loc = poly.get("location", "")
                if loc:
                    all_ys.extend([float(y) for y in loc.strip().split()[1::2]])
                    
            height_px = max(all_ys) - min(all_ys) if all_ys else 0
            
            # 대칭성 판정 (왼쪽과 오른쪽 부위가 모두 균등하게 보이는가)
            # 예: 왼팔/오른팔, 왼발/오른발이 모두 찍히면 정면 또는 후면
            symmetry = "대칭 (정면/후면 추정)" if abs(left_count - right_count) <= 1 and left_count > 0 else "비대칭 (측면 추정)"
            
            # 정면과 후면 구분: 20번 데이터에서 등/엉덩이 등 후면 특징 또는 라벨 매핑 확인
            # (라벨명에 '목뒤' 등이 특별히 검출되거나, 대칭이면서 특정 카메라 그룹에 속함)
            print(f"Cam: {zz:02d} | Left Labels: {left_count} | Right Labels: {right_count} | {symmetry} | Height: {height_px:.1f}px")
            
        except Exception as e:
            continue

if __name__ == "__main__":
    main()
