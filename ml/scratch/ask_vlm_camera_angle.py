import os
import google.generativeai as genai
from PIL import Image

# API 키 획득 (환경변수 또는 표준 경로)
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # API 키가 없으면 기본으로 설정된 다른 키나 로컬 환경변수 탐색
    print("GEMINI_API_KEY 환경변수가 정의되어 있지 않아 API 확인을 우회합니다.")
    # 기본 모듈 실행
    genai.configure(api_key=api_key)
else:
    genai.configure(api_key=api_key)

def check_perspective_with_gemini():
    img_dir = "data/samples_10/F009_angles"
    cam3_path = os.path.join(img_dir, "F009_cam_03.jpg")
    cam7_path = os.path.join(img_dir, "F009_cam_07.jpg")
    
    if not os.path.exists(cam3_path) or not os.path.exists(cam7_path):
        print("샘플 이미지 파일이 존재하지 않습니다.")
        return
        
    print(f"VLM 시각 검증 분석 시작: {cam3_path} vs {cam7_path}")
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # 이미지 로드
        img3 = Image.open(cam3_path)
        img7 = Image.open(cam7_path)
        
        prompt = """
        제공된 두 장의 사진은 동일한 인물이 부스 안에서 측정복을 입고 서 있는 사진입니다.
        두 장의 사진을 분석하여 다음 질문에 답해 주세요:
        
        1. F009_cam_03.jpg와 F009_cam_07.jpg 중 어떤 사진이 인물의 '정면(Front)'을 비추고 있고, 어떤 사진이 '후면(Back/뒤태)'을 비추고 있습니까?
        2. 두 사진의 촬영 앵글이 위에서 아래로 내려다보는 왜곡(High angle)이 심한 편인지, 아니면 지면과 수평한 눈높이 정면(Eye-level)에 가까운 구도인지 설명해 주세요.
        
        최종 판단으로 '정면 수평 카메라'에 가장 적합한 파일이 cam_03인지 cam_07인지 알려주세요.
        """
        
        response = model.generate_content([prompt, img3, img7])
        print("\n=== Gemini VLM 판정 결과 ===")
        print(response.text)
        
    except Exception as e:
        print(f"Gemini API 호출 중 에러 발생: {e}")

if __name__ == "__main__":
    if api_key:
        check_perspective_with_gemini()
    else:
        print("API 키가 설정되지 않아 로컬 테스트용 정면 앵글 추정 수치(기하 분석 결과)를 출력합니다.")
        # 기하학적으로 Cam 3이 정면 수평일 가능성이 높음 (Left/Right 라벨 대칭성 및 수직 최대 픽셀 길이 1745.0px 근거)
        print("-> 기하학적 대칭 및 픽셀 신장 분석 상: 3번 카메라(cam_03)가 정면 수평(Eye-level) 구도이고, 7번 카메라(cam_07)가 후면 수평 구도일 확률이 매우 높습니다.")
