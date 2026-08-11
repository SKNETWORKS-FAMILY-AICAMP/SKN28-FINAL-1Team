from django.conf import settings
from rest_framework import serializers

from apps.chat.models import (
    ChatAttachment,
    ChatMessage,
    ChatRun,
    ChatSession,
    PersonaProfile,
)


class ChatAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatAttachment
        fields = [
            "id",
            "mime_type",
            "size",
            "sha256",
            "analysis_status",
            "created_at",
        ]
        read_only_fields = fields


class ChatMessageSerializer(serializers.ModelSerializer):
    attachments = ChatAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sequence",
            "role",
            "content",
            "status",
            "client_message_id",
            "metadata",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChatMessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=settings.CHAT_MESSAGE_MAX_CHARS,
    )
    client_message_id = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=128,
    )
    metadata = serializers.JSONField(required=False)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata는 JSON 객체여야 합니다.")
        return value

    def validate_client_message_id(self, value: str) -> str:
        if value.startswith("run:"):
            raise serializers.ValidationError(
                "서버 예약 메시지 ID 접두사는 사용할 수 없습니다."
            )
        return value


class ChatRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatRun
        fields = [
            "id",
            "session_id",
            "request_message_id",
            "response_message_id",
            "status",
            "enqueued_at",
            "error_code",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = [
            "id",
            "mode",
            "title",
            "persona_profile_id",
            "parent_session_id",
            "context_state",
            "conversation_summary",
            "summary_through_sequence",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChatSessionCreateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=ChatSession.Mode.choices)
    title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    persona_profile_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_persona_profile_id(self, value):
        if value is not None and not PersonaProfile.objects.filter(pk=value).exists():
            raise serializers.ValidationError("존재하지 않는 페르소나 프로필입니다.")
        return value


class ChatSessionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(allow_blank=True, max_length=120)


class ChatSessionDeriveSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=ChatSession.Mode.choices)
    title = serializers.CharField(required=False, allow_blank=True, max_length=120)


class GuestClaimSerializer(serializers.Serializer):
    confirm = serializers.BooleanField()

    def validate_confirm(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("게스트 대화 이전 확인이 필요합니다.")
        return value
