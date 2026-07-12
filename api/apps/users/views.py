import logging

from django.contrib.auth.models import update_last_login
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import SocialAccount
from apps.users.serializers import SocialLoginSerializer, UserSerializer
from apps.users.services import accounts, oauth

logger = logging.getLogger(__name__)


class SocialLoginView(APIView):
    """
    POST /api/v1/auth/{provider}/login/

    body: {"code": "...", "redirect_uri": "...", "state": "..."}
    응답: {"access": "...", "refresh": "...", "user": {...}, "is_new_user": bool}
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []  # JWT 미보유 상태에서 호출

    def post(self, request, provider: str):
        if provider not in SocialAccount.Provider.values:
            return Response(
                {"detail": f"지원하지 않는 provider입니다: {provider}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 제공사별 필수 파라미터: 카카오/구글은 인가 요청과 동일한 redirect_uri를
        # 토큰 교환에 다시 보내야 하고, 네이버는 state가 필수다.
        if provider in ("kakao", "google") and not data.get("redirect_uri"):
            return Response(
                {"detail": "redirect_uri가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST
            )
        if provider == "naver" and not data.get("state"):
            return Response(
                {"detail": "state가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            profile = oauth.authenticate(
                provider=provider,
                code=data["code"],
                redirect_uri=data.get("redirect_uri") or None,
                state=data.get("state") or None,
            )
        except oauth.OAuthError as exc:
            # 제공사 원본 응답에 내부 정보가 포함될 수 있어 로그에만 남긴다.
            logger.warning("소셜 로그인 실패 (%s): %s", provider, exc)
            return Response(
                {"detail": "소셜 로그인에 실패했습니다. 인가 코드를 확인해주세요."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user, created = accounts.get_or_create_user(profile)
        refresh = RefreshToken.for_user(user)
        update_last_login(None, user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
                "is_new_user": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MeView(APIView):
    """GET/PATCH /api/v1/users/me/ — 내 정보 조회/수정(닉네임, 프로필 이미지)."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
