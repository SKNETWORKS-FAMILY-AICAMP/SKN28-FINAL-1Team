from rest_framework import serializers

from apps.users.models import SocialAccount, User


class SocialLoginSerializer(serializers.Serializer):
    """POST /auth/{provider}/login 요청 바디.

    code(인가 코드 방식) 또는 access_token(토큰 방식, 카카오 네이티브 앱 SDK 전용)
    중 하나는 반드시 있어야 한다.
    """

    code = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="인가 코드 (code 방식). naver/google/kakao 웹 로그인에서 필수.",
    )
    # 카카오 전용(token 방식): 네이티브 앱 SDK는 인가 코드를 노출하지 않고
    # access_token을 직접 반환하므로, 앱은 이 값을 백엔드로 전달한다.
    access_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="카카오 전용(token 방식). 네이티브 앱 SDK가 발급한 카카오 access token.",
    )
    # 카카오/구글은 토큰 교환 시 인가 요청과 동일한 redirect_uri가 필요하다.
    redirect_uri = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="kakao(code 방식)/google 필수. 인가 요청 시 사용한 값과 동일해야 함.",
    )
    # 네이버는 state 검증을 사용한다.
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="naver 필수. 인가 요청 시 보낸 CSRF 방지용 state 값.",
    )
    # 애플 전용: 최초 로그인 시 Apple SDK가 전달하는 사용자 이름 (이후 로그인엔 빈값).
    user_name = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="apple 전용 (구현 보류). 최초 로그인 시 Apple이 전달하는 사용자 이름.",
    )

    def validate(self, attrs):
        if not attrs.get("code") and not attrs.get("access_token"):
            raise serializers.ValidationError("code 또는 access_token 중 하나가 필요합니다.")
        return attrs


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
