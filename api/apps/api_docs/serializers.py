from rest_framework import serializers

from apps.users.serializers import UserSerializer


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class SocialLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()
    is_new_user = serializers.BooleanField()


class BodyPhotoMetaSerializer(serializers.Serializer):
    """접수된 사진 파일 메타데이터."""

    name = serializers.CharField(help_text="업로드된 파일명.")
    size = serializers.IntegerField(help_text="파일 크기(byte).")
    content_type = serializers.CharField(help_text="파일 MIME 타입.")


class BodyPhotoReceivedSerializer(serializers.Serializer):
    front_image = BodyPhotoMetaSerializer()
    side_image = BodyPhotoMetaSerializer()


class BodyPhotoResponseSerializer(serializers.Serializer):
    """POST /api/v1/users/me/body/photos/ 200 응답 본문."""

    detail = serializers.CharField()
    received = BodyPhotoReceivedSerializer()


class HomeWeatherSerializer(serializers.Serializer):
    """홈 화면 현재 날씨 블록. 데이터가 없으면 각 필드는 null이다."""

    region = serializers.CharField(
        allow_null=True,
        help_text="지역 표기. 광역시/특별자치시는 시도 축약(예: 서울), 그 외는 시군구명.",
    )
    temperature = serializers.IntegerField(
        allow_null=True, help_text="현재 기온(℃, 반올림 정수). 실황 없으면 null."
    )
    sky_state = serializers.CharField(
        allow_null=True, help_text="하늘상태: 맑음 | 구름많음 | 흐림 | 비 | 눈"
    )
    is_stale = serializers.BooleanField(
        help_text="실황이 2시간보다 오래됐거나 없으면 true."
    )
    observed_at = serializers.DateTimeField(
        allow_null=True, help_text="실황 관측(발표) 시각."
    )


class HomeTodayLookSerializer(serializers.Serializer):
    """기온 구간별 오늘의 룩 멘트. 기온을 알 수 없으면 빈 값이다."""

    comment = serializers.CharField(allow_blank=True, help_text="기온 구간별 추천 멘트.")
    tags = serializers.ListField(
        child=serializers.CharField(), help_text="추천 아이템 태그 목록."
    )


class HomeResponseSerializer(serializers.Serializer):
    """GET /api/v1/home/ 200 응답 본문."""

    nickname = serializers.CharField(help_text="사용자 닉네임(없으면 username).")
    weather = HomeWeatherSerializer()
    today_look = HomeTodayLookSerializer()
    quick_recommends = serializers.ListField(
        child=serializers.CharField(), help_text="빠른 추천 카테고리 목록."
    )
    closet_count = serializers.IntegerField(help_text="옷장에 등록된 아이템 수.")
    saved_look_count = serializers.IntegerField(help_text="저장한 룩 수.")
