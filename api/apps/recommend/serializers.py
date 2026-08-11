import logging

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.urls import reverse
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    DailyLook,
    OutfitAnalysis,
    OutfitComposition,
    OutfitCompositionItem,
    OutfitRenderJob,
    RecommendationFeedback,
    RecommendationResult,
)
from .services import storage, wardrobe_link

MAX_OUTFIT_IMAGE_SIZE_MB = 15
ALLOWED_OUTFIT_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


class OutfitAnalysisRequestSerializer(serializers.Serializer):
    """코디 평가 사진과 선택적인 위치를 검증한다."""

    image = serializers.ImageField(
        help_text="평가할 코디 사진 (JPEG, PNG, WebP, 최대 15MB)",
    )
    lat = serializers.FloatField(
        required=False,
        min_value=33.0,
        max_value=39.5,
        help_text="현재 위치 위도. 생략하면 서울 기준 날씨를 사용합니다.",
    )
    lon = serializers.FloatField(
        required=False,
        min_value=124.0,
        max_value=132.0,
        help_text="현재 위치 경도. 생략하면 서울 기준 날씨를 사용합니다.",
    )
    save_to_wardrobe = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "이 사진을 옷장 아이템 등록에도 넘길지 여부. "
            "**로그인 요청에만 적용**되며, 비로그인 요청에서는 무시됩니다(옷장은 사용자 소유 데이터). "
            "true면 응답의 wardrobe_job_id로 GET /api/v1/wardrobe/uploads/{job_id}/ 에서 "
            "등록 진행 상황을 따로 조회할 수 있습니다."
        ),
    )

    def validate_image(self, image: UploadedFile) -> UploadedFile:
        if image.size > MAX_OUTFIT_IMAGE_SIZE_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"이미지는 {MAX_OUTFIT_IMAGE_SIZE_MB}MB 이하여야 합니다."
            )
        if image.content_type not in ALLOWED_OUTFIT_IMAGE_CONTENT_TYPES:
            raise serializers.ValidationError(
                "지원하지 않는 이미지 형식입니다. JPEG, PNG, WebP만 사용할 수 있습니다."
            )
        return image

    def validate(self, attrs: dict) -> dict:
        if ("lat" in attrs) != ("lon" in attrs):
            raise serializers.ValidationError(
                "lat과 lon은 함께 입력하거나 모두 생략해야 합니다."
            )
        return attrs


class OutfitEvaluationSerializer(serializers.Serializer):
    overall_score = serializers.IntegerField(min_value=0, max_value=100)
    summary = serializers.CharField()
    strengths = serializers.ListField(child=serializers.CharField())
    weather_comment = serializers.CharField()
    personalization_comment = serializers.CharField()
    styling_tips = serializers.ListField(child=serializers.CharField())


class AnalysisContextSerializer(serializers.Serializer):
    weather = serializers.JSONField()
    personalized = serializers.BooleanField()
    used_pursuit = serializers.BooleanField()
    used_body = serializers.BooleanField()


class OutfitAnalysisAcceptedSerializer(serializers.Serializer):
    """202 접수 응답. 분석 결과는 poll_url로 따로 조회한다."""

    analysis_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=OutfitAnalysis.Status.choices)
    poll_url = serializers.CharField(
        help_text="결과 조회 경로. 이 URL을 poll_after_ms 간격으로 호출한다."
    )
    poll_after_ms = serializers.IntegerField(
        help_text="다음 조회까지 기다릴 시간(ms). 프론트가 간격을 하드코딩하지 않게 서버가 준다."
    )
    estimated_seconds = serializers.IntegerField(
        help_text="예상 소요 시간(초). 안내 문구용."
    )
    claim_token = serializers.CharField(
        allow_null=True,
        help_text=(
            "비로그인 접수 건의 소유권 이전용 1회성 토큰. 로그인 접수면 null. "
            "**이 응답에서만 받을 수 있으니 앱이 로컬에 보관**했다가, 로그인 직후 "
            "POST /api/v1/outfits/analyses/claim/ 으로 보내세요. 유효 시간이 짧습니다."
        ),
    )
    wardrobe_job_id = serializers.UUIDField(
        allow_null=True,
        help_text=(
            "옷장 등록 job ID. save_to_wardrobe를 요청하지 않았거나 비로그인이면 null. "
            "GET /api/v1/wardrobe/uploads/{job_id}/ 로 진행 상황을 조회합니다."
        ),
    )


class OutfitAnalysisPublicSerializer(serializers.ModelSerializer):
    """익명 조회용 — UUID만 아는 사람에게 내려주는 축소 응답.

    UUID는 URL·로그·Referer로 새어나갈 수 있다. 평가 문구가 노출되는 것과 본인 사진·
    체형이 노출되는 것은 무게가 다르므로, 개인 스냅샷과 LLM 원본은 여기서 뺀다.
    """

    analysis_id = serializers.UUIDField(source="id", read_only=True)
    evaluation = serializers.SerializerMethodField()
    context = serializers.SerializerMethodField()
    poll_after_ms = serializers.SerializerMethodField()
    detail = serializers.SerializerMethodField()

    class Meta:
        model = OutfitAnalysis
        fields = [
            "analysis_id",
            "status",
            "evaluation",
            "context",
            "poll_after_ms",
            "detail",
            "created_at",
            "finished_at",
        ]

    @extend_schema_field(OutfitEvaluationSerializer(allow_null=True))
    def get_evaluation(self, obj: OutfitAnalysis) -> dict | None:
        """완료 전에는 null. 프론트는 status로 판단하고 이 값은 참고만 한다."""
        return obj.evaluation

    @extend_schema_field(AnalysisContextSerializer)
    def get_context(self, obj: OutfitAnalysis) -> dict:
        # 개인화에 무엇이 쓰였는지는 알려주되(로그인 유도 안내에 쓴다) 값 자체는 주지 않는다
        return {
            "weather": obj.weather,
            "personalized": obj.personalized,
            "used_pursuit": obj.pursuit is not None,
            "used_body": obj.body is not None,
        }

    def get_poll_after_ms(self, obj: OutfitAnalysis) -> int | None:
        return settings.OUTFIT_POLL_AFTER_MS if obj.is_pending else None

    def get_detail(self, obj: OutfitAnalysis) -> str | None:
        """실패 사유(error_message)는 내부용이라 사용자 문구로 갈음한다."""
        if obj.status != OutfitAnalysis.Status.FAILED:
            return None
        return "코디 평가를 완료하지 못했습니다. 다시 시도해주세요."


class OutfitAnalysisListItemSerializer(serializers.ModelSerializer):
    """이력 목록용 요약. LLM 요청·응답 원본은 상세에서만 내려준다."""

    overall_score = serializers.IntegerField(allow_null=True, read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = OutfitAnalysis
        fields = [
            "id",
            "status",
            "overall_score",
            "summary",
            "weather",
            "personalized",
            "created_at",
        ]

    def get_summary(self, obj: OutfitAnalysis) -> str:
        return (obj.evaluation or {}).get("summary", "")


class WardrobeLinkedItemSerializer(serializers.Serializer):
    """옷장 등록이 끝난 뒤 생성된 아이템 1건의 요약.

    전체 태그(season/style/pattern/fit/material/sleeve/length/usage/layer_*/seg_meta)는
    옷장 API에서 본다 — GET /api/v1/wardrobe/items/ 또는
    GET /api/v1/wardrobe/uploads/{job_id}/.
    """

    id = serializers.UUIDField(help_text="옷장 아이템 UUID")
    item_name = serializers.CharField(allow_blank=True, help_text="아이템 표시 이름")
    category_large = serializers.CharField(help_text="대분류 (상의/하의/아우터 등)")
    category_small = serializers.CharField(allow_blank=True, help_text="소분류")
    color = serializers.CharField(allow_blank=True, help_text="색상 태그")
    image_url = serializers.CharField(
        allow_null=True,
        help_text="배경 제거·크롭된 아이템 이미지 presigned URL (발급 실패 시 null)",
    )
    confirmed = serializers.BooleanField(
        help_text="사용자 확정 여부. false면 태깅 확인 대기 상태다(추천 검색 제외)."
    )


class WardrobeLinkSerializer(serializers.Serializer):
    """save_to_wardrobe로 연계된 옷장 등록 job의 진행 상황과 결과."""

    job_id = serializers.UUIDField(help_text="옷장 등록 job UUID")
    status = serializers.CharField(help_text="등록 상태 (PENDING/PROCESSING/DONE/FAILED)")
    error_message = serializers.CharField(
        allow_blank=True, help_text="등록 실패 사유 (FAILED가 아니면 빈 문자열)"
    )
    created_at = serializers.DateTimeField(help_text="job 생성 시각")
    finished_at = serializers.DateTimeField(
        allow_null=True, help_text="등록 종료 시각 (진행 중이면 null)"
    )
    items = WardrobeLinkedItemSerializer(
        many=True,
        help_text="생성된 옷장 아이템 요약. **status가 DONE일 때만** 채워진다.",
    )


class OutfitAnalysisDetailSerializer(serializers.ModelSerializer):
    """이력 상세. 질의에 쓴 스냅샷과 LLM 요청·응답 원본을 그대로 노출한다."""

    image_url = serializers.SerializerMethodField()
    wardrobe = serializers.SerializerMethodField()

    class Meta:
        model = OutfitAnalysis
        fields = [
            "id",
            "status",
            "image_url",
            "image_content_type",
            "image_bytes",
            "requested_lat",
            "requested_lon",
            "resolved_lat",
            "resolved_lon",
            "weather",
            "body",
            "pursuit",
            "personalized",
            "save_to_wardrobe",
            "wardrobe_job",
            "wardrobe",
            "llm_model",
            "request_payload",
            "response_payload",
            "evaluation",
            "llm_image_bytes",
            "latency_ms",
            "attempts",
            "error_message",
            "created_at",
            "started_at",
            "finished_at",
        ]

    def get_image_url(self, obj: OutfitAnalysis) -> str | None:
        """비공개 버킷이므로 presigned GET으로만 노출한다. 발급 실패 시 null."""
        if not obj.image_s3_key or not storage.is_configured():
            return None
        try:
            return storage.presigned_get(obj.image_s3_key)
        except Exception:  # noqa: BLE001 — URL 발급 실패가 조회를 막지 않는다
            return None

    @extend_schema_field(WardrobeLinkSerializer(allow_null=True))
    def get_wardrobe(self, obj: OutfitAnalysis) -> dict | None:
        """옷장 연계 job의 상태와(완료시) 생성된 아이템 요약.

        옷장 모델 접근은 services/wardrobe_link.py가 전담한다 (두 도메인을 섞지 않기 위해).
        """
        return wardrobe_link.job_summary(obj)


class OutfitAnalysisListResponseSerializer(serializers.Serializer):
    """페이지네이션 응답 (DRF 전역 페이지네이션 미설정이라 뷰에서 직접 구성)."""

    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = OutfitAnalysisListItemSerializer(many=True)


class OutfitAnalysisClaimRequestSerializer(serializers.Serializer):
    """로그인 직후 넘겨받을 익명 접수 건들."""

    claim_tokens = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=settings.OUTFIT_CLAIM_MAX_ITEMS,
        help_text=(
            "접수 응답에서 받은 claim_token 목록. 토큰 안에 대상 식별자가 들어 있어 "
            "analysis_id를 따로 보낼 필요가 없습니다."
        ),
    )


class OutfitAnalysisClaimSkippedSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField(allow_null=True)
    reason = serializers.ChoiceField(
        choices=["invalid_token", "expired", "not_found", "already_owned"]
    )


class OutfitAnalysisClaimResponseSerializer(serializers.Serializer):
    claimed = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="소유권이 넘어온 평가 ID. 이미 본인 것이던 건도 포함합니다(멱등).",
    )
    skipped = OutfitAnalysisClaimSkippedSerializer(many=True)


logger = logging.getLogger(__name__)


def _image_url(row: dict | None) -> str | None:
    """S3 참조를 조회용 URL로 바꾼다.

    **조회 시점에** 서명한다. presigned URL은 만료되므로 DB에 미리 구워 넣으면
    며칠 뒤 죽은 링크가 남는다 (같은 이유로 Qdrant payload에도 넣지 않았다).

    서명 실패가 추천 조회 전체를 막지는 않게 한다 — 이미지가 없는 화면이
    500 화면보다 낫다.
    """
    if not row or not row.get("s3_key") or not row.get("s3_bucket"):
        return None
    try:
        return storage.presigned_get_for(str(row["s3_bucket"]), str(row["s3_key"]))
    except Exception:  # noqa: BLE001
        logger.exception("오늘의 룩 이미지 URL 생성 실패: %s", row.get("s3_key"))
        return None


class DailyLookItemSerializer(serializers.Serializer):
    """착장에 속한 의상 아이템 한 개.

    이미지는 원본 코디 사진이 아니라 파이프라인이 만든 흰 배경 파생물이다.
    그래서 원본이 노출 불가여도 이 이미지는 보여줄 수 있다.
    """

    item_key = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    sub_category = serializers.CharField(required=False, allow_blank=True)
    layer_role = serializers.CharField(required=False, allow_blank=True)
    color = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, obj: dict) -> str | None:
        return _image_url(obj)


class DailyLookResultSerializer(serializers.Serializer):
    """생성이 끝났을 때만 채워지는 추천 본문."""

    headline = serializers.CharField()
    golden_id = serializers.CharField()
    rationale_ko = serializers.CharField()
    styling_tips = serializers.ListField(child=serializers.CharField(), required=False)
    generated_by = serializers.CharField(
        required=False,
        help_text="문장을 누가 썼는지: llm | template. template이면 담백한 톤이다.",
    )
    items = DailyLookItemSerializer(many=True, required=False)
    render_image_url = serializers.SerializerMethodField()
    outfit_image_url = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_render_image_url(self, obj: dict) -> str | None:
        """정면 착용 이미지. 화면의 대표 이미지로 쓰는 값이다.

        골든 원본과 달리 사용권 제약이 없다 — 아이템 이미지를 참조로 새로 만든
        것이라 특정 인물이 담기지 않는다. 생성이 아직/실패면 null이며, 그때는
        items[].image_url 카드로 화면이 성립한다.
        """
        return _image_url(obj.get("render_image"))

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_outfit_image_url(self, obj: dict) -> str | None:
        """원본 코디 사진. 사용권이 열린 코디(exposable)에만 값이 있다."""
        return _image_url(obj.get("outfit_image"))


class DailyLookSerializer(serializers.ModelSerializer):
    """오늘의 룩 조회 응답.

    생성 전에도 200으로 내려간다. 404를 쓰면 프론트가 "없음"과 "아직"을 구분하지
    못하고, 202는 본문 스키마가 다른 응답을 만들어 클라이언트 분기를 늘린다.
    `status`와 `poll_after_ms` 두 필드로 판단하게 한다.
    """

    look_id = serializers.UUIDField(source="id", read_only=True)
    result = serializers.SerializerMethodField()
    context = serializers.SerializerMethodField()
    poll_after_ms = serializers.SerializerMethodField()
    detail = serializers.SerializerMethodField()

    class Meta:
        model = DailyLook
        fields = [
            "look_id",
            "look_date",
            "status",
            "result",
            "context",
            "poll_after_ms",
            "detail",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(DailyLookResultSerializer(allow_null=True))
    def get_result(self, obj: DailyLook) -> dict | None:
        """완성 전의 빈 JSON을 완성 결과 스키마로 직렬화하지 않는다."""
        if obj.status != DailyLook.Status.SUCCEEDED or not obj.result:
            return None
        return DailyLookResultSerializer(obj.result).data

    def get_context(self, obj: DailyLook) -> dict:
        """무엇이 개인화에 쓰였는지만 알려준다 (값 자체는 프로필 API에 있다)."""
        profile = obj.body_profile or {}
        return {
            "weather": obj.weather,
            "used_body": obj.body is not None,
            "used_pursuit": obj.pursuit is not None,
            "body_profile": profile.get("describe", ""),
            # 판정하지 못한 치수를 알려주면 프론트가 "어깨너비를 입력하면 더
            # 정확해져요" 같은 안내를 띄울 수 있다.
            "missing_measurements": profile.get("missing", []),
            "candidate_count": len(obj.candidates or []),
        }

    def get_poll_after_ms(self, obj: DailyLook) -> int | None:
        return settings.OUTFIT_POLL_AFTER_MS if obj.is_pending else None

    def get_detail(self, obj: DailyLook) -> str | None:
        """상태별 사용자 문구. 내부 error는 그대로 노출하지 않는다."""
        if obj.status in DailyLook.PENDING_STATUSES:
            return "오늘의 룩을 만들고 있어요. 잠시만 기다려주세요."
        if obj.status == DailyLook.Status.EMPTY:
            # 재시도해도 같은 결과다. 프론트는 프로필 입력을 유도해야 한다.
            return (
                "조건에 맞는 추천을 찾지 못했어요. "
                "신체치수나 추구미를 입력하면 더 잘 찾을 수 있어요."
            )
        if obj.status == DailyLook.Status.FAILED:
            return "오늘의 룩을 만들지 못했어요. 잠시 후 다시 확인해주세요."
        return None

class RecommendationHistoryQuerySerializer(serializers.Serializer):
    """추천 이력 필터와 offset 페이지네이션 입력."""

    mode = serializers.ChoiceField(
        choices=RecommendationResult.Mode.choices,
        required=False,
    )
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)
    offset = serializers.IntegerField(default=0, min_value=0)


class RecommendationFeedbackRequestSerializer(serializers.Serializer):
    """카드별 최신 피드백 입력. PUT할 때 전체 상태를 교체한다."""

    reaction = serializers.ChoiceField(choices=RecommendationFeedback.Reaction.choices)
    reason_codes = serializers.ListField(
        child=serializers.RegexField(r"^[A-Z][A-Z0-9_]{0,49}$"),
        required=False,
        default=list,
        max_length=5,
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
        trim_whitespace=True,
    )

    def validate_reason_codes(self, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise serializers.ValidationError("피드백 사유 코드는 중복될 수 없습니다.")
        return value


class RecommendationFeedbackSerializer(serializers.ModelSerializer):
    feedback_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = RecommendationFeedback
        fields = [
            "feedback_id",
            "reaction",
            "reason_codes",
            "comment",
            "created_at",
            "updated_at",
        ]


def _snapshot_text(snapshot: object, *keys: str) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    for key in keys:
        value = snapshot.get(key)
        if value not in (None, ""):
            return str(value)
    return None


class RecommendationCardItemSerializer(serializers.ModelSerializer):
    item_id = serializers.UUIDField(source="id", read_only=True)
    display_name = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    purchase_url = serializers.SerializerMethodField()

    class Meta:
        model = OutfitCompositionItem
        fields = [
            "item_id",
            "position",
            "slot",
            "source_type",
            "source_id",
            "display_name",
            "category",
            "color",
            "image_ref",
            "price_snapshot",
            "purchase_url",
            "reasons",
        ]

    def get_display_name(self, obj: OutfitCompositionItem) -> str:
        return (
            _snapshot_text(
                obj.item_snapshot,
                "display_name",
                "item_name",
                "product_name",
                "name",
                "title",
            )
            or obj.slot
        )

    def get_category(self, obj: OutfitCompositionItem) -> str | None:
        return _snapshot_text(
            obj.item_snapshot,
            "category_small",
            "category",
            "category_name",
            "category_large",
        )

    def get_color(self, obj: OutfitCompositionItem) -> str | None:
        return _snapshot_text(obj.item_snapshot, "color", "base_color")

    def get_purchase_url(self, obj: OutfitCompositionItem) -> str | None:
        if obj.source_type != OutfitCompositionItem.SourceType.PRODUCT:
            return None
        return _snapshot_text(
            obj.item_snapshot,
            "purchase_url",
            "product_url",
            "link",
            "url",
        )


class RecommendationCardSerializer(serializers.ModelSerializer):
    card_id = serializers.UUIDField(source="id", read_only=True)
    items = RecommendationCardItemSerializer(many=True, read_only=True)
    feedback = serializers.SerializerMethodField()

    class Meta:
        model = OutfitComposition
        fields = [
            "card_id",
            "rank",
            "total_product_price",
            "validation_reasons",
            "warnings",
            "items",
            "feedback",
        ]

    @extend_schema_field(RecommendationFeedbackSerializer(allow_null=True))
    def get_feedback(self, obj: OutfitComposition) -> dict | None:
        try:
            feedback = obj.feedback
        except RecommendationFeedback.DoesNotExist:
            return None
        return RecommendationFeedbackSerializer(feedback).data


class OutfitRenderJobSerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(source="id", read_only=True)
    card_id = serializers.UUIDField(source="composition_id", read_only=True)
    image_url = serializers.SerializerMethodField()
    events_url = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()

    class Meta:
        model = OutfitRenderJob
        fields = [
            "job_id",
            "card_id",
            "status",
            "cache_hit",
            "image_url",
            "output_media_type",
            "output_bytes",
            "provider",
            "model",
            "prompt_version",
            "reference_count",
            "attempts",
            "error",
            "events_url",
            "enqueued_at",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]

    def get_image_url(self, obj: OutfitRenderJob) -> str | None:
        if (
            obj.status != OutfitRenderJob.Status.SUCCEEDED
            or not obj.output_s3_bucket
            or not obj.output_s3_key
        ):
            return None
        return storage.presigned_get_for(
            obj.output_s3_bucket,
            obj.output_s3_key,
            ttl=settings.OUTFIT_RENDER_PRESIGNED_GET_TTL_SECONDS,
        )

    def get_events_url(self, obj: OutfitRenderJob) -> str:
        path = reverse("recommend:outfit-render-events", args=[obj.pk])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request is not None else path

    def get_error(self, obj: OutfitRenderJob) -> dict | None:
        if obj.status != OutfitRenderJob.Status.FAILED:
            return None
        return {"code": obj.error_code, "message": obj.error_message}


class RecommendationHistoryItemSerializer(serializers.ModelSerializer):
    result_id = serializers.UUIDField(source="id", read_only=True)
    card_count = serializers.SerializerMethodField()
    top_card = serializers.SerializerMethodField()

    class Meta:
        model = RecommendationResult
        fields = [
            "result_id",
            "session_id",
            "mode",
            "created_at",
            "card_count",
            "top_card",
        ]

    def get_card_count(self, obj: RecommendationResult) -> int:
        return len(getattr(obj, "public_compositions", ()))

    @extend_schema_field(RecommendationCardSerializer(allow_null=True))
    def get_top_card(self, obj: RecommendationResult) -> dict | None:
        cards = getattr(obj, "public_compositions", ())
        return RecommendationCardSerializer(cards[0]).data if cards else None


class RecommendationHistoryResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = RecommendationHistoryItemSerializer(many=True)


class RecommendationResultDetailSerializer(serializers.ModelSerializer):
    result_id = serializers.UUIDField(source="id", read_only=True)
    cards = serializers.SerializerMethodField()

    class Meta:
        model = RecommendationResult
        fields = [
            "result_id",
            "session_id",
            "run_id",
            "mode",
            "dataset_version",
            "created_at",
            "cards",
        ]

    @extend_schema_field(RecommendationCardSerializer(many=True))
    def get_cards(self, obj: RecommendationResult) -> list[dict]:
        cards = getattr(obj, "public_compositions", ())
        return RecommendationCardSerializer(cards, many=True).data
