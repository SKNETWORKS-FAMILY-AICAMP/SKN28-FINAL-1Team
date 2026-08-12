import logging

from django.conf import settings
from rest_framework import serializers

from apps.chat.models import (
    ChatAttachment,
    ChatMessage,
    ChatRun,
    ChatSession,
    PersonaProfile,
)
from apps.chat.services import attachment_storage

logger = logging.getLogger(__name__)

# Django의 ImageField 검증 단계에서도 iPhone HEIC를 이미지로 인식하게 한다.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    logger.debug("pillow-heif 미설치: HEIC 채팅 첨부 검증을 사용할 수 없습니다.")


class ChatAttachmentSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatAttachment
        fields = [
            "id",
            "mime_type",
            "size",
            "sha256",
            "analysis_status",
            "analysis_result",
            "mood_decision",
            "mood_decided_at",
            "image_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_image_url(self, obj: ChatAttachment) -> str | None:
        try:
            return attachment_storage.presigned_get(obj.s3_key)
        except Exception:
            logger.warning(
                "채팅 첨부 presigned URL 발급 실패: attachment=%s",
                obj.pk,
                exc_info=True,
            )
            return None


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


class ChatAttachmentUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(allow_empty_file=False)
    client_message_id = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=128,
    )
    content = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        max_length=settings.CHAT_MESSAGE_MAX_CHARS,
        default="",
    )
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_image(self, image):
        if image.size > settings.CHAT_ATTACHMENT_MAX_BYTES:
            max_mb = settings.CHAT_ATTACHMENT_MAX_BYTES // (1024 * 1024)
            raise serializers.ValidationError(
                f"이미지는 {max_mb}MB 이하여야 합니다."
            )
        if image.content_type not in settings.CHAT_ATTACHMENT_ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                "지원하지 않는 이미지 형식입니다 (jpeg/png/webp/heic)."
            )
        return image

    def validate_client_message_id(self, value: str) -> str:
        if value.startswith("run:"):
            raise serializers.ValidationError(
                "서버 예약 메시지 ID 접두사는 사용할 수 없습니다."
            )
        return value

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata는 JSON 객체여야 합니다.")
        return value


class ChatAttachmentUploadResponseSerializer(serializers.Serializer):
    message = ChatMessageSerializer(read_only=True)
    attachment = ChatAttachmentSerializer(read_only=True)
    created = serializers.BooleanField(read_only=True)


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


class GuestIdentityResponseSerializer(serializers.Serializer):
    identity_id = serializers.UUIDField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class GuestClaimResponseSerializer(serializers.Serializer):
    guest_identity_id = serializers.UUIDField(read_only=True)
    member_identity_id = serializers.UUIDField(read_only=True)
    session_count = serializers.IntegerField(read_only=True)
    message_count = serializers.IntegerField(read_only=True)
    attachment_count = serializers.IntegerField(read_only=True)
    recommendation_count = serializers.IntegerField(read_only=True)


class ChatMessageSubmitResponseSerializer(serializers.Serializer):
    message = ChatMessageSerializer(read_only=True)
    run = ChatRunSerializer(read_only=True)
    events_url = serializers.URLField(read_only=True)


class ChatMoodAnalysisResponseSerializer(serializers.Serializer):
    attachment = ChatAttachmentSerializer(read_only=True)
    run = ChatRunSerializer(read_only=True)
    events_url = serializers.URLField(read_only=True)


class ChatMoodDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["APPROVE", "REJECT"])


class ChatMoodDecisionResponseSerializer(serializers.Serializer):
    attachment = ChatAttachmentSerializer(read_only=True)
    changed = serializers.BooleanField(read_only=True)
    applied = serializers.BooleanField(read_only=True)
    context_state = serializers.JSONField(read_only=True)


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


class ChatHistoryCursorSerializer(serializers.Serializer):
    cursor = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2048,
        default="",
    )


class ChatMessagePageQuerySerializer(ChatHistoryCursorSerializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=50)


class ChatMessagePageResponseSerializer(serializers.Serializer):
    items = ChatMessageSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    next_cursor = serializers.CharField(read_only=True, allow_null=True)
    has_more = serializers.BooleanField(read_only=True)


class ChatSessionSearchQuerySerializer(ChatHistoryCursorSerializer):
    query = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=100,
    )
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)


class ChatSessionSearchMatchSerializer(serializers.Serializer):
    message_id = serializers.UUIDField(read_only=True)
    sequence = serializers.IntegerField(read_only=True)
    role = serializers.ChoiceField(choices=ChatMessage.Role.choices, read_only=True)
    preview = serializers.CharField(read_only=True)


class ChatSessionSearchItemSerializer(ChatSessionSerializer):
    search_match = ChatSessionSearchMatchSerializer(read_only=True, allow_null=True)

    class Meta(ChatSessionSerializer.Meta):
        fields = [*ChatSessionSerializer.Meta.fields, "search_match"]
        read_only_fields = fields

class ChatSessionSearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField(read_only=True)
    items = ChatSessionSearchItemSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    next_cursor = serializers.CharField(read_only=True, allow_null=True)
    has_more = serializers.BooleanField(read_only=True)


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
