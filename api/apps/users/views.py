import logging

from django.contrib.auth.models import update_last_login
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import BodyMeasurement, SocialAccount
from apps.users.serializers import (
    BodyBasicInputSerializer,
    BodyDetailInputSerializer,
    BodyMeasurementSerializer,
    BodyPhotoUploadSerializer,
    SocialLoginSerializer,
    UserSerializer,
)
from apps.users.services import accounts, oauth

logger = logging.getLogger(__name__)


class SocialLoginView(APIView):
    """
    POST /api/v1/auth/{provider}/login/

    body (code 방식): {"code": "...", "redirect_uri": "...", "state": "..."}
    body (token 방식, 카카오 네이티브 앱 SDK 전용): {"access_token": "..."}
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

        # token 방식(카카오 네이티브 앱 SDK): 앱이 SDK로 받은 access_token을 전달.
        # code 방식: 웹 프론트가 받은 인가 코드를 전달 (기존 흐름).
        use_token_login = bool(data.get("access_token")) and not data.get("code")

        if not use_token_login:
            # 제공사별 필수 파라미터: 카카오/구글은 인가 요청과 동일한 redirect_uri를
            # 토큰 교환에 다시 보내야 하고, 네이버는 state가 필수다.
            if provider in ("kakao", "google", "apple") and not data.get("redirect_uri"):
                return Response(
                    {"detail": "redirect_uri가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST
                )
            if provider == "naver" and not data.get("state"):
                return Response(
                    {"detail": "state가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST
                )

        try:
            if use_token_login:
                profile = oauth.authenticate_with_token(
                    provider=provider,
                    access_token=data["access_token"],
                )
            else:
                profile = oauth.authenticate(
                    provider=provider,
                    code=data["code"],
                    redirect_uri=data.get("redirect_uri") or None,
                    state=data.get("state") or None,
                    apple_user_name=data.get("user_name") or None,
                )
        except oauth.OAuthError as exc:
            # 제공사 원본 응답에 내부 정보가 포함될 수 있어 로그에만 남긴다.
            logger.warning("소셜 로그인 실패 (%s): %s", provider, exc)
            return Response(
                {"detail": "소셜 로그인에 실패했습니다. 인가 코드 또는 토큰을 확인해주세요."},
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


def _save_body_measurement(request, serializer_class, *, partial: bool) -> Response:
    """신체치수 upsert 공통 처리. 저장 후 전체 치수를 응답한다."""
    measurement, _ = BodyMeasurement.objects.get_or_create(user=request.user)
    serializer = serializer_class(measurement, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(BodyMeasurementSerializer(measurement).data)


class BodyMeasurementView(APIView):
    """GET /api/v1/users/me/body/ — 내 신체치수 조회 (미입력 필드는 null)."""

    def get(self, request):
        measurement = BodyMeasurement.objects.filter(user=request.user).first()
        # 아직 입력 전이면 모든 필드가 null인 빈 치수를 반환한다 (404 대신).
        return Response(BodyMeasurementSerializer(measurement or BodyMeasurement()).data)


class BodyBasicView(APIView):
    """PUT /api/v1/users/me/body/basic/ — 키·몸무게 입력 (둘 다 필수)."""

    def put(self, request):
        return _save_body_measurement(request, BodyBasicInputSerializer, partial=False)


class BodyDetailView(APIView):
    """PATCH /api/v1/users/me/body/detail/ — 상세 둘레 수치 입력 (전부 선택)."""

    def patch(self, request):
        return _save_body_measurement(request, BodyDetailInputSerializer, partial=True)


class BodyPhotoView(APIView):
    """POST /api/v1/users/me/body/photos/ — 정면/측면 사진 접수.

    사진은 디스크·DB에 저장하지 않는다. 요청 처리 후 Django가 임시 업로드
    파일을 정리하며, 추후 이 자리에서 상세 수치 추론 기능을 호출할 예정이다.
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = BodyPhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def file_meta(image):
            return {
                "name": image.name,
                "size": image.size,
                "content_type": image.content_type,
            }

        return Response(
            {
                "detail": "사진이 정상 접수되었습니다. 상세 수치 추론 기능은 준비 중입니다.",
                "received": {
                    "front_image": file_meta(serializer.validated_data["front_image"]),
                    "side_image": file_meta(serializer.validated_data["side_image"]),
                },
            }
        )
