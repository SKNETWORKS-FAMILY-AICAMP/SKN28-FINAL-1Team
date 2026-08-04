"""스타일 캘린더 조회 API 직렬화."""

from __future__ import annotations

from rest_framework import serializers

from apps.style_calendar.models import (
    CalendarEntry,
    CalendarItem,
    CalendarWardrobeItem,
)


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


class CalendarWardrobeItemSerializer(serializers.ModelSerializer):
    """캘린더와 수동 선택 옷장 아이템의 연결 정보."""

    link_id = serializers.UUIDField(source="id", read_only=True)
    wardrobe_item_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CalendarWardrobeItem
        fields = ("link_id", "wardrobe_item_id", "sort_order", "snapshot")


class CalendarItemSerializer(serializers.ModelSerializer):
    """이미지 프로세서가 추출한 사용자 노출용 아이템 정보."""

    class Meta:
        model = CalendarItem
        fields = ("id", "image_s3_key", "category", "tags", "bbox", "sort_order")


class CalendarEntrySerializer(serializers.ModelSerializer):
    """캘린더 목록·날짜별·상세 조회의 공통 응답."""

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
