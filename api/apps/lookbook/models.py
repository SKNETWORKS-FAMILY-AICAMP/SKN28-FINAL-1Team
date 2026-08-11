"""룩북 도메인 모델.

룩북은 "룩 한 벌"의 기록이다. 캘린더(calendar_entry)와 담는 내용은 같지만
**날짜에 매이지 않는다** — 캘린더는 user+date 유니크라 하루 한 건이고, 룩북은
같은 날 여러 벌을 올릴 수 있고 날짜가 아예 없을 수도 있다. 그래서 캘린더
테이블을 늘리지 않고 별도 테이블을 뒀고, 두 기록을 잇고 싶을 때만
calendar_entry로 연결한다.

사진 등록 경로는 캘린더와 동일하게 기존 옷장 업로드 job(WardrobeUploadJob)을
재사용한다. 다른 점은 하나 — 사용자가 '입은 옷'으로 이미 지정한 대분류는
이미지 프로세서 단계에서 제외한다(skipped_categories).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.lookbook.contracts import (
    LookbookLinkType,
    LookbookSourceType,
    LookbookStatus,
)


class LookbookPost(models.Model):
    """사용자가 올린 룩 한 벌."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="룩북 UUID (외부 노출 식별자)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lookbook_posts",
        db_comment="룩북 소유 사용자 FK (users.id)",
    )
    wardrobe_upload_job = models.OneToOneField(
        "wardrobe.WardrobeUploadJob",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lookbook_post",
        db_comment=(
            "룩 사진 처리에 재사용한 옷장 job FK "
            "(wardrobe_upload_job.id, 옷장 직접 선택 등록은 NULL)"
        ),
    )
    calendar_entry = models.OneToOneField(
        "style_calendar.CalendarEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lookbook_post",
        db_comment=(
            "'캘린더에도 기록'으로 함께 만든 캘린더 FK "
            "(calendar_entry.id, 캘린더를 남기지 않으면 NULL)"
        ),
    )
    wardrobe_items = models.ManyToManyField(
        "wardrobe.WardrobeItem",
        through="LookbookWardrobeItem",
        through_fields=("lookbook", "wardrobe_item"),
        related_name="lookbook_posts",
        blank=True,
    )
    source_type = models.CharField(
        max_length=24,
        choices=[
            (LookbookSourceType.PHOTO_UPLOAD.value, "룩 사진 업로드"),
            (LookbookSourceType.WARDROBE_SELECTED.value, "옷장 직접 선택"),
        ],
        db_comment="룩북 등록 경로 (PHOTO_UPLOAD/WARDROBE_SELECTED)",
    )
    image_s3_key = models.CharField(
        max_length=512,
        db_comment="룩북 대표 이미지 S3 키 (룩북 소유 경로)",
    )
    schedule = models.TextField(
        blank=True,
        default="",
        db_comment="사용자가 입력한 일정 설명",
    )
    tpo = models.JSONField(
        default=list,
        blank=True,
        db_comment="착장 상황(TPO) 코드 또는 문자열 목록 JSON",
    )
    hashtags = models.JSONField(
        default=list,
        blank=True,
        db_comment="룩북 해시태그 문자열 목록 JSON",
    )
    skipped_categories = models.JSONField(
        default=list,
        blank=True,
        db_comment=(
            "입은 옷 지정과 겹쳐 사진 등록에서 제외한 옷장 대분류 목록 JSON "
            "(예: 상의/하의)"
        ),
    )
    status = models.CharField(
        max_length=16,
        choices=[
            (LookbookStatus.REGISTERED.value, "등록"),
            (LookbookStatus.PROCESSING.value, "처리중"),
            (LookbookStatus.COMPLETED.value, "완료"),
            (LookbookStatus.FAILED.value, "실패"),
        ],
        default=LookbookStatus.REGISTERED.value,
        db_comment="이미지 처리 상태 (REGISTERED/PROCESSING/COMPLETED/FAILED)",
    )
    processing_error_code = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_comment="전체 이미지 처리 실패 오류 코드",
    )
    processing_error_message = models.TextField(
        blank=True,
        default="",
        db_comment="전체 이미지 처리 실패 오류 메시지",
    )
    processing_started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="이미지 프로세서 작업 시작 시각",
    )
    processing_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="이미지 프로세서 작업 종료 시각",
    )
    callback_applied_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="최종 callback을 DB에 최초 반영한 시각",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_comment="룩북 생성 시각")
    updated_at = models.DateTimeField(auto_now=True, db_comment="룩북 수정 시각")

    class Meta:
        db_table = "lookbook_post"
        db_table_comment = (
            "사용자가 올린 룩 한 벌 (대표 사진·입은 옷·일정·해시태그와 이미지 처리 상태)"
        )
        ordering = ["-created_at"]  # noqa: RUF012 - Django Meta option
        indexes = [  # noqa: RUF012 - Django Meta option
            models.Index(
                fields=["user", "-created_at"],
                name="lookbook_user_created_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="lookbook_status_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.pk} ({self.status})"


class LookbookWardrobeItem(models.Model):
    """룩북과 옷장 아이템의 N:N 연결 행."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="룩북-옷장 아이템 연결 UUID",
    )
    lookbook = models.ForeignKey(
        LookbookPost,
        on_delete=models.CASCADE,
        related_name="wardrobe_links",
        db_comment="연결 대상 룩북 FK (lookbook_post.id)",
    )
    wardrobe_item = models.ForeignKey(
        "wardrobe.WardrobeItem",
        on_delete=models.CASCADE,
        related_name="lookbook_links",
        db_comment="연결 대상 옷장 아이템 FK (wardrobe_item.id)",
    )
    link_type = models.CharField(
        max_length=16,
        choices=[
            (LookbookLinkType.SELECTED.value, "사용자 직접 선택"),
            (LookbookLinkType.EXTRACTED.value, "룩 사진에서 추출"),
        ],
        default=LookbookLinkType.SELECTED.value,
        db_comment="아이템이 붙은 경로 (SELECTED: 직접 선택 / EXTRACTED: 사진 추출)",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        db_comment="룩북 안의 옷장 아이템 표시 순서 (0부터 시작)",
    )
    snapshot = models.JSONField(
        default=dict,
        blank=True,
        db_comment="연결 당시 옷장 아이템의 이미지·이름·카테고리·태그 스냅샷 JSON",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_comment="룩북-옷장 아이템 연결 생성 시각",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_comment="룩북-옷장 아이템 연결 수정 시각",
    )

    class Meta:
        db_table = "lookbook_wardrobe_item"
        db_table_comment = "룩북과 옷장 아이템의 N:N 연결 정보"
        ordering = ["sort_order", "created_at"]  # noqa: RUF012 - Django Meta option
        constraints = [  # noqa: RUF012 - Django Meta option
            models.UniqueConstraint(
                fields=["lookbook", "wardrobe_item"],
                name="uq_lookbook_wardrobe_link",
            )
        ]
        indexes = [  # noqa: RUF012 - Django Meta option
            models.Index(
                fields=["lookbook", "sort_order"],
                name="lookbook_wardrobe_order_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.lookbook_id}:{self.wardrobe_item_id}"
