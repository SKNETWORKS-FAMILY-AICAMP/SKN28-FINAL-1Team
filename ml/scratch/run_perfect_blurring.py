import os
import sys
import json
import boto3
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter
from concurrent.futures import ThreadPoolExecutor, as_completed

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")

META_FILE = "data/golden_200_meta.csv"
INPUT_DIR = "data/golden_200_front"
OUTPUT_DIR = "data/golden_200_front_blurred"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_polygon_points(polygon_str):
    points = [float(x) for x in polygon_str.strip().split()]
    return list(zip(points[0::2], points[1::2]))

def process_perfect_blur(row):
    s3_client = session.client("s3", region_name="ap-southeast-2")
    subject = row["subject_id"]
    chunk = row["chunk"]
    
    img_path = os.path.join(INPUT_DIR, f"{subject}_front.jpg")
    output_path = os.path.join(OUTPUT_DIR, f"{subject}_front_blurred.jpg")
    
    if not os.path.exists(img_path):
        return subject, False, "원본 이미지 없음"
        
    # S3에서 3번 정면 카메라의 라벨링 JSON 파일 읽기
    json_key = f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/라벨링데이터/{chunk.replace('TS_', 'TL_')}/{subject.replace('F', 'TL_F').replace('M', 'TL_M')}/json/01_01_{subject}_03.json"
    
    # 만약 위의 복잡한 경로가 안 맞을 경우를 위해 유연한 경로 구성 시도
    # 예: TL_F009toF108/TL_F009/json/01_01_F009_03.json
    sub_folder = subject.replace('F', 'TL_F').replace('M', 'TL_M')
    # 폴더명이 그냥 F009일 수도 있으므로 보정
    possible_keys = [
        f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/라벨링데이터/{chunk.replace('TS_', 'TL_')}/{sub_folder}/json/01_01_{subject}_03.json",
        f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/라벨링데이터/{chunk.replace('TS_', 'TL_')}/{subject}/json/01_01_{subject}_03.json"
    ]
    
    json_data = None
    loaded_key = None
    for k in possible_keys:
        try:
            obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=k)
            json_data = json.loads(obj["Body"].read().decode("utf-8"))
            loaded_key = k
            break
        except Exception:
            continue
            
    if json_data is None:
        return subject, False, "라벨 JSON을 찾을 수 없음"
        
    # '머리' 라벨 폴리곤 탐색
    head_polygon_str = None
    for item in json_data.get("labelingInfo", []):
        poly = item.get("polygon", {})
        if poly.get("label") == "머리":
            head_polygon_str = poly.get("location")
            break
            
    if not head_polygon_str:
        return subject, False, "머리 폴리곤 라벨 없음"
        
    try:
        # 다각형 좌표 파싱
        polygon_points = parse_polygon_points(head_polygon_str)
        
        # 이미지 로드 (Pillow)
        original_img = Image.open(img_path).convert("RGB")
        
        # 블러 처리된 전체 이미지 생성 (강한 가우시안 블러 커널 35 적용)
        blurred_img = original_img.filter(ImageFilter.GaussianBlur(radius=35))
        
        # 알파 마스크 생성 (머리 영역만 흰색, 나머지는 검은색)
        mask = Image.new("L", original_img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(polygon_points, fill=255)
        
        # 원본 이미지에 머리 영역만 블러 이미지 합성
        final_img = Image.composite(blurred_img, original_img, mask)
        
        # 저장
        final_img.save(output_path, "JPEG", quality=95)
        return subject, True, "성공"
        
    except Exception as e:
        return subject, False, f"블러 처리 중 에러: {e}"

def main():
    if not os.path.exists(META_FILE):
        print("골든셋 메타 데이터가 존재하지 않습니다.")
        return
        
    df = pd.read_csv(META_FILE)
    print(f"골든셋 {len(df)}명에 대한 라벨 매핑 정밀 헤드 블러링 전처리 시작...")
    
    success_count = 0
    failures = []
    
    max_workers = 30
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_perfect_blur, row): row["subject_id"] for _, row in df.iterrows()}
        
        for future in as_completed(futures):
            sub = futures[future]
            try:
                sub_id, success, msg = future.result()
                if success:
                    success_count += 1
                else:
                    failures.append((sub_id, msg))
            except Exception as e:
                failures.append((sub, str(e)))
                
            completed = success_count + len(failures)
            if completed % 25 == 0:
                print(f"진행 상황: {completed}/200 완료 (성공: {success_count}, 실패: {len(failures)})...")
                
    print("\n=== 정밀 헤드 블러링 전처리 최종 결과 ===")
    print(f"완료 이미지 수: {success_count} / 200")
    if failures:
        print(f"실패 사례 수: {len(failures)}")
        for sub, err in failures[:10]:
            print(f"- {sub}: {err}")

if __name__ == "__main__":
    main()
