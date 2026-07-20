"""
인증 우회 개발 설정 (로컬 전용 — 프로덕션 사용 금지).

소셜 로그인 없이 보호된 API를 테스트할 때 사용한다.
Authorization 헤더가 없는 모든 요청은 개발용 유저(dev_autologin)로
자동 인증되고, Bearer JWT를 보내면 기존 JWT 인증이 우선 적용된다.

실행:
    DJANGO_SETTINGS_MODULE=config.settings.noauth python manage.py runserver
"""

from .dev import *  # noqa: F401,F403

# AutoLoginAuthentication의 안전장치 플래그 (이 설정에서만 켠다)
AUTO_LOGIN_ENABLED = True

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # JWT가 헤더에 있으면 그대로 인증하고, 없으면 자동 로그인으로 폴백한다.
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.users.authentication.AutoLoginAuthentication",
    ],
}
