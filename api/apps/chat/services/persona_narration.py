"""확정된 스타일리스트 코디를 검증 가능한 한 문장으로 변환한다."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import ClassVar, Protocol

from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field

from apps.chat.services.openai_adapter import LLMUsage
from apps.chat.services.stylist_personas import (
    EXPECTED_PERSONA_ORDER,
    VoiceProfile,
)

logger = logging.getLogger(__name__)

MAX_PERSONA_SENTENCE_CHARS = 300
MAX_PERSONA_ITEMS = 8
MAX_REASON_CODES = 32
_SENTENCE_TERMINATOR = re.compile(r"[.!?。！？]")

PERSONA_NARRATION_INSTRUCTIONS = """
당신은 이미 확정되고 검증된 패션 코디의 문장을 다듬는 편집기다.
추천하거나 아이템을 선택·교체·추가하지 않는다.
입력의 persona_id와 voice_profile을 말투에만 적용한다.
message는 자연스러운 한국어 한 문장으로 작성한다.
입력의 outfit_id, items, reason_codes는 순서와 값을 바꾸지 않고 그대로 출력한다.
아이템의 색상, 소재, 핏, 브랜드, 가격, 사이즈, 세탁법, 날씨 적합성 등 입력에
없는 속성을 추론하거나 언급하지 않으며 attribute_claims는 반드시 빈 배열로 둔다.
Voice Profile의 examples는 문체 참고일 뿐 현재 코디의 사실로 복사하지 않는다.
검증 근거를 설명할 때도 입력 reason_codes의 범위를 넘지 않는다.
응답은 지정된 구조화 출력 스키마만 따른다.
""".strip()


class PersonaNarrationError(RuntimeError):
    code = "PERSONA_NARRATION_FAILED"


class PersonaNarrationConfigurationError(PersonaNarrationError):
    code = "PERSONA_NARRATION_NOT_CONFIGURED"


class PersonaNarrationProviderError(PersonaNarrationError):
    code = "PERSONA_NARRATION_PROVIDER_FAILED"


class PersonaNarrationContractError(PersonaNarrationError):
    code = "PERSONA_NARRATION_CONTRACT_FAILED"


@dataclass(frozen=True)
class PersonaNarrationItem:
    slot: str
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot", _required_text(self.slot, field="item.slot"))
        object.__setattr__(self, "name", _required_text(self.name, field="item.name"))

    def payload(self) -> dict[str, str]:
        return {"slot": self.slot, "name": self.name}


@dataclass(frozen=True)
class PersonaNarrationRequest:
    """말투 모델에 전달할 수 있는 정보의 폐쇄된 입력 계약."""

    persona_id: str
    outfit_id: str
    items: tuple[PersonaNarrationItem, ...]
    reason_codes: tuple[str, ...]
    voice_profile: VoiceProfile

    def __post_init__(self) -> None:
        persona_id = _required_text(self.persona_id, field="persona_id")
        if persona_id not in EXPECTED_PERSONA_ORDER:
            raise PersonaNarrationContractError("지원하지 않는 스타일리스트 ID입니다.")
        object.__setattr__(self, "persona_id", persona_id)
        object.__setattr__(
            self,
            "outfit_id",
            _required_text(self.outfit_id, field="outfit_id"),
        )
        if not 1 <= len(self.items) <= MAX_PERSONA_ITEMS:
            raise PersonaNarrationContractError(
                f"말투 변환 아이템은 1~{MAX_PERSONA_ITEMS}개여야 합니다."
            )
        slots = [item.slot for item in self.items]
        if len(slots) != len(set(slots)):
            raise PersonaNarrationContractError(
                "말투 변환 아이템 슬롯은 중복될 수 없습니다."
            )
        normalized_codes = tuple(
            _required_text(code, field="reason_code") for code in self.reason_codes
        )
        if len(normalized_codes) > MAX_REASON_CODES:
            raise PersonaNarrationContractError(
                f"검증 근거 코드는 최대 {MAX_REASON_CODES}개까지 전달할 수 있습니다."
            )
        if len(normalized_codes) != len(set(normalized_codes)):
            raise PersonaNarrationContractError("검증 근거 코드는 중복될 수 없습니다.")
        object.__setattr__(self, "reason_codes", normalized_codes)
        if not isinstance(self.voice_profile, VoiceProfile):
            raise PersonaNarrationContractError(
                "검증된 Voice Profile만 말투 변환에 사용할 수 있습니다."
            )
        if self.voice_profile.max_sentences != 1:
            raise PersonaNarrationContractError(
                "Voice Profile의 최대 문장 수는 1이어야 합니다."
            )

    def payload(self) -> dict[str, object]:
        """전체 대화·사용자·상품 원본 ID가 섞이지 않는 제공자 입력."""

        voice = self.voice_profile
        return {
            "persona_id": self.persona_id,
            "outfit_id": self.outfit_id,
            "items": [item.payload() for item in self.items],
            "reason_codes": list(self.reason_codes),
            "voice_profile": {
                "worldview": voice.worldview,
                "tone_traits": list(voice.tone_traits),
                "sentence_guidelines": list(voice.sentence_guidelines),
                "examples": list(voice.examples),
                "max_sentences": voice.max_sentences,
            },
        }


class PersonaNarrationDraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: str
    name: str


class PersonaNarrationDraft(BaseModel):
    """제공자가 입력 사실을 함께 반납하는 검증 전 구조화 출력."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_PERSONA_SENTENCE_CHARS)
    outfit_id: str = Field(min_length=1)
    items: list[PersonaNarrationDraftItem] = Field(
        min_length=1,
        max_length=MAX_PERSONA_ITEMS,
    )
    reason_codes: list[str] = Field(max_length=MAX_REASON_CODES)
    attribute_claims: list[str] = Field(
        description="입력에 속성이 없으므로 반드시 빈 배열",
        max_length=8,
    )


@dataclass(frozen=True)
class ProviderNarration:
    provider: str
    model: str
    draft: PersonaNarrationDraft
    response_id: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)


@dataclass(frozen=True)
class PersonaNarrationResult:
    message: str
    provider: str
    requested_provider: str
    model: str
    fallback_used: bool
    fallback_reason: str
    response_id: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)


class PersonaNarrator(Protocol):
    provider: str

    def generate_draft(
        self,
        request: PersonaNarrationRequest,
    ) -> ProviderNarration: ...


class TemplatePersonaNarrator:
    provider = "template"

    _ENDING: ClassVar[dict[str, str]] = {
        "minimal": "검증된 조건 안에서 차분하게 정리한 코디예요.",
        "experimental": "검증된 조건은 지키면서 새로운 인상으로 묶은 코디예요.",
        "practical": "검증된 조건을 실제로 활용하기 쉽게 묶은 코디예요.",
    }

    def generate(
        self,
        request: PersonaNarrationRequest,
        *,
        requested_provider: str,
        reason: str,
    ) -> PersonaNarrationResult:
        item_text = ", ".join(
            f"{item.slot}의 {item.name}" for item in request.items[:3]
        )
        if len(request.items) > 3:
            item_text = f"{item_text} 외 {len(request.items) - 3}개 아이템"
        message = f"{item_text} 조합은 {self._ENDING[request.persona_id]}"
        _validate_sentence(message)
        return PersonaNarrationResult(
            message=message,
            provider=self.provider,
            requested_provider=requested_provider,
            model="",
            fallback_used=True,
            fallback_reason=reason,
        )


class PersonaNarrationService:
    """설정된 한 제공자만 호출하고 실패 시 템플릿으로 종료한다."""

    def __init__(
        self,
        *,
        narrator: PersonaNarrator,
        fallback: TemplatePersonaNarrator | None = None,
    ) -> None:
        self.narrator = narrator
        self.fallback = fallback or TemplatePersonaNarrator()

    def generate(self, request: PersonaNarrationRequest) -> PersonaNarrationResult:
        try:
            generated = self.narrator.generate_draft(request)
            if generated.provider != self.narrator.provider:
                raise PersonaNarrationContractError(
                    "말투 응답의 제공자 식별자가 요청과 다릅니다."
                )
            message = validate_narration_draft(request, generated.draft)
        except Exception as exc:  # noqa: BLE001 - 추천 성공을 말투 실패와 격리한다.
            code = getattr(exc, "code", PersonaNarrationProviderError.code)
            logger.warning(
                "페르소나 말투 변환 fallback: provider=%s code=%s type=%s",
                self.narrator.provider,
                code,
                type(exc).__name__,
            )
            return self.fallback.generate(
                request,
                requested_provider=self.narrator.provider,
                reason=str(code)[:64],
            )
        return PersonaNarrationResult(
            message=message,
            provider=generated.provider,
            requested_provider=self.narrator.provider,
            model=generated.model,
            fallback_used=False,
            fallback_reason="",
            response_id=generated.response_id,
            usage=generated.usage,
        )


def build_persona_narration_service(
    *,
    openai_chat_adapter=None,
    gemini_post=None,
) -> PersonaNarrationService:
    """서버 환경변수로 단 하나의 제공자 구현만 선택한다."""

    provider = settings.PERSONA_LLM_PROVIDER.strip().lower()
    if provider == "openai":
        from apps.chat.services.openai_persona_narrator import (
            OpenAIPersonaNarrator,
        )

        return PersonaNarrationService(
            narrator=OpenAIPersonaNarrator(chat_adapter=openai_chat_adapter)
        )
    if provider == "gemini":
        from apps.chat.services.gemini_persona_narrator import (
            GeminiPersonaNarrator,
        )

        return PersonaNarrationService(narrator=GeminiPersonaNarrator(post=gemini_post))
    raise PersonaNarrationConfigurationError(
        "PERSONA_LLM_PROVIDER는 openai 또는 gemini여야 합니다."
    )


def validate_narration_draft(
    request: PersonaNarrationRequest,
    draft: PersonaNarrationDraft,
) -> str:
    """코디·아이템·근거·속성을 바꾼 출력은 문장 사용 전에 폐기한다."""

    if draft.outfit_id != request.outfit_id:
        raise PersonaNarrationContractError("말투 출력의 코디 ID가 다릅니다.")
    expected_items = [item.payload() for item in request.items]
    actual_items = [item.model_dump() for item in draft.items]
    if actual_items != expected_items:
        raise PersonaNarrationContractError("말투 출력의 구성 아이템이 다릅니다.")
    if draft.reason_codes != list(request.reason_codes):
        raise PersonaNarrationContractError("말투 출력의 검증 근거가 다릅니다.")
    if draft.attribute_claims:
        raise PersonaNarrationContractError(
            "입력에 없는 아이템 속성을 말투 출력에 추가할 수 없습니다."
        )
    return _validate_sentence(draft.message)


def persona_narration_json_schema() -> dict[str, object]:
    """Gemini REST 구조화 출력에서 참조 없이 사용할 제한 JSON Schema."""

    return {
        "type": "object",
        "properties": {
            "message": {"type": "string", "maxLength": MAX_PERSONA_SENTENCE_CHARS},
            "outfit_id": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slot": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["slot", "name"],
                    "additionalProperties": False,
                },
            },
            "reason_codes": {"type": "array", "items": {"type": "string"}},
            "attribute_claims": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "message",
            "outfit_id",
            "items",
            "reason_codes",
            "attribute_claims",
        ],
        "additionalProperties": False,
    }


def _validate_sentence(value: str) -> str:
    message = _required_text(value, field="message")
    if len(message) > MAX_PERSONA_SENTENCE_CHARS:
        raise PersonaNarrationContractError(
            f"페르소나 문장은 {MAX_PERSONA_SENTENCE_CHARS}자 이하여야 합니다."
        )
    if "\n" in message or "\r" in message:
        raise PersonaNarrationContractError("페르소나 출력은 한 줄이어야 합니다.")
    terminators = list(_SENTENCE_TERMINATOR.finditer(message))
    if len(terminators) > 1 or (terminators and terminators[0].end() != len(message)):
        raise PersonaNarrationContractError("페르소나 출력은 한 문장이어야 합니다.")
    return message


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonaNarrationContractError(f"{field}는 비어 있지 않은 문자열입니다.")
    return value.strip()
