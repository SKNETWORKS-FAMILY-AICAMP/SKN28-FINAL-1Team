import os
import json
import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = "skn28-cozy"
s3 = boto3.client("s3")

def test_01_dataset():
    print("\n=== [01_의류통합데이터] 샘플 조회 및 다운로드 테스트 ===")
    prefix = "01_의류통합데이터/Training/02.라벨링데이터/"
    try:
        # 라벨링 JSON 파일 탐색
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix, MaxKeys=50)
        if "Contents" not in response:
            print("라벨링데이터 목록을 가져오지 못했습니다.")
            return
        
        json_key = None
        for obj in response["Contents"]:
            if obj["Key"].endswith(".json"):
                json_key = obj["Key"]
                break
        
        if not json_key:
            print("라벨링 JSON 파일을 찾지 못했습니다.")
            return

        print(f"발견한 JSON Key: {json_key}")
        
        # JSON 다운로드 및 파싱
        json_obj = s3.get_object(Bucket=BUCKET_NAME, Key=json_key)
        data = json.loads(json_obj["Body"].read().decode("utf-8"))
        
        # 핵심 메타데이터 출력
        model_meta = data.get("metadata", {}).get("model", {})
        print("파싱된 metadata.model 정보:")
        print(json.dumps(model_meta, indent=2, ensure_ascii=False))
        
        # 연관 이미지 찾기
        # 02.라벨링데이터 -> 01.원천데이터 경로로 변환
        image_key = json_key.replace("02.라벨링데이터", "01.원천데이터").replace(".json", ".jpg")
        print(f"매핑할 이미지 Key 예상: {image_key}")
        
        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=image_key)
            print("-> 이미지 파일이 S3에 존재함을 확인했습니다. (head_object 성공)")
            
            # 다운로드 테스트
            os.makedirs("data/samples_check", exist_ok=True)
            local_img_path = f"data/samples_check/sample_01.jpg"
            local_json_path = f"data/samples_check/sample_01.json"
            
            s3.download_file(BUCKET_NAME, image_key, local_img_path)
            with open(local_json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            print(f"-> 다운로드 성공: {local_img_path}, {local_json_path}")
        except ClientError as e:
            print(f"-> 매핑 이미지 확인 실패: {e}")
            
    except Exception as e:
        print(f"에러 발생: {e}")

def test_20_dataset():
    print("\n=== [20.한국인_전신_형상_및_치수_측정_데이터] 샘플 조회 및 다운로드 테스트 ===")
    prefix = "20.한국인_전신_형상_및_치수_측정_데이터/"
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix, MaxKeys=100)
        if "Contents" not in response:
            print("데이터 목록을 가져오지 못했습니다.")
            return
            
        csv_key = None
        jpg_key = None
        
        for obj in response["Contents"]:
            if obj["Key"].endswith(".csv") and not csv_key:
                csv_key = obj["Key"]
            elif (obj["Key"].endswith(".jpg") or obj["Key"].endswith(".png")) and not jpg_key:
                jpg_key = obj["Key"]
                
        if not csv_key:
            print("계측 CSV 파일을 찾지 못했습니다.")
            return
            
        print(f"발견한 CSV Key: {csv_key}")
        if jpg_key:
            print(f"발견한 이미지 Key: {jpg_key}")
            
        # CSV 다운로드 및 미리보기
        csv_obj = s3.get_object(Bucket=BUCKET_NAME, Key=csv_key)
        content = csv_obj["Body"].read().decode("cp949", errors="ignore")
        lines = content.splitlines()
        print("CSV 상위 5줄 미리보기:")
        for line in lines[:5]:
            print(line)
            
        # 로컬 다운로드
        os.makedirs("data/samples_check", exist_ok=True)
        s3.download_file(BUCKET_NAME, csv_key, "data/samples_check/sample_20.csv")
        if jpg_key:
            s3.download_file(BUCKET_NAME, jpg_key, f"data/samples_check/sample_20{os.path.splitext(jpg_key)[1]}")
            print(f"-> 다운로드 성공: sample_20.csv, sample_20{os.path.splitext(jpg_key)[1]}")
            
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    test_01_dataset()
    test_20_dataset()
