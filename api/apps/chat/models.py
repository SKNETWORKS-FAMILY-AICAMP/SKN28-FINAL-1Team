"""대화형 추천의 회원·게스트 identity, 세션, 메시지와 첨부파일 모델."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ChatIdentity(models.Model):
    """채팅 데이터를 소유하는 회원 또는 만료 가능한 게스트 identity."""

    class IdentityType(models.TextChoices):
        MEMBER = "MEMBER", "회원"
        GUEST = "GUEST", "게스트"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="채팅 identity UUID",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_identity",
        db_comment="회원 사용자 FK (users.id, 게스트이면 NULL)",
    )
    identity_type = models.CharField(
        max_length=12,
        choices=IdentityType.choices,
        db_comment="채팅 identity 유형 (MEMBER/GUEST)",
    )
    guest_token_hash = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_comment="게스트 원문 토큰의 SHA-256 HMAC 해시 (회원이면 NULL)",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="게스트 identity 만료 시각 (회원이면 NULL, 마지막 활동부터 7일)",
    )
    last_active_at = models.DateTimeField(
        default=timezone.now,
        db_comment="채팅 identity의 마지막 활동 시각",
    )
    claimed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="게스트 대화가 회원에게 이전된 시각 (미이전이면 NULL)",
    )
    claimed_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claimed_guest_identities",
        db_comment="게스트 대화를 이전받은 회원 채팅 identity FK (미이전이면 NULL)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_comment="채팅 identity 생성 시각",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_comment="채팅 identity 마지막 수정 시각",
    )

    class Meta:
        db_table = "chat_identity"
        db_table_comment = "회원과 게스트 채팅 소유권 및 게스트 토큰 만료·이전 기록"
        indexes = [
            models.Index(
                fields=["identity_type", "expires_at"],
                name="ix_chat_identity_expiry",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        identity_type="MEMBER",
                        user__isnull=False,
                        guest_token_hash__isnull=True,
                        expires_at__isnull=True,
                    )
                    | Q(
                        identity_type="GUEST",
                        user__isnull=True,
                        guest_token_hash__isnull=False,
                        expires_at__isnull=False,
                    )
                ),
                name="ck_chat_identity_owner_type",
            ),
        ]

    def __str__(self) -> str:
        owner = self.user_id if self.user_id is not None else "guest"
        return f"chat-identity {self.id} ({self.identity_type}:{owner})"

    @property
    def is_guest_active(self) -> bool:
        return (
            self.identity_type == self.IdentityType.GUEST
            and self.claimed_at is None
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )


class ChatSession(models.Model):
    """추천 모드가 고정된 하나의 대화 세션."""

    class Mode(models.TextChoices):
        WARDROBE_BASED = "WARDROBE_BASED", "옷장 기반 추천"
        NEW_ITEM = "NEW_ITEM", "신규 상품 포함 추천"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="채팅 세션 UUID (외부 노출 식별자)",
    )
    identity = models.ForeignKey(
        ChatIdentity,
        on_delete=models.CASCADE,
        related_name="sessions",
        db_comment="채팅 소유 identity FK (chat_identity.id)",
    )
    mode = models.CharField(
        max_length=24,
        choices=Mode.choices,
        db_comment="세션 생성 후 변경할 수 없는 추천 모드 (WARDROBE_BASED/NEW_ITEM)",
    )
    title = models.CharField(
        max_length=120,
        blank=True,
        default="",
        db_comment="사용자 지정 또는 자동 생성 세션 제목",
    )
    persona_profile_id = models.UUIDField(
        null=True,
        blank=True,
        db_comment="세션에 적용할 페르소나 프로필 UUID (미지정이면 활성 기본값)",
    )
    parent_session = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_sessions",
        db_comment="모드 변경 시 조건을 이어받은 원본 세션 FK (일반 세션이면 NULL)",
    )
    context_state = models.JSONField(
        default=dict,
        blank=True,
        db_comment="세션의 구조화 추천 조건과 컨텍스트 버전 JSON",
    )
    conversation_summary = models.TextField(
        blank=True,
        default="",
        db_comment="오래된 메시지를 압축한 대화 요약",
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="마지막 메시지 생성 시각 (메시지가 없으면 NULL)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_comment="채팅 세션 생성 시각",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_comment="채팅 세션 마지막 수정 시각",
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="사용자가 세션을 삭제한 시각 (소프트 삭제, 활성 세션이면 NULL)",
    )

    class Meta:
        db_table = "chat_session"
        db_table_comment = "추천 모드·조건·대화 요약을 보관하는 회원·게스트 채팅 세션"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["identity", "deleted_at", "-updated_at"],
                name="ix_chat_session_owner",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(mode__in=["WARDROBE_BASED", "NEW_ITEM"]),
                name="ck_chat_session_mode",
            ),
        ]

    def __str__(self) -> str:
        return f"chat-session {self.id} ({self.mode})"

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            previous_mode = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("mode", flat=True)
                .first()
            )
            if previous_mode is not None and previous_mode != self.mode:
                raise ValidationError(
                    {"mode": "추천 모드는 변경할 수 없습니다. 파생 세션을 생성하세요."}
                )
        super().save(*args, **kwargs)


class ChatMessage(models.Model):
    """세션 안에서 순서가 보장되는 사용자·AI·시스템 메시지."""

    class Role(models.TextChoices):
        USER = "USER", "사용자"
        ASSISTANT = "ASSISTANT", "AI"
        SYSTEM = "SYSTEM", "시스템"
        TOOL = "TOOL", "도구"

    class Status(models.TextChoices):
        PENDING = "PENDING", "처리 대기"
        PROCESSING = "PROCESSING", "처리 중"
        COMPLETED = "COMPLETED", "처리 완료"
        FAILED = "FAILED", "처리 실패"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="채팅 메시지 UUID",
    )
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        db_comment="채팅 세션 FK (chat_session.id)",
    )
    sequence = models.PositiveBigIntegerField(
        db_comment="세션 내부 메시지 순서 (1부터 시작)",
    )
    role = models.CharField(
        max_length=12,
        choices=Role.choices,
        db_comment="메시지 역할 (USER/ASSISTANT/SYSTEM/TOOL)",
    )
    content = models.TextField(
        blank=True,
        default="",
        db_comment="채팅 메시지 본문 (첨부파일 전용 메시지이면 빈 문자열 가능)",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.COMPLETED,
        db_comment="메시지 처리 상태 (PENDING/PROCESSING/COMPLETED/FAILED)",
    )
    client_message_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        db_comment="클라이언트 재전송 중복 방지 ID (서버 메시지이면 NULL)",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_comment="추천 결과·실행 ID·오류 등 메시지 부가정보 JSON",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_comment="채팅 메시지 생성 시각",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_comment="채팅 메시지 마지막 수정 시각",
    )

    class Meta:
        db_table = "chat_message"
        db_table_comment = "세션별 순서·역할·처리 상태·중복 방지 ID를 가진 채팅 메시지"
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "sequence"],
                name="uq_chat_message_sequence",
            ),
            models.UniqueConstraint(
                fields=["session", "client_message_id"],
                condition=Q(client_message_id__isnull=False),
                name="uq_chat_message_client_id",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="ck_chat_message_sequence",
            ),
        ]

    def __str__(self) -> str:
        return f"chat-message {self.session_id}#{self.sequence} ({self.role})"


class ChatAttachment(models.Model):
    """사용자 메시지에 첨부된 비공개 파일 메타데이터."""

    class AnalysisStatus(models.TextChoices):
        NOT_REQUESTED = "NOT_REQUESTED", "분석 안 함"
        QUEUED = "QUEUED", "분석 대기"
        PROCESSING = "PROCESSING", "분석 중"
        SUCCEEDED = "SUCCEEDED", "분석 완료"
        FAILED = "FAILED", "분석 실패"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="채팅 첨부파일 UUID",
    )
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
        db_comment="첨부파일이 속한 채팅 메시지 FK (chat_message.id)",
    )
    s3_key = models.CharField(
        max_length=512,
        db_comment="비공개 S3 객체 키",
    )
    mime_type = models.CharField(
        max_length=100,
        db_comment="첨부파일 MIME 타입",
    )
    size = models.PositiveBigIntegerField(
        db_comment="첨부파일 크기 (bytes)",
    )
    sha256 = models.CharField(
        max_length=64,
        db_comment="첨부파일 내용 SHA-256 해시",
    )
    analysis_status = models.CharField(
        max_length=20,
        choices=AnalysisStatus.choices,
        default=AnalysisStatus.NOT_REQUESTED,
        db_comment=(
            "첨부 이미지 분석 상태 (NOT_REQUESTED/QUEUED/PROCESSING/SUCCEEDED/FAILED)"
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_comment="채팅 첨부파일 메타데이터 생성 시각",
    )

    class Meta:
        db_table = "chat_attachment"
        db_table_comment = "채팅 메시지에 연결된 비공개 S3 첨부파일 메타데이터"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "sha256"],
                name="uq_chat_attachment_hash",
            ),
        ]

    def __str__(self) -> str:
        return f"chat-attachment {self.id} ({self.mime_type})"
