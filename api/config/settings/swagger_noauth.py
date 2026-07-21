"""
Swagger UI + 인증 우회 개발 설정 (로컬 전용 — 프로덕션 사용 금지).

swagger 설정(문서 UI + 스키마)에 noauth의 자동 로그인을 얹는다.
Swagger UI에서 Authorize 없이 자물쇠 걸린 엔드포인트를 바로 호출할 수 있고,
Authorization 헤더에 JWT를 넣으면 기존 JWT 인증이 우선 적용된다.

실행:
    DJANGO_SETTINGS_MODULE=config.settings.swagger_noauth python manage.py runserver

주의: noauth를 import로 겹치면 dev의 REST_FRAMEWORK가 다시 덮어써져
DEFAULT_SCHEMA_CLASS가 사라지므로, 여기서 명시적으로 병합한다.
"""

from .swagger import *  # noqa: F401,F403

# AutoLoginAuthentication의 안전장치 플래그 (noauth 계열 설정에서만 켠다)
AUTO_LOGIN_ENABLED = True

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405  (swagger의 DEFAULT_SCHEMA_CLASS 유지)
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # JWT가 헤더에 있으면 그대로 인증하고, 없으면 자동 로그인으로 폴백한다.
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.users.authentication.AutoLoginAuthentication",
    ],
}
