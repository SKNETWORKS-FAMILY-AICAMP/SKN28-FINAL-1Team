from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from apps.api_docs.serializers import (
    DetailResponseSerializer,
    SocialLoginResponseSerializer,
)
from apps.users.serializers import SocialLoginSerializer, UserSerializer


PROVIDER_PARAMETER = OpenApiParameter(
    name="provider",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.PATH,
    required=True,
    enum=["naver", "kakao", "google", "apple"],
    description="소셜 로그인 제공자",
)


class SocialLoginViewExtension(OpenApiViewExtension):
    target_class = "apps.users.views.SocialLoginView"

    def view_replacement(self):
        @extend_schema_view(
            post=extend_schema(
                operation_id="social_login",
                tags=["Authentication"],
                summary="소셜 로그인",
                description=(
                    "소셜 로그인 제공자가 발급한 authorization code를 서비스 JWT로 "
                    "교환합니다. kakao/google/apple은 redirect_uri, naver는 state가 "
                    "필수입니다."
                ),
                parameters=[PROVIDER_PARAMETER],
                request=SocialLoginSerializer,
                responses={
                    200: SocialLoginResponseSerializer,
                    201: SocialLoginResponseSerializer,
                    400: OpenApiResponse(
                        response=DetailResponseSerializer,
                        description="요청값 또는 provider 오류",
                    ),
                    401: OpenApiResponse(
                        response=DetailResponseSerializer,
                        description="소셜 로그인 실패",
                    ),
                },
            )
        )
        class DocumentedSocialLoginView(self.target_class):
            pass

        return DocumentedSocialLoginView


class MeViewExtension(OpenApiViewExtension):
    target_class = "apps.users.views.MeView"

    def view_replacement(self):
        @extend_schema_view(
            get=extend_schema(
                operation_id="get_current_user",
                tags=["Users"],
                summary="내 정보 조회",
                responses={
                    200: UserSerializer,
                    401: DetailResponseSerializer,
                },
            ),
            patch=extend_schema(
                operation_id="update_current_user",
                tags=["Users"],
                summary="내 정보 수정",
                request=UserSerializer,
                responses={
                    200: UserSerializer,
                    400: DetailResponseSerializer,
                    401: DetailResponseSerializer,
                },
            ),
        )
        class DocumentedMeView(self.target_class):
            pass

        return DocumentedMeView
