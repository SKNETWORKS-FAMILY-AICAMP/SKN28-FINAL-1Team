from django.core.files.uploadedfile import UploadedFile
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


class OutfitAnalysisResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["completed"])
    # 기록 저장에 실패해도 평가는 반환하므로 null이 될 수 있다 (services/analysis.py 참고)
    analysis_id = serializers.UUIDField(
        allow_null=True,
        help_text="저장된 평가 기록 ID. 이력 조회에 사용합니다. 기록 실패 시 null.",
    )
    evaluation = OutfitEvaluationSerializer()
    context = AnalysisContextSerializer()


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
            "llm_model",
            "request_payload",
            "response_payload",
            "evaluation",
            "latency_ms",
            "error_message",
            "created_at",
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
