import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("recommend", "0009_outfitrenderjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyLook",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_comment="오늘의 룩 UUID (외부 노출 식별자)",
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "look_date",
                    models.DateField(
                        db_comment="추천이 속한 날짜 (서비스 로컬 기준, Asia/Seoul)",
                        verbose_name="추천 날짜",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("QUEUED", "대기중"),
                            ("PROCESSING", "생성 진행중"),
                            ("SUCCEEDED", "생성 완료"),
                            ("FAILED", "생성 실패"),
                            ("EMPTY", "추천 후보 없음"),
                        ],
                        db_comment="생성 상태 (QUEUED/PROCESSING/SUCCEEDED/FAILED/EMPTY)",
                        default="QUEUED",
                        max_length=16,
                    ),
                ),
                (
                    "weather",
                    models.JSONField(
                        blank=True,
                        db_comment="추천에 사용한 날씨 JSON (지역·기온·하늘 상태 등)",
                        default=dict,
                        verbose_name="날씨 스냅샷",
                    ),
                ),
                (
                    "body",
                    models.JSONField(
                        blank=True,
                        db_comment="추천에 사용한 신체치수 JSON (미등록이면 NULL)",
                        null=True,
                        verbose_name="신체치수 스냅샷",
                    ),
                ),
                (
                    "body_profile",
                    models.JSONField(
                        blank=True,
                        db_comment="치수에서 판정한 실루엣·BMI·비율 JSON",
                        default=dict,
                        verbose_name="체형 판정 스냅샷",
                    ),
                ),
                (
                    "pursuit",
                    models.JSONField(
                        blank=True,
                        db_comment="추천에 사용한 추구미 JSON (미등록이면 NULL)",
                        null=True,
                        verbose_name="추구미 스냅샷",
                    ),
                ),
                (
                    "candidates",
                    models.JSONField(
                        blank=True,
                        db_comment="리트리버가 뽑은 골든 코디 후보 요약 배열",
                        default=list,
                        verbose_name="리트리버 후보",
                    ),
                ),
                (
                    "rules_version",
                    models.CharField(
                        blank=True,
                        db_comment="추천에 사용한 체형 규칙표 스키마 버전",
                        default="",
                        max_length=40,
                    ),
                ),
                (
                    "llm_model",
                    models.CharField(
                        blank=True,
                        db_comment="오늘의 룩 설명 생성에 사용한 Gemini 모델명",
                        default="",
                        max_length=120,
                    ),
                ),
                (
                    "llm_request",
                    models.JSONField(
                        blank=True,
                        db_comment="Gemini에 보낸 오늘의 룩 설명 생성 요청 JSON",
                        default=dict,
                    ),
                ),
                (
                    "llm_response",
                    models.JSONField(
                        blank=True,
                        db_comment="Gemini가 반환한 오늘의 룩 설명 원본 응답 JSON",
                        default=dict,
                    ),
                ),
                (
                    "llm_latency_ms",
                    models.PositiveIntegerField(
                        blank=True,
                        db_comment="오늘의 룩 설명 생성 소요 시간 (ms)",
                        null=True,
                    ),
                ),
                (
                    "result",
                    models.JSONField(
                        blank=True,
                        db_comment="오늘의 룩 결과 JSON (코디·아이템·공통 렌더 S3 참조)",
                        default=dict,
                        verbose_name="추천 결과",
                    ),
                ),
                (
                    "error",
                    models.TextField(
                        blank=True,
                        db_comment="내부 실패 사유 (성공 시 빈 문자열)",
                        default="",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, db_comment="오늘의 룩 생성 접수 시각"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, db_comment="오늘의 룩 마지막 수정 시각"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_comment="추천 대상 사용자 FK (users.id)",
                        db_index=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_looks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "daily_looks",
                "db_table_comment": "사용자별 하루 1건의 오늘의 룩 추천",
                "ordering": ["-look_date"],
                "indexes": [
                    models.Index(fields=["status"], name="idx_daily_look_status")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "look_date"), name="uq_daily_look_user_date"
                    )
                ],
            },
        ),
    ]
