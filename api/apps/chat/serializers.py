from rest_framework import serializers

from apps.chat.models import ChatAttachment, ChatMessage, ChatSession


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
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ChatSessionCreateSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=ChatSession.Mode.choices)
    title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    persona_profile_id = serializers.UUIDField(required=False, allow_null=True)


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
