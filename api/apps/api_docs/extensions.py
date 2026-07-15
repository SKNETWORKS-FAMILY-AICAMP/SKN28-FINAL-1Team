from drf_spectacular.extensions import OpenApiViewExtension
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from apps.api_docs.serializers import (
    DetailResponseSerializer,
    HomeResponseSerializer,
    SocialLoginResponseSerializer,
)
from apps.users.serializers import SocialLoginSerializer, UserSerializer


# apple은 백엔드 코드는 있으나 서비스 구현 보류 상태라 문서에서 제외한다.
PROVIDER_PARAMETER = OpenApiParameter(
    name="provider",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.PATH,
    required=True,
    enum=["naver", "kakao", "google"],
    description="소셜 로그인 제공자",
)

SOCIAL_LOGIN_DESCRIPTION = """소셜 로그인 제공자의 인증 정보를 서비스 JWT로 교환합니다.

## 제공자별 필수값

### kakao — 두 가지 방식 지원
| 방식 | 필수값 | 사용처 |
|------|--------|--------|
| code 방식 | `code`, `redirect_uri` | 웹 프론트엔드 (인가 코드 플로우) |
| token 방식 | `access_token` | 네이티브 앱 (Android/iOS SDK) |

- code 방식: `redirect_uri`는 인가 요청 시 사용한 값과 동일해야 합니다.
- token 방식: SDK가 발급한 카카오 access token을 그대로 전달합니다. 백엔드가 토큰의 `app_id`를 검증하므로 다른 앱에서 발급된 토큰은 거부됩니다.
- `code`와 `access_token`을 함께 보내면 code 방식으로 처리됩니다.

### google — code 방식만 지원
필수값: `code`, `redirect_uri` (인가 요청 시 사용한 값과 동일)

### naver — code 방식만 지원
필수값: `code`, `state` (naver는 redirect_uri 대신 CSRF 방지용 state를 검증)

## 응답
성공 시 서비스 자체 JWT(`access`/`refresh`)와 사용자 정보를 반환합니다.
신규 가입이면 201, 기존 사용자 로그인이면 200입니다.
"""

SOCIAL_LOGIN_EXAMPLES = [
    OpenApiExample(
        name="kakao (code 방식, 웹)",
        value={
            "code": "인가_코드",
            "redirect_uri": "https://service.example.com/oauth/kakao/callback",
        },
        request_only=True,
    ),
    OpenApiExample(
        name="kakao (token 방식, 네이티브 앱)",
        value={"access_token": "카카오_SDK가_발급한_액세스_토큰"},
        request_only=True,
    ),
    OpenApiExample(
        name="google (code 방식)",
        value={
            "code": "인가_코드",
            "redirect_uri": "https://service.example.com/oauth/google/callback",
        },
        request_only=True,
    ),
    OpenApiExample(
        name="naver (code 방식)",
        value={"code": "인가_코드", "state": "인가_요청_시_보낸_state"},
        request_only=True,
    ),
]


class SocialLoginViewExtension(OpenApiViewExtension):
    target_class = "apps.users.views.SocialLoginView"

    def view_replacement(self):
        @extend_schema_view(
            post=extend_schema(
                operation_id="social_login",
                tags=["Authentication"],
                summary="소셜 로그인",
                description=SOCIAL_LOGIN_DESCRIPTION,
                parameters=[PROVIDER_PARAMETER],
                request=SocialLoginSerializer,
                examples=SOCIAL_LOGIN_EXAMPLES,
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


HOME_DESCRIPTION = """홈 화면에 필요한 데이터를 한 번에 반환합니다 (로그인 필요).

- `lat`/`lon`을 보내면 가장 가까운 예보구역의 현재 날씨를 반환합니다.
- 좌표가 없거나 국내 범위(위도 33~39, 경도 124~132)를 벗어나면 서울시청 좌표로 대체합니다.
- `quick_recommends`, `closet_count`, `saved_look_count`는 실제 추천·옷장 기능 연동 전까지 mock 값입니다.
"""

HOME_COORDINATE_PARAMETERS = [
    OpenApiParameter(
        name="lat",
        type=OpenApiTypes.NUMBER,
        location=OpenApiParameter.QUERY,
        required=False,
        description="위도 (예: 37.5665). 생략 시 서울시청 좌표 사용.",
    ),
    OpenApiParameter(
        name="lon",
        type=OpenApiTypes.NUMBER,
        location=OpenApiParameter.QUERY,
        required=False,
        description="경도 (예: 126.9780). 생략 시 서울시청 좌표 사용.",
    ),
]

HOME_RESPONSE_EXAMPLE = OpenApiExample(
    name="맑은 날 예시",
    value={
        "nickname": "건우",
        "weather": {
            "region": "서울",
            "temperature": 26,
            "sky_state": "맑음",
            "is_stale": False,
            "observed_at": "2026-07-15T14:00:00+09:00",
        },
        "today_look": {
            "comment": "26도예요. 반팔이면 딱 좋은 날씨예요.",
            "tags": ["반팔 티셔츠", "얇은 셔츠", "면바지"],
        },
        "quick_recommends": ["출근룩", "데이트룩", "면접룩", "주말룩"],
        "closet_count": 42,
        "saved_look_count": 8,
    },
    response_only=True,
)


class HomeViewExtension(OpenApiViewExtension):
    target_class = "apps.home.views.HomeView"

    def view_replacement(self):
        @extend_schema_view(
            get=extend_schema(
                operation_id="get_home",
                tags=["Home"],
                summary="홈 화면 통합 조회",
                description=HOME_DESCRIPTION,
                parameters=HOME_COORDINATE_PARAMETERS,
                examples=[HOME_RESPONSE_EXAMPLE],
                responses={
                    200: HomeResponseSerializer,
                    401: OpenApiResponse(
                        response=DetailResponseSerializer,
                        description="인증 실패 (JWT 필요)",
                    ),
                },
            )
        )
        class DocumentedHomeView(self.target_class):
            pass

        return DocumentedHomeView


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
