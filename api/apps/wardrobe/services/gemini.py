import os
import json
import base64
import logging
import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def analyze_clothing_image(image_path: str) -> dict:
    """Gemini API를 사용하여 의류 이미지를 분석하고 속성을 반환합니다."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY가 없습니다. 기본값을 반환합니다.")
        return {
            "item_name": "새 의류",
            "category_large": "상의",
            "category_small": "티셔츠",
            "color": "기타"
        }

    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine MIME type based on file extension
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/jpeg"
        if ext in (".png", ".jpg", ".jpeg"):
            mime_type = "image/jpeg"
        elif ext == ".webp":
            mime_type = "image/webp"

        prompt = (
            "Analyze this clothing item photo. You must output a JSON object containing the clothing properties. "
            "Use ONLY these exact category values:\n"
            "Category Large: must be one of ['상의', '하의', '아우터', '원피스', '스커트', '신발', '가방', '패션잡화']\n"
            "Category Small: select the closest category small (e.g. 티셔츠, 셔츠, 니트/스웨터, 데님팬츠, 슬랙스, 자켓, 코트, 패딩, 운동화, 구두, 숄더백, 모자, 양말, 등)\n"
            "Color: select the main color (e.g. 블랙, 화이트, 그레이, 네이비, 블루, 베이지, 브라운, 카키, 그린, 핑크, 레드, 옐로우, 오렌지, 퍼플, 골드, 실버, 기타)\n"
            "Item Name: generate a suitable short name in Korean (e.g. '화이트 면 반팔 티셔츠').\n"
            "Output JSON format:\n"
            "{\n"
            "  \"item_name\": \"...\",\n"
            "  \"category_large\": \"...\",\n"
            "  \"category_small\": \"...\",\n"
            "  \"color\": \"...\"\n"
            "}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        res_json = response.json()
        text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
        
        data = json.loads(text_content.strip())
        logger.info("Gemini 분석 성공: %s", data)
        return {
            "item_name": data.get("item_name", "새 의류"),
            "category_large": data.get("category_large", "상의"),
            "category_small": data.get("category_small", "티셔츠"),
            "color": data.get("color", "기타")
        }
    except Exception as e:
        logger.exception("Gemini 분석 중 오류 발생: %s", e)
        return {
            "item_name": "새 의류 (분석 실패)",
            "category_large": "상의",
            "category_small": "티셔츠",
            "color": "기타"
        }
