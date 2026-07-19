from drf_spectacular.extensions import (
    OpenApiAuthenticationExtension,
    OpenApiViewExtension,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from apps.api_docs.serializers import (
    BodyPhotoResponseSerializer,
    DetailResponseSerializer,
    HomeResponseSerializer,
    SocialLoginResponseSerializer,
)
from apps.users.serializers import (
    BodyBasicInputSerializer,
    BodyDetailInputSerializer,
    BodyMeasurementSerializer,
    BodyPhotoUploadSerializer,
    SocialLoginSerializer,
    UserSerializer,
)


class JWTAuthenticationExtension(OpenApiAuthenticationExtension):
    """
    simplejwt 기본 확장을 대체(priority)해 헤더 인증 구조 설명을 추가한다.

    보호된 엔드포인트는 소셜 로그인으로 발급받은 access 토큰을
    Authorization 헤더에 담아 호출해야 한다.
    """

    target_class = "rest_framework_simplejwt.authentication.JWTAuthentication"
    name = "jwtAuth"
    priority = 1  # drf-spectacular 내장 simplejwt 확장(priority 0)보다 우선

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "소셜 로그인(`POST /api/v1/auth/{provider}/login/`)이 발급한 "
                "**access 토큰**을 `Authorization: Bearer <access>` 헤더로 전달합니다.\n\n"
                "- access 토큰 만료 시 401이 반환되며, "
                "`POST /api/v1/auth/token/refresh/`로 재발급합니다.\n"
                "- refresh 토큰은 회전(rotate)되므로 갱신 응답의 새 refresh 토큰으로 "
                "교체 저장해야 합니다 (이전 refresh 토큰은 블랙리스트 처리)."
            ),
        }


class TokenRefreshViewExtension(OpenApiViewExtension):
    """simplejwt 기본 영문 설명을 서비스 맥락에 맞는 한국어 문서로 교체한다."""

    target_class = "rest_framework_simplejwt.views.TokenRefreshView"

    def view_replacement(self):
        @extend_schema_view(
            post=extend_schema(
                operation_id="token_refresh",
                tags=["Authentication"],
                summary="JWT 토큰 갱신",
                description=(
                    "refresh 토큰으로 새 access 토큰을 발급합니다.\n\n"
                    "- refresh 토큰이 회전되므로 응답에 **새 refresh 토큰**도 함께 "
                    "반환됩니다. 클라이언트는 두 토큰 모두 교체 저장해야 합니다.\n"
                    "- 이전 refresh 토큰은 블랙리스트 처리되어 재사용 시 401이 "
                    "반환됩니다."
                ),
            )
        )
        class DocumentedTokenRefreshView(self.target_class):
            pass

        return DocumentedTokenRefreshView


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

token 방식은 백엔드가 토큰의 `app_id`를 검증하므로 다른 앱에서 발급된 토큰은 거부됩니다.

### google — 두 가지 방식 지원
| 방식 | 필수값 | 사용처 |
|------|--------|--------|
| code 방식 | `code`, `redirect_uri` | 웹 프론트엔드 (인가 코드 플로우) |
| token 방식 | `access_token` | 네이티브 앱 (Android/iOS SDK) |

token 방식은 백엔드가 토큰의 `aud`(발급 대상 client_id)를 검증하므로 다른 앱에서 발급된 토큰은 거부됩니다.

### naver — 두 가지 방식 지원
| 방식 | 필수값 | 사용처 |
|------|--------|--------|
| code 방식 | `code`, `state` | 웹 프론트엔드 (redirect_uri 대신 CSRF 방지용 state 검증) |
| token 방식 | `access_token` | 네이티브 앱 (Android/iOS SDK) |

⚠️ naver token 방식은 토큰 유효성 확인과 사용자 식별(`/v1/nid/me`)만 수행합니다.
naver는 발급 앱을 확인할 API를 제공하지 않아 **다른 naver 앱에서 발급된 토큰을
구분할 수 없습니다** (kakao/google과 달리 발급 앱 검증 없음). 이 한계를 수용한
구현이므로, 가능하면 code 방식을 우선 사용하세요.

### 공통 규칙
- code 방식의 `redirect_uri`는 인가 요청 시 사용한 값과 동일해야 합니다.
- `code`와 `access_token`을 함께 보내면 code 방식으로 처리됩니다.

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
        name="google (token 방식, 네이티브 앱)",
        value={"access_token": "구글_SDK가_발급한_액세스_토큰"},
        request_only=True,
    ),
    OpenApiExample(
        name="naver (code 방식)",
        value={"code": "인가_코드", "state": "인가_요청_시_보낸_state"},
        request_only=True,
    ),
    OpenApiExample(
        name="naver (token 방식, 네이티브 앱)",
        value={"access_token": "네이버_SDK가_발급한_액세스_토큰"},
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


BODY_DETAIL_DESCRIPTION = """상세 둘레 수치를 저장합니다. **모든 필드가 선택 입력**입니다.

- 보낸 필드만 갱신됩니다 (partial update).
- 필드에 `null`을 보내면 저장된 값을 지웁니다.
- 단위는 cm, 소수점 1자리까지 허용합니다 (1 ~ 999.9).
"""

BODY_PHOTOS_DESCRIPTION = """정면/측면 전신 사진을 접수합니다 (multipart/form-data).

- 사진은 **서버에 저장하지 않습니다.** 요청 처리 후 임시 파일은 즉시 정리됩니다.
- 추후 접수된 사진으로 상세 신체치수를 추론하는 기능이 연결될 예정이며,
  현재는 접수 확인 응답만 반환합니다.
- 파일당 10MB 이하의 이미지 파일이어야 합니다.
"""


class BodyMeasurementViewExtension(OpenApiViewExtension):
    target_class = "apps.users.views.BodyMeasurementView"

    def view_replacement(self):
        @extend_schema_view(
            get=extend_schema(
                operation_id="get_body_measurement",
                tags=["Body"],
                summary="신체치수 조회",
                description="저장된 신체치수를 반환합니다. 아직 입력하지 않은 필드는 `null`입니다.",
                responses={
                    200: BodyMeasurementSerializer,
                    401: DetailResponseSerializer,
                },
            )
        )
        class DocumentedBodyMeasurementView(self.target_class):
            pass

        return DocumentedBodyMeasurementView


class BodyBasicViewExtension(OpenApiViewExtension):
    target_class = "apps.users.views.BodyBasicView"

    def view_replacement(self):
        @extend_schema_view(
            put=extend_schema(
                operation_id="update_body_basic",
                tags=["Body"],
                summary="기본 신체치수 입력 (키·몸무게)",
                description=(
                    "키(cm)와 몸무게(kg)를 저장합니다. **두 값 모두 필수**이며 "
                    "소수점 1자리까지 허용합니다 (1 ~ 999.9). 상세 수치는 건드리지 않습니다."
                ),
                request=BodyBasicInputSerializer,
                responses={
                    200: BodyMeasurementSerializer,
                    400: DetailResponseSerializer,
                    401: DetailResponseSerializer,
                },
            )
        )
        class DocumentedBodyBasicView(self.target_class):
            pass

        return DocumentedBodyBasicView


class BodyDetailViewExtension(OpenApiViewExtension):
    target_class = "apps.users.views.BodyDetailView"

    def view_replacement(self):
        @extend_schema_view(
            patch=extend_schema(
                operation_id="update_body_detail",
                tags=["Body"],
                summary="상세 신체치수 입력 (전부 선택)",
                description=BODY_DETAIL_DESCRIPTION,
                request=BodyDetailInputSerializer,
                responses={
                    200: BodyMeasurementSerializer,
                    400: DetailResponseSerializer,
                    401: DetailResponseSerializer,
                },
            )
        )
        class DocumentedBodyDetailView(self.target_class):
            pass

        return DocumentedBodyDetailView


class BodyPhotoViewExtension(OpenApiViewExtension):
    target_class = "apps.users.views.BodyPhotoView"

    def view_replacement(self):
        @extend_schema_view(
            post=extend_schema(
                operation_id="upload_body_photos",
                tags=["Body"],
                summary="신체 사진 접수 (수치 추론용, 저장 안 함)",
                description=BODY_PHOTOS_DESCRIPTION,
                request=BodyPhotoUploadSerializer,
                responses={
                    200: BodyPhotoResponseSerializer,
                    400: DetailResponseSerializer,
                    401: DetailResponseSerializer,
                },
            )
        )
        class DocumentedBodyPhotoView(self.target_class):
            pass

        return DocumentedBodyPhotoView


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
