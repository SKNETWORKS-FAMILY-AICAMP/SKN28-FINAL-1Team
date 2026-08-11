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

# Expo 웹 개발 서버(localhost:8001)에서 API(localhost:8000)를 호출할 수 있게 한다.
# noauth 설정은 DEBUG 로컬 전용이므로 프로덕션 CORS 정책에는 영향을 주지 않는다.
CORS_ALLOW_ALL_ORIGINS = True

# 같은 Wi-Fi의 휴대폰에서 PC의 Expo 웹 화면을 열어도 Django가 Host를 거부하지 않게 한다.
# 이 설정 파일은 DEBUG 로컬 전용이며 프로덕션에는 사용하지 않는다.
ALLOWED_HOSTS = ["*"]
