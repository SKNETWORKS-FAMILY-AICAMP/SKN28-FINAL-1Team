from __future__ import annotations

import base64
import json
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)


class GeminiConfigurationError(Exception):
    """Gemini 설정이 누락된 경우."""


class GeminiServiceError(Exception):
    """Gemini 호출 또는 응답 처리에 실패한 경우."""


EVALUATION_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "description": "코디의 전체 완성도 점수",
        },
        "summary": {"type": "string", "description": "긍정적인 종합 평가"},
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 4,
            "description": "사진에서 확인되는 코디의 구체적인 장점",
        },
        "weather_comment": {
            "type": "string",
            "description": "현재 날씨와 코디의 어울림에 대한 평가",
        },
        "personalization_comment": {
            "type": "string",
            "description": "추구미와 체형 정보가 있을 때 제공하는 개인화 평가",
        },
        "styling_tips": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 3,
            "description": "현재 코디의 장점을 살리는 선택적인 스타일링 팁",
        },
    },
    "required": [
        "overall_score",
        "summary",
        "strengths",
        "weather_comment",
        "personalization_comment",
        "styling_tips",
    ],
}

SYSTEM_INSTRUCTION = """당신은 따뜻하고 전문적인 한국어 패션 스타일리스트입니다.
사진에서 실제로 확인되는 요소와 제공된 컨텍스트만 사용하세요.
코디의 장점을 먼저 구체적으로 찾아 긍정적으로 평가하되, 보이지 않는 의류나 신체 특징을 추측하지 마세요.
개선 제안은 비판이 아니라 현재 장점을 더 살리는 선택적인 팁으로 표현하세요.
성별과 체형 정보는 적합도 판단을 돕는 용도로만 사용하고 외모를 평가하거나 고정관념을 적용하지 마세요.
제공되지 않은 개인화 정보는 없다고 명확히 말하고, 모든 응답은 한국어로 작성하세요."""


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts if "text" in part)
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiServiceError("Gemini 응답에 평가 결과가 없습니다.") from exc


def evaluate_outfit(
    image: UploadedFile,
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY가 설정되지 않았습니다.")

    image.seek(0)
    encoded_image = base64.b64encode(image.read()).decode("ascii")
    prompt = (
        "첨부된 코디 사진을 평가해 주세요. 다음 JSON은 평가에 활용할 컨텍스트입니다. "
        "값이 null이면 해당 항목을 평가에 사용하지 마세요.\n"
        f"{json.dumps(context, ensure_ascii=False, default=str)}"
    )
    request_body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": image.content_type,
                            "data": encoded_image,
                        }
                    },
                ],
            }
        ],
        # structured output은 responseMimeType + responseSchema로 지정한다
        # (v1beta GenerationConfig에 responseFormat 필드는 없어 400을 받는다).
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "responseSchema": EVALUATION_SCHEMA,
        },
    }
    url = (
        f"{settings.GEMINI_API_BASE_URL}/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )

    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=request_body,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            # 잘못된 필드명·스키마 등 실제 사유는 본문에만 담기므로 남긴다
            logger.error(
                "Gemini 호출 실패 %s: %s", response.status_code, response.text[:2000]
            )
        response.raise_for_status()
        result = json.loads(_extract_text(response.json()))
    except requests.Timeout as exc:
        raise GeminiServiceError("Gemini 응답 시간이 초과되었습니다.") from exc
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        logger.exception("Gemini 코디 평가 호출 실패")
        raise GeminiServiceError("Gemini 코디 평가에 실패했습니다.") from exc

    return result
