"""옷장 아이템 등록 도메인 모델.

설계 문서: Confluence > 설계 > "옷장 기능 전체 설계".
- DB가 source of truth. Qdrant 벡터는 파생 저장소 (services/vectors.py).
- 업로드 1건 = WardrobeUploadJob 1건 → 처리 결과 아이템 N건(WardrobeItem).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models


class WardrobeUploadJob(models.Model):
    """사진 업로드 → 이미지 프로세서 처리 job. 콜백 멱등성의 기준 키."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "대기"
        PROCESSING = "PROCESSING", "처리중"
        DONE = "DONE", "완료"
        FAILED = "FAILED", "실패"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wardrobe_jobs"
    )
    source_s3_key = models.CharField("원본 S3 키", max_length=512)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # 프로젝트 규칙: db_table 명시 (기본값이면 wardrobe_wardrobeuploadjob처럼
        # 앱 라벨과 모델명 접두사가 중복된다)
        db_table = "wardrobe_upload_job"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return f"job {self.id} ({self.status})"


class WardrobeItem(models.Model):
    """분리·태깅된 옷장 아이템 1벌. 태그 스키마는 taxonomy.py를 따른다.

    벡터는 DB에 저장하지 않고 Qdrant(wardrobe_items 컬렉션)에만 둔다.
    confirmed=False는 사용자 확인 대기 상태 — 추천 검색 대상에서 제외한다.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wardrobe_items"
    )
    job = models.ForeignKey(
        WardrobeUploadJob, on_delete=models.SET_NULL, null=True, related_name="items"
    )
    s3_key = models.CharField("크롭 이미지 S3 키", max_length=512)

    # ── 캡셔닝(태깅) 필드 — Confluence 태그 체계 ──
    item_name = models.CharField(max_length=120, blank=True, default="")
    category_large = models.CharField(max_length=20)
    category_small = models.CharField(max_length=30, blank=True, default="")
    season = ArrayField(models.CharField(max_length=10), default=list, blank=True)
    style = ArrayField(models.CharField(max_length=10), default=list, blank=True)
    color = models.CharField(max_length=10, blank=True, default="")
    pattern = models.CharField(max_length=10, blank=True, default="")
    fit = models.CharField(max_length=10, blank=True, default="")
    material = models.CharField(max_length=10, blank=True, default="")
    sleeve = models.CharField(max_length=10, blank=True, default="")
    length = models.CharField(max_length=10, blank=True, default="")
    usage = ArrayField(models.CharField(max_length=20), default=list, blank=True)
    layer_role = models.CharField(max_length=10, blank=True, default="")
    layer_order = models.PositiveSmallIntegerField(null=True, blank=True)

    # ── 메타 ──
    seg_meta = models.JSONField(
        "세그멘테이션 메타(raw_label·score·bbox 등)", default=dict, blank=True
    )
    confirmed = models.BooleanField("사용자 확정 여부", default=False)
    embedding_version = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wardrobe_item"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "category_large"]),
            models.Index(fields=["user", "confirmed"]),
        ]

    def __str__(self) -> str:
        return f"{self.item_name or self.category_large} ({self.user_id})"
