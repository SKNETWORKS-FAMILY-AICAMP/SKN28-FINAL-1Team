import logging

from django.contrib.auth.models import update_last_login
from django.db import IntegrityError
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import BodyMeasurement, BodyPhotoTransaction, SocialAccount
from apps.users.serializers import (
    BodyBasicInputSerializer,
    BodyDetailInputSerializer,
    BodyMeasurementSerializer,
    BodyPhotoTransactionSerializer,
    BodyPhotoUploadSerializer,
    PreferenceCategorySerializer,
    PursuitPayloadInputSerializer,
    PursuitPayloadResponseSerializer,
    SocialLoginSerializer,
    UserSerializer,
)
from apps.users.services import accounts, body_inference, oauth, pursuit

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


IN_PROGRESS_DETAIL = "이미 진행 중인 신체 측정이 있습니다. 완료 후 다시 시도해주세요."


class BodyPhotoView(APIView):
    """POST /api/v1/users/me/body/photos/ — 정면/측면 사진 접수 → 측정 트랜잭션 시작.

    사진은 디스크·DB에 저장하지 않는다. 접수 시 측정 트랜잭션을 '진행중'으로
    생성하고 202와 함께 transaction_id를 반환한다. 진행중 트랜잭션이 이미 있으면
    400. 실제 추론이 준비되기 전이라 백그라운드 mock이 10초 뒤 상세 수치를
    갱신하고 '성공'으로 마친다 (services/body_inference.py).
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = BodyPhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if BodyPhotoTransaction.objects.filter(
            user=request.user, status=BodyPhotoTransaction.Status.IN_PROGRESS
        ).exists():
            return Response(
                {"detail": IN_PROGRESS_DETAIL}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tx = BodyPhotoTransaction.objects.create(user=request.user)
        except IntegrityError:
            # 동시 요청이 부분 유니크 제약(사용자당 진행중 1건)에 걸린 경우
            return Response(
                {"detail": IN_PROGRESS_DETAIL}, status=status.HTTP_400_BAD_REQUEST
            )

        body_inference.start_measurement(tx.pk)

        def file_meta(image):
            return {
                "name": image.name,
                "size": image.size,
                "content_type": image.content_type,
            }

        return Response(
            {
                "detail": "사진이 접수되었습니다. 신체 측정이 진행 중입니다.",
                "transaction_id": str(tx.pk),
                "status": tx.status,
                "received": {
                    "front_image": file_meta(serializer.validated_data["front_image"]),
                    "side_image": file_meta(serializer.validated_data["side_image"]),
                },
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BodyPhotoTransactionView(APIView):
    """GET /api/v1/users/me/body/photos/{transaction_id}/ — 측정 트랜잭션 상태 조회.

    프론트가 폴링으로 진행중 → 성공/실패 전환을 확인하는 용도다.
    """

    def get(self, request, transaction_id):
        tx = BodyPhotoTransaction.objects.filter(
            pk=transaction_id, user=request.user
        ).first()
        if tx is None:
            return Response(
                {"detail": "해당 측정 트랜잭션을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(BodyPhotoTransactionSerializer(tx).data)


# =============================================================================
# 추구미 (Pursuit) — 옵션 마스터 + 사용자 선택
# =============================================================================


class PreferenceOptionsView(APIView):
    """GET /api/v1/preference-options/ — 11개 카테고리 + 옵션 마스터.

    인증 필요. 프론트가 화면 진입 시 옵션 목록을 받아 칩을 렌더링하는 용도.
    """

    def get(self, request):
        grouped = pursuit.get_options_grouped_by_category()
        # OrderedDict을 list[dict]로 변환 (Serializer와 호환)
        categories = [grouped[k] for k in grouped]
        return Response(
            {"categories": PreferenceCategorySerializer(categories, many=True).data}
        )


class PursuitView(APIView):
    """GET /api/v1/users/me/pursuit/ — 내 추구미 조회 (저장 없으면 빈 payload).
    PUT /api/v1/users/me/pursuit/ — 내 추구미 저장 (upsert, 전체 교체).
    """

    def get(self, request):
        payload = pursuit.get_pursuit(request.user)
        return Response(PursuitPayloadResponseSerializer(payload).data)

    def put(self, request):
        serializer = PursuitPayloadInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        obj = pursuit.upsert_pursuit(
            request.user,
            preferred=serializer.validated_data["preferred"],
            avoided=serializer.validated_data["avoided"],
        )
        # 저장된 결과 응답 (재조회와 동일 형식)
        return Response(
            PursuitPayloadResponseSerializer(obj.payload).data,
            status=status.HTTP_200_OK,
        )
