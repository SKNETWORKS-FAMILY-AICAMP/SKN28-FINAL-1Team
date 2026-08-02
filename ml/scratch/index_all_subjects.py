import os
import boto3
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")

# 20번 데이터셋의 남성/여성 전체 청크 리스트 정의
CHUNKS = [
    # 여성 청크
    "TS_F009toF108", "TS_F109toF208", "TS_F209toF308", "TS_F309toF408", "TS_F409toF505",
    # 남성 청크
    "TS_M009toM108", "TS_M109toM208", "TS_M209toM308", "TS_M309toM408", "TS_M409toM505"
]

OUTPUT_FILE = "data/all_subjects_meta.csv"
os.makedirs("data", exist_ok=True)

def process_subject_csv(chunk, subject_id):
    """S3에서 개별 CSV를 읽어 인체 프로필 메타데이터를 파싱합니다."""
    s3_client = session.client("s3", region_name="ap-southeast-2")
    base_prefix = f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/원천데이터/{chunk}/{subject_id}/"
    csv_prefix = f"{base_prefix}csv/"
    
    # csv/ 폴더 아래의 파일 목록 조회
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=csv_prefix)
        csv_key = None
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].lower().endswith(".csv"):
                    csv_key = obj["Key"]
                    break
        if not csv_key:
            # 상위 폴더 재탐색
            response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=base_prefix)
            for obj in response["Contents"]:
                if obj["Key"].lower().endswith(".csv"):
                    csv_key = obj["Key"]
                    break
                    
        if not csv_key:
            return None

        # S3에서 CSV 내용 직접 가져오기
        csv_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=csv_key)
        
        # 인코딩 디코딩 처리
        content = csv_obj["Body"].read()
        parsed_df = None
        for enc in ["utf-8", "cp949", "euc-kr"]:
            try:
                # header=1을 주어 두 번째 행을 컬럼명으로 읽음
                import io
                df = pd.read_csv(io.BytesIO(content), encoding=enc, header=1)
                df.columns = df.columns.str.strip()
                if "키" in df.columns:
                    parsed_df = df
                    break
            except Exception:
                continue
                
        if parsed_df is None:
            return None
            
        row = parsed_df.iloc[0]
        return {
            "subject_id": subject_id,
            "chunk": chunk,
            "gender": str(row.get("성별", "")).strip(),
            "age": int(row.get("나이", 0)),
            "height": float(row.get("키", 0.0)),
            "weight": float(row.get("몸무게", 0.0)),
            "chest": float(row.get("젖가슴둘레", 0.0)),
            "waist": float(row.get("허리둘레", 0.0)),
            "hip": float(row.get("엉덩이둘레", 0.0)),
            "s3_csv_key": csv_key
        }
    except Exception as e:
        # print(f"[{subject_id}] 에러: {e}")
        return None

def main():
    s3_client = session.client("s3", region_name="ap-southeast-2")
    
    # 1단계: S3에서 모든 피측정자(Subject) 폴더 식별
    print("S3에서 피측정자 폴더를 탐색 중입니다...")
    subject_tasks = []
    
    for chunk in CHUNKS:
        prefix = f"20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/원천데이터/{chunk}/"
        try:
            response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix, Delimiter="/")
            if "CommonPrefixes" in response:
                for cp in response["CommonPrefixes"]:
                    folder_name = cp["Prefix"].split("/")[-2]
                    # F 또는 M으로 시작하는 폴더만 식별 (예: F009, M012)
                    if folder_name.startswith("F") or folder_name.startswith("M"):
                        subject_tasks.append((chunk, folder_name))
        except Exception as e:
            print(f"[{chunk}] 탐색 에러: {e}")
            
    total_subjects = len(subject_tasks)
    print(f"총 {total_subjects}명의 피측정자 식별 완료. 신체 프로필 정보 병렬 수집 시작...")
    
    # 2단계: ThreadPoolExecutor를 이용한 고속 병렬 수집
    results = []
    max_workers = 30  # S3 동시 쿼리 속도 극대화
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_subject_csv, chunk, sub_id): sub_id for chunk, sub_id in subject_tasks}
        
        completed_count = 0
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
            completed_count += 1
            if completed_count % 100 == 0:
                print(f"진행 상황: {completed_count}/{total_subjects} 완료...")
                
    # 3단계: 로컬 CSV 파일로 저장
    if results:
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"\n=== 인덱싱 완료 ===")
        print(f"성공적으로 {len(df)}명의 메타 정보 인덱스를 빌드했습니다 -> {OUTPUT_FILE}")
        print(df.head())
    else:
        print("메타데이터를 수집하지 못했습니다.")

if __name__ == "__main__":
    main()
