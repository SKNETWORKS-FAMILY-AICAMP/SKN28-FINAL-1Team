"""회원 채팅 세션의 응답 모드와 스타일리스트 선택을 변경한다."""

from __future__ import annotations

from collections.abc import Sequence

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.chat.models import (
    ChatIdentity,
    ChatSession,
    validate_member_last_selected_persona_ids,
)
from apps.chat.services import member_stylist_selections


class ChatResponseModeError(RuntimeError):
    code = "CHAT_RESPONSE_MODE_INVALID"


class ChatResponseModeSessionNotFound(ChatResponseModeError):
    code = "CHAT_SESSION_NOT_FOUND"


def _validate_persona_ids(persona_ids: Sequence[str]) -> list[str]:
    if isinstance(persona_ids, (str, bytes)) or not isinstance(
        persona_ids,
        Sequence,
    ):
        raise ChatResponseModeError(
            "스타일리스트 선택값은 문자열 배열이어야 합니다."
        )
    normalized_ids = list(persona_ids)
    try:
        validate_member_last_selected_persona_ids(normalized_ids)
    except ValidationError as exc:
        raise ChatResponseModeError("; ".join(exc.messages)) from exc
    return normalized_ids


@transaction.atomic
def update_session_response_mode(
    *,
    user,
    identity: ChatIdentity,
    session_id,
    response_mode: str,
    selected_persona_ids: Sequence[str] | None = None,
) -> ChatSession:
    """세션 모드를 바꾸고 STYLIST 선택은 회원 마지막 값과 함께 저장한다."""

    session = (
        ChatSession.objects.select_for_update()
        .filter(
            pk=session_id,
            identity=identity,
            deleted_at__isnull=True,
        )
        .first()
    )
    if session is None:
        raise ChatResponseModeSessionNotFound(
            "채팅 세션이 없거나 현재 회원이 소유하지 않습니다."
        )
    if response_mode not in ChatSession.ResponseMode.values:
        raise ChatResponseModeError("지원하지 않는 응답 모드입니다.")

    if response_mode == ChatSession.ResponseMode.DEFAULT:
        if selected_persona_ids is not None:
            raise ChatResponseModeError(
                "DEFAULT 전환에는 selected_persona_ids를 입력하지 않습니다."
            )
        if session.response_mode != ChatSession.ResponseMode.DEFAULT:
            session.response_mode = ChatSession.ResponseMode.DEFAULT
            session.full_clean()
            session.save(update_fields=["response_mode", "updated_at"])
        return session

    resolved_ids = selected_persona_ids
    if resolved_ids is None:
        resolved_ids = (
            session.selected_persona_ids
            or member_stylist_selections.get_member_last_persona_ids(user)
        )
    normalized_ids = _validate_persona_ids(resolved_ids)

    session.response_mode = ChatSession.ResponseMode.STYLIST
    session.selected_persona_ids = normalized_ids
    session.full_clean()
    session.save(
        update_fields=[
            "response_mode",
            "selected_persona_ids",
            "updated_at",
        ]
    )
    member_stylist_selections.save_member_last_persona_ids(
        user,
        normalized_ids,
    )
    return session
