from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import OutfitAnalysis
from .services import storage


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


class OutfitAnalysisDetailSerializer(serializers.ModelSerializer):
    """이력 상세. 질의에 쓴 스냅샷과 LLM 요청·응답 원본을 그대로 노출한다."""

    image_url = serializers.SerializerMethodField()

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
