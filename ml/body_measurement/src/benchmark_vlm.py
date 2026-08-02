import os
import json
import argparse
import time
import pandas as pd
from PIL import Image
import google.generativeai as genai
from openai import OpenAI

# API 키 바인딩
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# API 설정 초기화
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def build_benchmark_prompt(height):
    return f"""
    You are an expert in anthropometry and visual fashion sizing.
    Analyze the provided front-facing full-body photo of a model.
    
    Known metadata:
    - Height: {height} cm
    
    Using the model's height as a spatial scale anchor (pixel-to-centimeter calibration), 
    estimate their body circumferences:
    1. Chest (Bust) circumference (가슴둘레) in cm
    2. Waist circumference (허리둘레) in cm
    3. Hip circumference (엉덩이둘레) in cm
    
    Format the output strictly as JSON with keys: 'chest', 'waist', and 'hip'.
    Ensure all values are floating-point numbers.
    Do not add any explanations, markdown format blocks, or surrounding text.
    """

def query_gemini(img_path, prompt):
    model = genai.GenerativeModel("gemini-1.5-flash")
    img = Image.open(img_path)
    response = model.generate_content(
        [prompt, img],
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text.strip())

def query_openrouter(img_path, prompt, model_id):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    # 이미지를 base64 등으로 전송해야 하므로 바이너리 처리
    import base64
    with open(img_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
    response = client.chat.completions.create(
        model=model_id,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    )
    
    res_text = response.choices[0].message.content
    return json.loads(res_text.strip())

def main():
    parser = argparse.ArgumentParser(description="VLM Body Measurement Benchmarker")
    parser.add_argument("--model", type=str, default="gemini", choices=["gemini", "qwen", "internvl", "gpt4o-mini"],
                        help="VLM Model to benchmark")
    parser.add_argument("--limit", type=int, default=5, help="Number of subjects to test")
    args = parser.parse_args()

    meta_path = "ml/body_measurement/data/external_samples/summary_external_samples.csv"
    if not os.path.exists(meta_path):
        print(f"오류: 수집된 외부 메타데이터를 찾을 수 없습니다 -> {meta_path}")
        return
        
    df = pd.read_csv(meta_path)
    limit = min(args.limit, len(df))
    test_df = df.head(limit)
    
    print(f"\n=== {args.model.upper()} VLM 성능 계측 벤치마크 시작 (표본 수: {limit}명) ===")
    
    results = []
    
    for idx, row in test_df.iterrows():
        sub_id = row["subject_id"]
        height = row["height"]
        actual_chest = row["bust"]
        actual_waist = row["waist"]
        actual_hip = row["hip"]
        
        img_path = row["image_path"]
        
        print(f"[{sub_id}] 계측 수행 중... (실측 키: {height}cm)")
        
        prompt = build_benchmark_prompt(height)
        
        try:
            start_time = time.time()
            if args.model == "gemini":
                pred = query_gemini(img_path, prompt)
            elif args.model == "qwen":
                pred = query_openrouter(img_path, prompt, "qwen/qwen2.5-vl-72b-instruct")
            elif args.model == "internvl":
                pred = query_openrouter(img_path, prompt, "opengvlab/internvl3-78b")
            elif args.model == "gpt4o-mini":
                pred = query_openrouter(img_path, prompt, "openai/gpt-4o-mini")
            latency = time.time() - start_time
            
            p_chest = float(pred.get("chest", 0.0))
            p_waist = float(pred.get("waist", 0.0))
            p_hip = float(pred.get("hip", 0.0))
            
            err_chest = abs(p_chest - actual_chest)
            err_waist = abs(p_waist - actual_waist)
            err_hip = abs(p_hip - actual_hip)
            
            results.append({
                "subject_id": sub_id,
                "height": height,
                "actual_chest": actual_chest,
                "pred_chest": p_chest,
                "err_chest": err_chest,
                "actual_waist": actual_waist,
                "pred_waist": p_waist,
                "err_waist": err_waist,
                "actual_hip": actual_hip,
                "pred_hip": p_hip,
                "err_hip": err_hip,
                "latency_sec": round(latency, 2)
            })
            
            print(f"-> 계측 성공 (Latency: {latency:.2f}s) | 오차 - 가슴: {err_chest:.1f}cm, 허리: {err_waist:.1f}cm, 엉덩이: {err_hip:.1f}cm")
            
        except Exception as e:
            print(f"-> [{sub_id}] 계측 실패: {e}")
            
    if results:
        res_df = pd.DataFrame(results)
        report_dir = "ml/body_measurement/reports"
        os.makedirs(report_dir, exist_ok=True)
        
        output_csv = os.path.join(report_dir, f"benchmark_results_{args.model}.csv")
        res_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        
        print("\n=== 벤치마크 최종 요약 리포트 ===")
        print(f"가슴둘레 평균 절대 오차 (MAE): {res_df['err_chest'].mean():.2f} cm")
        print(f"허리둘레 평균 절대 오차 (MAE): {res_df['err_waist'].mean():.2f} cm")
        print(f"엉덩이둘레 평균 절대 오차 (MAE): {res_df['err_hip'].mean():.2f} cm")
        print(f"평균 응답 지연 시간 (Latency): {res_df['latency_sec'].mean():.2f} 초")
        print(f"결과 리포트 파일 저장 위치: {output_csv}")
    else:
        print("모든 계측에 실패하여 리포트를 생성하지 못했습니다.")

if __name__ == "__main__":
    main()
