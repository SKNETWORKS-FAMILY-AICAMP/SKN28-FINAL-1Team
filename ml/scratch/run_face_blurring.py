import os
import sys
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# 공통 유틸 모듈을 참조하기 위한 sys.path 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../body_measurement/src")))
from utils.privacy import blur_face

META_FILE = "data/golden_200_meta.csv"
INPUT_DIR = "data/golden_200_front"
OUTPUT_DIR = "data/golden_200_front_blurred"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def process_image(subject):
    input_path = os.path.join(INPUT_DIR, f"{subject}_front.jpg")
    output_path = os.path.join(OUTPUT_DIR, f"{subject}_front_blurred.jpg")
    
    if not os.path.exists(input_path):
        return subject, False, "파일 없음"
        
    try:
        # 가우시안 블러링 처리 실행
        detected = blur_face(input_path, output_path)
        status_msg = "얼굴 검출 및 블러 적용" if detected else "검출 실패하여 폴백 상단 블러 적용"
        return subject, True, status_msg
    except Exception as e:
        return subject, False, str(e)

def main():
    if not os.path.exists(META_FILE):
        print("골든셋 메타 데이터가 존재하지 않습니다.")
        return
        
    df = pd.read_csv(META_FILE)
    subjects = df["subject_id"].tolist()
    
    print(f"골든셋 {len(subjects)}명 사진에 대해 얼굴 블러 처리 시작 -> {OUTPUT_DIR}")
    
    success_count = 0
    fallback_count = 0
    failures = []
    
    # 병렬 이미지 파일 입출력 가속
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(process_image, sub): sub for sub in subjects}
        
        for future in futures:
            sub = futures[future]
            try:
                subject_id, success, msg = future.result()
                if success:
                    success_count += 1
                    if "폴백" in msg:
                        fallback_count += 1
                else:
                    failures.append((sub, msg))
            except Exception as e:
                failures.append((sub, str(e)))
                
            completed = success_count + len(failures)
            if completed % 25 == 0:
                print(f"전처리 진행 상황: {completed}/200 완료 (성공: {success_count}, 실패: {len(failures)})...")
                
    print("\n=== 블러 처리 전처리 최종 요약 ===")
    print(f"블러 전처리 완료 이미지 수: {success_count} / 200")
    print(f"그 중 안전 폴백(Fallback) 블러 적용 수: {fallback_count}")
    if failures:
        print(f"실패 사례 수: {len(failures)}")
        for sub, err in failures[:5]:
            print(f"- {sub}: {err}")
            
if __name__ == "__main__":
    main()
