import os
import json
import base64
import logging
import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

#: 모델명은 은퇴(retire)가 잦아 환경변수로 뺀다. 계정이 실제로 쓸 수 있는 목록은
#: `GET https://generativelanguage.googleapis.com/v1beta/models` (헤더 인증)로 확인한다.
#: 404 는 두 가지를 같은 코드로 알려 온다 — 모델이 없거나, **인증이 안 됐거나**.
#: (키를 쿼리스트링으로 보내던 시절엔 인증이 안 돼 멀쩡한 모델도 404가 났다)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

#: 초 단위. 사용자 요청을 붙잡는 동기 호출이라 무한정 늘리지 않는다.
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT_SEC", "60"))


class GeminiAnalysisError(RuntimeError):
    pass


def _parse_json_object(text: str) -> dict:
    """모델 출력에서 첫 번째 유효한 JSON 객체를 뽑는다.

    `responseMimeType: application/json` 을 줘도 출력이 항상 깨끗하지는 않다 —
    코드펜스가 붙거나, 앞뒤에 설명이 섞이거나, 한글 값 안의 따옴표 때문에
    `json.loads` 가 통째로 실패한다(실제로 "Expecting ',' delimiter" 로 실패했다).
    그래서 여는 중괄호마다 `raw_decode` 를 시도해 처음 성공하는 객체를 쓴다.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # ```json ... ``` 펜스 제거
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned.lstrip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(cleaned[index:])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj

    raise GeminiAnalysisError("Gemini 응답에서 JSON 객체를 찾지 못했습니다.")

def analyze_clothing_image(image_path: str) -> dict:
    """Gemini API를 사용하여 의류 이미지를 분석하고 속성을 반환합니다."""
    if not GEMINI_API_KEY:
        raise GeminiAnalysisError("GEMINI_API_KEY가 설정되지 않았습니다.")

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

        # 키는 쿼리스트링이 아니라 헤더로 보낸다.
        # 쿼리에 실으면 예외 메시지·액세스 로그에 URL 통째로 찍히면서 **API 키가 로그에 남는다**
        # (실제로 404 트레이스백에 키가 그대로 노출된 적이 있다).
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

        # 15초로는 이미지 한 장 분석이 끝나지 않아 매번 Read timeout 이 났다.
        # 이 호출이 사용자 요청을 붙잡고 있으므로(동기) 무한정 늘리지는 않는다.
        response = requests.post(url, json=payload, headers=headers, timeout=GEMINI_TIMEOUT)
        if response.status_code != 200:
            # 본문에 사유가 들어 있다(모델명 오류/키 종류 불일치/쿼터). 키는 로그에 남기지 않는다.
            logger.error(
                "Gemini 응답 오류: status=%s model=%s body=%s",
                response.status_code,
                GEMINI_MODEL,
                response.text[:300],
            )
            response.raise_for_status()

        res_json = response.json()
        text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
        
        data = _parse_json_object(text_content)
        logger.info("Gemini 분석 성공: %s", data)
        return {
            "item_name": data.get("item_name", "새 의류"),
            "category_large": data.get("category_large", "상의"),
            "category_small": data.get("category_small", "티셔츠"),
            "color": data.get("color", "기타")
        }
    except Exception as e:
        logger.exception("Gemini 분석 중 오류 발생: %s", e)
        raise GeminiAnalysisError("Gemini 의류 분석에 실패했습니다.") from e
