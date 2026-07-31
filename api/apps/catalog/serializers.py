"""상품 임베딩 내부 API 요청 검증."""

from rest_framework import serializers


class ProductEmbeddingStatusSerializer(serializers.Serializer):
    target_version = serializers.CharField(max_length=200)
    reset_stale = serializers.BooleanField(default=False)
    stale_job_minutes = serializers.IntegerField(
        min_value=1,
        max_value=24 * 60,
        default=30,
    )


class ProductEmbeddingClaimSerializer(serializers.Serializer):
    target_version = serializers.CharField(max_length=200)
    limit = serializers.IntegerField(min_value=1, max_value=256)


class ProductEmbeddingActionSerializer(serializers.Serializer):
    generation = serializers.IntegerField(min_value=1)
    attempt_count = serializers.IntegerField(min_value=1)


class ProductEmbeddingImageSerializer(ProductEmbeddingActionSerializer):
    image_s3_key = serializers.CharField(max_length=2048)
    image_checksum = serializers.RegexField(r"^[0-9a-fA-F]{64}$")


class ProductEmbeddingCompleteSerializer(ProductEmbeddingImageSerializer):
    embedding_version = serializers.CharField(max_length=200)


class ProductEmbeddingFailureSerializer(ProductEmbeddingActionSerializer):
    error = serializers.CharField(max_length=4000)
    max_retries = serializers.IntegerField(min_value=0, max_value=20)
    retry_delay_seconds = serializers.IntegerField(
        min_value=1,
        max_value=24 * 60 * 60,
    )
    transient = serializers.BooleanField(default=True)
