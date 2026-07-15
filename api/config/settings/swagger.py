"""Development settings with OpenAPI schema and Swagger UI enabled."""

from .dev import *  # noqa: F401,F403

INSTALLED_APPS = [  # noqa: F405
    *INSTALLED_APPS,  # noqa: F405
    "drf_spectacular",
    "apps.api_docs",
]

ROOT_URLCONF = "config.urls_swagger"

REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

API_DESCRIPTION = """SKN28 개인화 패션 추천 서비스 API 문서

## 인증 구조 (JWT Bearer)

이 API는 헤더 기반 JWT 인증을 사용합니다.

1. **토큰 발급**: `POST /api/v1/auth/{provider}/login/` (소셜 로그인)이 서비스 자체
   JWT인 `access`/`refresh` 토큰을 반환합니다.
2. **인증 요청**: 보호된 엔드포인트는 `Authorization: Bearer <access>` 헤더를
   요구합니다. Swagger UI에서는 우측 상단 **Authorize** 버튼에 access 토큰을
   입력하면 요청에 자동으로 헤더가 붙습니다.
3. **토큰 갱신**: access 토큰 만료(기본 30분) 시 `POST /api/v1/auth/token/refresh/`로
   재발급합니다. refresh 토큰(기본 14일)은 회전 방식이라 갱신할 때마다 새
   refresh 토큰이 함께 발급되며, 이전 refresh 토큰은 블랙리스트 처리됩니다.

자물쇠 아이콘이 있는 엔드포인트가 인증 필수이고, 소셜 로그인·토큰 갱신은 인증
없이 호출할 수 있습니다.
"""

SPECTACULAR_SETTINGS = {
    "TITLE": "SKN28 Fashion Recommendation API",
    "DESCRIPTION": API_DESCRIPTION,
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}
