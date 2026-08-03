from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers


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
    evaluation = OutfitEvaluationSerializer()
    context = AnalysisContextSerializer()
