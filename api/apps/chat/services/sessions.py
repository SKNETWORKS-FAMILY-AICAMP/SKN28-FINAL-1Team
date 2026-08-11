"""채팅 세션 생성·파생과 메시지 순서·멱등 저장."""

from __future__ import annotations

from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from apps.chat.models import ChatIdentity, ChatMessage, ChatSession
from apps.chat.services.identity import touch_identity


class ChatSessionError(RuntimeError):
    code = "CHAT_SESSION_INVALID"


class ChatSessionForbidden(ChatSessionError):
    code = "CHAT_SESSION_FORBIDDEN"


class ChatModeMismatch(ChatSessionError):
    code = "CHAT_MODE_MISMATCH"


def create_session(
    *,
    identity: ChatIdentity,
    mode: str,
    title: str = "",
    persona_profile_id=None,
) -> ChatSession:
    session = ChatSession(
        identity=identity,
        mode=mode,
        title=title.strip(),
        persona_profile_id=persona_profile_id,
    )
    session.full_clean()
    session.save()
    touch_identity(identity)
    return session


@transaction.atomic
def derive_session(
    *,
    identity: ChatIdentity,
    source_session_id,
    mode: str,
    title: str = "",
) -> ChatSession:
    source = (
        ChatSession.objects.select_for_update()
        .filter(pk=source_session_id, identity=identity, deleted_at__isnull=True)
        .first()
    )
    if source is None:
        raise ChatSessionForbidden("원본 채팅 세션에 접근할 수 없습니다.")
    if source.mode == mode:
        raise ChatModeMismatch("같은 모드로 파생 세션을 만들 수 없습니다.")

    derived = ChatSession(
        identity=identity,
        mode=mode,
        title=title.strip(),
        persona_profile_id=source.persona_profile_id,
        parent_session=source,
        context_state=deepcopy(source.context_state),
        conversation_summary=source.conversation_summary,
    )
    derived.full_clean()
    derived.save()
    touch_identity(identity)
    return derived


@transaction.atomic
def append_message(
    *,
    identity: ChatIdentity,
    session_id,
    role: str,
    content: str = "",
    status: str = ChatMessage.Status.COMPLETED,
    client_message_id: str | None = None,
    metadata: dict | None = None,
) -> tuple[ChatMessage, bool]:
    """세션 잠금으로 sequence를 배정하고 client_message_id 재전송을 멱등 처리한다."""
    session = (
        ChatSession.objects.select_for_update()
        .filter(pk=session_id, identity=identity, deleted_at__isnull=True)
        .first()
    )
    if session is None:
        raise ChatSessionForbidden("채팅 세션에 접근할 수 없습니다.")

    normalized_client_id = (client_message_id or "").strip() or None
    if normalized_client_id is not None:
        existing = ChatMessage.objects.filter(
            session=session,
            client_message_id=normalized_client_id,
        ).first()
        if existing is not None:
            return existing, False

    last_sequence = (
        ChatMessage.objects.filter(session=session).aggregate(value=Max("sequence"))[
            "value"
        ]
        or 0
    )
    message = ChatMessage(
        session=session,
        sequence=last_sequence + 1,
        role=role,
        content=content,
        status=status,
        client_message_id=normalized_client_id,
        metadata=metadata or {},
    )
    try:
        message.full_clean()
    except ValidationError as exc:
        raise ChatSessionError("채팅 메시지 값이 올바르지 않습니다.") from exc
    message.save()

    session.last_message_at = message.created_at
    session.save(update_fields=["last_message_at", "updated_at"])
    touch_identity(identity)
    return message, True
