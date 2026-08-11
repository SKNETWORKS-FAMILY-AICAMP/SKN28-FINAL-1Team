from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiConfigurationError(Exception):
    """Gemini 설정이 누락된 경우."""


class GeminiServiceError(Exception):
    """Gemini 호출 또는 응답 처리에 실패한 경우.

    실패한 호출도 DB에 기록하므로, 원인 파악에 쓸 수 있는 원본 응답을 함께 실어 보낸다.
    """

    def __init__(self, message: str = "", *, response_payload: Any = None) -> None:
        super().__init__(message)
        self.response_payload = response_payload


@dataclass(frozen=True)
class GeminiResult:
    """평가 1건의 호출 결과. DB 기록에 필요한 메타를 함께 담는다."""

    evaluation: dict[str, Any]
    response_payload: dict[str, Any]
    model: str
    latency_ms: int


@dataclass(frozen=True)
class DailyLookResult:
    parsed: dict[str, Any]
    request: dict[str, Any]
    response: dict[str, Any]
    model: str
    latency_ms: int


DAILY_LOOK_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "rationale_ko": {"type": "string"},
        "styling_tips": {"type": "array", "items": {"type": "string"}},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_key": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["item_key"],
            },
        },
    },
    "required": ["headline", "rationale_ko"],
}

DAILY_LOOK_SYSTEM_INSTRUCTION = (
    "당신은 한국어 패션 스타일리스트입니다. 이미 확정된 오늘의 착장에 설명만 붙입니다. "
    "코디나 아이템을 바꾸거나 없는 아이템을 만들지 마세요. 체형은 평가하지 말고 균형을 "
    "살리는 표현을 사용하며, 날씨가 있으면 실용적인 레이어링 안내를 덧붙이세요."
)


# 저장용 요청 본문에서 이미지 base64 자리에 넣는 표시자.
# 원본 사진은 S3에 있으므로 요청 본문에 base64를 남길 이유가 없다 (행 크기 폭증).
IMAGE_PLACEHOLDER = "<image omitted: {size} bytes, stored in S3>"


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


def build_prompt(context: dict[str, Any]) -> str:
    return (
        "첨부된 코디 사진을 평가해 주세요. 다음 JSON은 평가에 활용할 컨텍스트입니다. "
        "값이 null이면 해당 항목을 평가에 사용하지 마세요.\n"
        f"{json.dumps(context, ensure_ascii=False, default=str)}"
    )


def _build_request_body(
    context: dict[str, Any],
    *,
    mime_type: str,
    image_data: str,
) -> dict[str, Any]:
    """실제 호출 본문과 저장용 본문을 같은 함수로 만든다 (둘이 어긋나지 않게)."""
    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": build_prompt(context)},
                    {"inlineData": {"mimeType": mime_type, "data": image_data}},
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


def build_request_payload(
    context: dict[str, Any],
    *,
    mime_type: str,
    image_bytes: int,
) -> dict[str, Any]:
    """DB에 남길 요청 본문. 호출 실패 시에도 기록해야 하므로 호출과 분리한다."""
    return _build_request_body(
        context,
        mime_type=mime_type,
        image_data=IMAGE_PLACEHOLDER.format(size=image_bytes),
    )


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts if "text" in part)
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiServiceError(
            "Gemini 응답에 평가 결과가 없습니다.", response_payload=payload
        ) from exc


def _error_payload(response: requests.Response) -> Any:
    """오류 응답 본문. JSON이 아니면 잘라낸 문자열로 남긴다."""
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text[:2000]}


def evaluate_outfit(
    image_data: bytes,
    *,
    mime_type: str,
    context: dict[str, Any],
) -> GeminiResult:
    """업로드 파일 객체가 아니라 **읽어 둔 바이트**를 받는다.

    같은 업로드를 S3와 Gemini가 차례로 써야 하는데, boto3 upload_fileobj가
    넘겨받은 파일 객체를 닫아버려 두 번째 읽기가 ValueError로 죽었다.
    호출부에서 한 번만 읽고 바이트를 돌려쓰는 것이 유일하게 안전한 방식이다.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY가 설정되지 않았습니다.")

    encoded_image = base64.b64encode(image_data).decode("ascii")
    request_body = _build_request_body(
        context, mime_type=mime_type, image_data=encoded_image
    )
    model = settings.GEMINI_MODEL
    url = f"{settings.GEMINI_API_BASE_URL}/v1beta/models/{model}:generateContent"

    started = time.monotonic()
    error_payload: Any = None
    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=request_body,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            # 잘못된 필드명·스키마 등 실제 사유는 본문에만 담기므로 남긴다
            error_payload = _error_payload(response)
            logger.error(
                "Gemini 호출 실패 %s: %s", response.status_code, response.text[:2000]
            )
        response.raise_for_status()
        response_payload = response.json()
        evaluation = json.loads(_extract_text(response_payload))
    except requests.Timeout as exc:
        # 타임아웃은 대개 사진이 크거나 네트워크가 느린 경우다.
        # 전송 크기를 함께 남겨야 GEMINI_TIMEOUT_SECONDS를 올릴지 판단할 수 있다.
        logger.error(
            "Gemini 타임아웃 %.1fs (limit=%ss, 전송=%dKB)",
            time.monotonic() - started,
            settings.GEMINI_TIMEOUT_SECONDS,
            len(image_data) // 1024,
        )
        raise GeminiServiceError("Gemini 응답 시간이 초과되었습니다.") from exc
    except GeminiServiceError:
        # _extract_text가 이미 원본 응답을 실어 던진 경우 — 덮어쓰지 않는다
        raise
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        logger.exception("Gemini 코디 평가 호출 실패")
        raise GeminiServiceError(
            "Gemini 코디 평가에 실패했습니다.", response_payload=error_payload
        ) from exc

    return GeminiResult(
        evaluation=evaluation,
        response_payload=response_payload,
        model=model,
        latency_ms=int((time.monotonic() - started) * 1000),
    )


def write_daily_look_copy(
    *, outfit: dict[str, Any], context: dict[str, Any]
) -> DailyLookResult:
    """리트리버가 확정한 코디는 유지하고 사용자용 설명만 생성한다."""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY가 설정되지 않았습니다.")
    request_body = {
        "systemInstruction": {"parts": [{"text": DAILY_LOOK_SYSTEM_INSTRUCTION}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "다음 사용자 컨텍스트와 이미 확정된 착장을 설명해 주세요.\n"
                            f"컨텍스트: {json.dumps(context, ensure_ascii=False, default=str)}\n"
                            f"착장: {json.dumps(outfit, ensure_ascii=False, default=str)}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
            "responseSchema": DAILY_LOOK_SCHEMA,
        },
    }
    model = settings.GEMINI_MODEL
    url = f"{settings.GEMINI_API_BASE_URL}/v1beta/models/{model}:generateContent"
    started = time.monotonic()
    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=request_body,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_payload = response.json()
        parsed = json.loads(_extract_text(response_payload))
    except requests.Timeout as exc:
        raise GeminiServiceError("Gemini 응답 시간이 초과되었습니다.") from exc
    except GeminiServiceError:
        raise
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        raise GeminiServiceError("오늘의 룩 설명 생성에 실패했습니다.") from exc

    known_keys = {str(item.get("item_key")) for item in outfit.get("items", [])}
    parsed["items"] = [
        row
        for row in parsed.get("items") or []
        if str(row.get("item_key")) in known_keys
    ]
    return DailyLookResult(
        parsed=parsed,
        request=request_body,
        response=response_payload,
        model=model,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
