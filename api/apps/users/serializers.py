from rest_framework import serializers

from apps.users.models import SocialAccount, User


class SocialLoginSerializer(serializers.Serializer):
    """POST /auth/{provider}/login 요청 바디."""

    code = serializers.CharField()
    # 카카오/구글은 토큰 교환 시 인가 요청과 동일한 redirect_uri가 필요하다.
    redirect_uri = serializers.URLField(required=False, allow_blank=True)
    # 네이버는 state 검증을 사용한다.
    state = serializers.CharField(required=False, allow_blank=True)


class SocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = ["provider", "email", "connected_at"]


class UserSerializer(serializers.ModelSerializer):
    social_accounts = SocialAccountSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "nickname", "profile_image", "social_accounts"]
        read_only_fields = ["id", "username", "email", "social_accounts"]
