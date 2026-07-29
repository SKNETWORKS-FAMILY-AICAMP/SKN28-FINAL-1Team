"""옷장 아이템 등록 도메인 모델.

설계 문서: Confluence > 설계 > "옷장 기능 전체 설계".
- DB가 source of truth. Qdrant 벡터는 파생 저장소 (services/vectors.py).
- 업로드 1건 = WardrobeUploadJob 1건 → 처리 결과 아이템 N건(WardrobeItem).

테이블·컬럼 comment는 db_table_comment/db_comment로 모델이 소유한다
(새 필드 추가 시 반드시 db_comment 지정).
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

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="job UUID (외부 노출 식별자)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wardrobe_jobs",
        db_comment="업로드 사용자 FK (users.id)",
    )
    source_s3_key = models.CharField(
        "원본 S3 키", max_length=512, db_comment="업로드 원본 이미지 S3 키"
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_comment="처리 상태 (PENDING/PROCESSING/DONE/FAILED)",
    )
    error_message = models.TextField(
        blank=True, default="", db_comment="실패 시 오류 메시지"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_comment="job 생성(접수) 시각")
    finished_at = models.DateTimeField(
        null=True, blank=True, db_comment="처리 종료 시각 (DONE/FAILED 전환 시)"
    )

    class Meta:
        # 프로젝트 규칙: db_table 명시 (기본값이면 wardrobe_wardrobeuploadjob처럼
        # 앱 라벨과 모델명 접두사가 중복된다)
        db_table = "wardrobe_upload_job"
        db_table_comment = "옷장 사진 업로드 처리 job (이미지 프로세서 콜백 멱등성 기준)"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return f"job {self.id} ({self.status})"


class WardrobeItem(models.Model):
    """분리·태깅된 옷장 아이템 1벌. 태그 스키마는 taxonomy.py를 따른다.

    벡터는 DB에 저장하지 않고 Qdrant(wardrobe_items 컬렉션)에만 둔다.
    confirmed=False는 사용자 확인 대기 상태 — 추천 검색 대상에서 제외한다.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="아이템 UUID (외부 노출 식별자)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wardrobe_items",
        db_comment="소유 사용자 FK (users.id)",
    )
    job = models.ForeignKey(
        WardrobeUploadJob,
        on_delete=models.SET_NULL,
        null=True,
        related_name="items",
        db_comment="생성 출처 업로드 job FK (wardrobe_upload_job.id, job 삭제 시 NULL)",
    )
    s3_key = models.CharField(
        "크롭 이미지 S3 키", max_length=512, db_comment="배경 제거·크롭된 아이템 이미지 S3 키"
    )

    # ── 캡셔닝(태깅) 필드 — Confluence 태그 체계 ──
    item_name = models.CharField(
        max_length=120, blank=True, default="", db_comment="아이템 표시 이름 (태깅 생성 또는 사용자 수정)"
    )
    category_large = models.CharField(
        max_length=20, db_comment="대분류 (상의/하의/아우터/신발/가방 등)"
    )
    category_small = models.CharField(
        max_length=30, blank=True, default="", db_comment="소분류 (티셔츠/청바지 등)"
    )
    season = ArrayField(
        models.CharField(max_length=10), default=list, blank=True, db_comment="계절 태그 배열"
    )
    style = ArrayField(
        models.CharField(max_length=10), default=list, blank=True, db_comment="스타일 태그 배열"
    )
    color = models.CharField(max_length=10, blank=True, default="", db_comment="색상 태그")
    pattern = models.CharField(max_length=10, blank=True, default="", db_comment="패턴 태그")
    fit = models.CharField(max_length=10, blank=True, default="", db_comment="핏 태그")
    material = models.CharField(max_length=10, blank=True, default="", db_comment="소재 태그")
    sleeve = models.CharField(max_length=10, blank=True, default="", db_comment="소매 길이 태그")
    length = models.CharField(max_length=10, blank=True, default="", db_comment="기장 태그")
    usage = ArrayField(
        models.CharField(max_length=20), default=list, blank=True, db_comment="용도(TPO) 태그 배열"
    )
    layer_role = models.CharField(
        max_length=10, blank=True, default="", db_comment="레이어링 역할 태그"
    )
    layer_order = models.PositiveSmallIntegerField(
        null=True, blank=True, db_comment="레이어링 착용 순서 (안쪽부터 1)"
    )

    # ── 메타 ──
    seg_meta = models.JSONField(
        "세그멘테이션 메타(raw_label·score·bbox 등)",
        default=dict,
        blank=True,
        db_comment="세그멘테이션 메타 JSON (raw_label/score/bbox 등)",
    )
    confirmed = models.BooleanField(
        "사용자 확정 여부",
        default=False,
        db_comment="사용자 확정 여부 (false: 확인 대기 — 추천 검색 제외)",
    )
    embedding_version = models.CharField(
        max_length=40, blank=True, default="", db_comment="Qdrant 임베딩 버전 (재임베딩 판단 기준)"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_comment="행 생성 시각")
    updated_at = models.DateTimeField(auto_now=True, db_comment="행 수정 시각")

    class Meta:
        db_table = "wardrobe_item"
        db_table_comment = "사용자 옷장 아이템 (업로드 사진에서 분리·태깅된 옷 1벌, 벡터는 Qdrant에 별도 저장)"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "category_large"]),
            models.Index(fields=["user", "confirmed"]),
        ]

    def __str__(self) -> str:
        return f"{self.item_name or self.category_large} ({self.user_id})"
