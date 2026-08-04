"""스타일 캘린더 조회 API 직렬화."""

from __future__ import annotations

from collections.abc import Mapping

from rest_framework import serializers

from apps.style_calendar.models import (
    CalendarEntry,
    CalendarItem,
    CalendarWardrobeItem,
)
from apps.style_calendar.services import storage

MAX_CALENDAR_UPLOAD_MB = 15
ALLOWED_CALENDAR_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}


class StrictObjectInputMixin:
    """입력 serializer가 JSON 객체와 선언된 필드만 받도록 제한한다."""

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError(
                {"non_field_errors": ["요청 본문은 JSON 객체여야 합니다."]}
            )

        allowed_fields = set(self.fields)
        unknown_fields = set(data) - allowed_fields
        if unknown_fields:
            raise serializers.ValidationError(
                {
                    field: "허용되지 않은 필드입니다."
                    for field in sorted(unknown_fields)
                }
            )
        return super().to_internal_value(data)


class StringListField(serializers.ListField):
    """숫자를 문자열로 묵시적으로 변환하지 않는 문자열 배열 필드."""

    def to_internal_value(self, data):
        if not isinstance(data, list) or any(not isinstance(item, str) for item in data):
            raise serializers.ValidationError("문자열 배열이어야 합니다.")
        return super().to_internal_value(data)


class CalendarPeriodQuerySerializer(serializers.Serializer):
    """기간별 조회 쿼리 파라미터."""

    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError(
                {"end_date": "종료일은 시작일보다 빠를 수 없습니다."}
            )
        return attrs


class CalendarDateQuerySerializer(serializers.Serializer):
    """특정 날짜 조회 쿼리 파라미터."""

    date = serializers.DateField()


class CalendarMetadataUpdateSerializer(StrictObjectInputMixin, serializers.ModelSerializer):
    """사용자가 수정할 수 있는 캘린더 메타데이터."""

    schedule = serializers.CharField(required=False, allow_blank=True)
    tpo = StringListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
    )
    hashtags = StringListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = CalendarEntry
        fields = ("schedule", "tpo", "hashtags")



class CalendarWardrobeCreateSerializer(StrictObjectInputMixin, serializers.Serializer):
    """기존 옷장 아이템 직접 선택 캘린더 등록 요청."""

    date = serializers.DateField()
    wardrobe_item_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )
    schedule = serializers.CharField(required=False, allow_blank=True, default="")
    tpo = StringListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        default=list,
    )
    hashtags = StringListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate_wardrobe_item_ids(self, item_ids):
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("중복된 옷장 아이템 ID가 있습니다.")
        return item_ids


class CalendarPhotoCreateSerializer(StrictObjectInputMixin, serializers.Serializer):
    """사용자 사진 한 장을 이용한 캘린더 등록 요청."""

    image = serializers.ImageField()
    date = serializers.DateField()
    wardrobe_item_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    schedule = serializers.CharField(required=False, allow_blank=True, default="")
    tpo = StringListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        default=list,
    )
    hashtags = StringListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate_image(self, image):
        if image.size > MAX_CALENDAR_UPLOAD_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"이미지는 {MAX_CALENDAR_UPLOAD_MB}MB 이하여야 합니다."
            )
        if image.content_type not in ALLOWED_CALENDAR_IMAGE_TYPES:
            raise serializers.ValidationError(
                "지원하지 않는 이미지 형식입니다 (jpeg/png/webp/heic)."
            )
        return image

    def validate_wardrobe_item_ids(self, item_ids):
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError("중복된 옷장 아이템 ID가 있습니다.")
        return item_ids


class CalendarWardrobeItemSerializer(serializers.ModelSerializer):
    """캘린더와 수동 선택 옷장 아이템의 연결 정보."""

    link_id = serializers.UUIDField(source="id", read_only=True)
    wardrobe_item_id = serializers.UUIDField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CalendarWardrobeItem
        fields = (
            "link_id",
            "wardrobe_item_id",
            "image_url",
            "sort_order",
            "snapshot",
        )

    def get_image_url(self, obj) -> str:
        return storage.presigned_get(obj.snapshot.get("s3_key", ""))


class CalendarItemSerializer(serializers.ModelSerializer):
    """이미지 프로세서가 추출한 사용자 노출용 아이템 정보."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CalendarItem
        fields = (
            "id",
            "image_s3_key",
            "image_url",
            "category",
            "tags",
            "bbox",
            "sort_order",
        )

    def get_image_url(self, obj) -> str:
        return storage.presigned_get(obj.image_s3_key)


class CalendarEntrySerializer(serializers.ModelSerializer):
    """캘린더 목록·날짜별·상세 조회의 공통 응답."""

    image_url = serializers.SerializerMethodField()
    wardrobe_items = CalendarWardrobeItemSerializer(
        source="wardrobe_links",
        many=True,
        read_only=True,
    )
    items = CalendarItemSerializer(many=True, read_only=True)

    class Meta:
        model = CalendarEntry
        fields = (
            "id",
            "date",
            "source_type",
            "image_s3_key",
            "image_url",
            "schedule",
            "tpo",
            "weather_snapshot",
            "hashtags",
            "status",
            "wardrobe_items",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_image_url(self, obj) -> str:
        return storage.presigned_get(obj.image_s3_key)
