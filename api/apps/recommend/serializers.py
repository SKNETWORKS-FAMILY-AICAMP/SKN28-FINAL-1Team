from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers


MAX_OUTFIT_IMAGE_SIZE_MB = 15
ALLOWED_OUTFIT_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


class OutfitAnalysisRequestSerializer(serializers.Serializer):
    """코디 분석을 위해 업로드하는 사진을 검증한다."""

    image = serializers.ImageField(
        help_text="분석할 코디 사진 (JPEG, PNG, WebP, 최대 15MB)",
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


class ReceivedImageSerializer(serializers.Serializer):
    name = serializers.CharField(help_text="업로드한 파일명")
    size = serializers.IntegerField(help_text="파일 크기 (byte)")
    content_type = serializers.CharField(help_text="파일의 MIME 타입")


class OutfitAnalysisResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    status = serializers.ChoiceField(choices=["pending_evaluation"])
    received = ReceivedImageSerializer()
    result = serializers.JSONField(allow_null=True)
