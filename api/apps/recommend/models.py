"""코디 사진 AI 평가 기록 모델.

`POST /api/v1/outfits/analyze/` 요청 1건 = `OutfitAnalysis` 1행.

설계 원칙
- **스냅샷 저장**: 날씨·체형·추구미는 FK로 참조하지 않고 요청 시점 값을 복사해 둔다.
  프로필과 날씨는 계속 바뀌므로, 참조만 두면 "왜 이 평가가 나왔는지"를 나중에
  재현할 수 없다.
- **질의와 응답을 함께 보관**: LLM에 보낸 요청 본문과 원본 응답을 그대로 남겨
  프롬프트·모델 교체 전후의 평가 품질을 비교할 수 있게 한다.
- **이미지는 S3**: 원본 사진은 DB에 넣지 않고 S3 키만 저장한다 (wardrobe와 동일).
- **옷장 등록은 곁가지**: 로그인 사용자가 원하면 같은 사진을 옷장 아이템 등록
  파이프라인에도 넘긴다. 실패해도 코디 평가는 그대로 진행된다 (services/wardrobe_link.py).
- **익명 요청도 기록**: 이 API는 AllowAny라 user가 NULL인 행이 정상적으로 존재한다.
  익명 행은 소유자를 특정할 수 없어 UUID를 아는 사람만 조회할 수 있고(뷰에서 제어),
  일정 시간이 지나면 조회를 막는다.

테이블·컬럼 comment는 db_table_comment/db_comment로 모델이 소유한다
(새 필드 추가 시 반드시 db_comment 지정 — CLAUDE.md 5장).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class OutfitAnalysis(models.Model):
    """코디 사진 1장에 대한 LLM 평가 요청·결과 1건."""

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "대기중"
        PROCESSING = "PROCESSING", "평가 진행중"
        SUCCEEDED = "SUCCEEDED", "평가 완료"
        FAILED = "FAILED", "평가 실패"

    #: 아직 결과가 나오지 않아 클라이언트가 폴링을 계속해야 하는 상태
    PENDING_STATUSES = (Status.QUEUED, Status.PROCESSING)

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="평가 UUID (외부 노출 식별자)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outfit_analyses",
        # FK 기본 인덱스는 아래 (user, -created_at) 복합 인덱스와 선두 컬럼이 겹쳐 불필요하다
        db_index=False,
        db_comment="요청 사용자 FK (users.id, 비로그인 요청이면 NULL)",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
        db_comment="평가 상태 (QUEUED/PROCESSING/SUCCEEDED/FAILED)",
    )

    # ── 입력(사진·위치) ──
    image_s3_key = models.CharField(
        "원본 사진 S3 키",
        max_length=512,
        blank=True,
        default="",
        db_comment="평가 대상 코디 사진 S3 키 (업로드 미설정 또는 실패 시 빈 문자열)",
    )
    image_content_type = models.CharField(
        max_length=50,
        blank=True,
        default="",
        db_comment="업로드 이미지 MIME 타입 (image/jpeg, image/png, image/webp)",
    )
    image_bytes = models.PositiveIntegerField(
        null=True, blank=True, db_comment="업로드 이미지 크기 (bytes)"
    )
    requested_lat = models.FloatField(
        null=True, blank=True, db_comment="요청 위도 (클라이언트가 보낸 값, 미전달 시 NULL)"
    )
    requested_lon = models.FloatField(
        null=True, blank=True, db_comment="요청 경도 (클라이언트가 보낸 값, 미전달 시 NULL)"
    )
    resolved_lat = models.FloatField(
        null=True,
        blank=True,
        db_comment="날씨 조회에 실제 사용한 위도 (미전달·국내 범위 밖이면 서울 좌표로 대체)",
    )
    resolved_lon = models.FloatField(
        null=True,
        blank=True,
        db_comment="날씨 조회에 실제 사용한 경도 (미전달·국내 범위 밖이면 서울 좌표로 대체)",
    )

    # ── LLM 질의 구성 정보 (요청 시점 스냅샷) ──
    weather = models.JSONField(
        "날씨 스냅샷",
        default=dict,
        blank=True,
        db_comment="질의에 사용한 날씨 JSON (region/temperature/sky_state/is_stale/observed_at)",
    )
    body = models.JSONField(
        "신체치수 스냅샷",
        null=True,
        blank=True,
        db_comment="질의에 사용한 신체치수·성별 JSON (비로그인 또는 미등록이면 NULL)",
    )
    pursuit = models.JSONField(
        "추구미 스냅샷",
        null=True,
        blank=True,
        db_comment="질의에 사용한 추구미 JSON (preferred/avoided, 비로그인이면 NULL)",
    )
    personalized = models.BooleanField(
        default=False,
        db_comment="개인화 정보 반영 여부 (로그인 요청이면 true)",
    )

    # ── 옷장 등록 연계 (선택) ──
    save_to_wardrobe = models.BooleanField(
        default=False,
        db_comment="이 사진을 옷장 아이템 등록에도 넘길지 여부 (비로그인 요청이면 항상 false)",
    )
    wardrobe_job = models.ForeignKey(
        "wardrobe.WardrobeUploadJob",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outfit_analyses",
        db_comment="연계 생성한 옷장 등록 job FK (wardrobe_upload_job.id, 미요청·적재 실패 시 NULL)",
    )

    # ── LLM 호출·응답 ──
    llm_model = models.CharField(
        max_length=80,
        blank=True,
        default="",
        db_comment="평가에 사용한 LLM 모델명 (예: gemini-3.5-flash)",
    )
    request_payload = models.JSONField(
        "LLM 요청 본문",
        default=dict,
        blank=True,
        db_comment="LLM에 보낸 요청 본문 JSON 전체 (사진 base64는 자리표시자로 대체)",
    )
    response_payload = models.JSONField(
        "LLM 원본 응답",
        default=dict,
        blank=True,
        db_comment="LLM 원본 응답 JSON 전체 (candidates/usageMetadata 등, 실패 시 오류 본문)",
    )
    evaluation = models.JSONField(
        "평가 결과",
        null=True,
        blank=True,
        db_comment="파싱된 평가 결과 JSON (API 응답의 evaluation 필드와 동일, 실패 시 NULL)",
    )
    llm_image_bytes = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_comment="LLM에 실제 전송한 축소본 크기 (bytes, image_bytes는 원본 크기)",
    )
    latency_ms = models.PositiveIntegerField(
        null=True, blank=True, db_comment="LLM 호출 소요 시간 (밀리초)"
    )
    attempts = models.PositiveSmallIntegerField(
        default=0, db_comment="워커 처리 시도 횟수 (재시도 포함)"
    )
    error_message = models.TextField(
        blank=True, default="", db_comment="실패 시 오류 메시지"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, db_comment="요청 접수 시각"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="워커가 처리를 시작한 시각 (큐 대기시간 측정·좀비 정리 기준)",
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="평가 종료 시각 (SUCCEEDED/FAILED 전환 시)",
    )

    class Meta:
        # 프로젝트 규칙: db_table 명시 (기본값이면 recommend_outfitanalysis)
        db_table = "outfit_analysis"
        db_table_comment = (
            "코디 사진 AI 평가 기록 (질의에 쓴 날씨·체형·추구미 스냅샷과 LLM 요청·응답 원본 보관)"
        )
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="ix_outfit_analysis_user"),
            models.Index(fields=["status", "-created_at"], name="ix_outfit_analysis_stat"),
        ]

    def __str__(self) -> str:
        return f"outfit-analysis {self.id} ({self.status})"

    @property
    def overall_score(self) -> int | None:
        """목록 응답에서 쓰는 요약 점수. 평가 실패 행이면 None."""
        return (self.evaluation or {}).get("overall_score")

    @property
    def is_pending(self) -> bool:
        return self.status in self.PENDING_STATUSES

    def llm_context(self) -> dict:
        """LLM 질의에 넣을 컨텍스트를 접수 시점 스냅샷에서 복원한다.

        워커는 이 값을 쓰고 컨텍스트를 다시 만들지 않는다. 큐에서 대기하는 사이
        날씨가 바뀌거나 사용자가 추구미를 수정해도, 사용자가 사진을 올린 그 순간의
        조건으로 평가해야 결과와 기록이 일치한다.
        """
        return {
            "weather": self.weather or {},
            "pursuit": self.pursuit,
            "body": self.body,
            "personalized": self.personalized,
        }
