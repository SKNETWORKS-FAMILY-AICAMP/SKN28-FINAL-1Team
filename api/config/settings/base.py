"""
공통 설정. 환경별 차이는 dev.py / prod.py에서 오버라이드한다.

환경변수는 프로젝트 루트(SKN28-FINAL-1Team/)의 .env 하나로 관리한다.
시크릿은 코드에 하드코딩하지 않는다 (CLAUDE.md 규칙).
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# api/config/settings/base.py → BASE_DIR = api/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# 루트 .env (api/의 상위 = 프로젝트 루트)
load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-dev-only-change-me")

DEBUG = False
ALLOWED_HOSTS: list[str] = [
    h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # ArrayField/GinIndex 시스템 체크 지원
    # 3rd party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    # local apps
    "apps.users",
    "apps.catalog",
    "apps.weather",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------
# Database (PostgreSQL, collector와 동일한 환경변수 키 사용)
# ------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "fashion_db"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------
# DRF / JWT
# ------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("JWT_REFRESH_DAYS", "14"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    # 회전된 이전 refresh 토큰 재사용 차단 (token_blacklist 앱 필요)
    "BLACKLIST_AFTER_ROTATION": True,
}

# ------------------------------------------------------------
# 소셜 로그인 (naver / kakao / google)
# 검색 API용 NAVER_CLIENT_ID와 혼동하지 않도록 *_OAUTH_* 접두사를 쓴다.
# ------------------------------------------------------------
OAUTH_PROVIDERS = {
    "naver": {
        "client_id": os.getenv("NAVER_OAUTH_CLIENT_ID", ""),
        "client_secret": os.getenv("NAVER_OAUTH_CLIENT_SECRET", ""),
        "token_url": "https://nid.naver.com/oauth2.0/token",
        "profile_url": "https://openapi.naver.com/v1/nid/me",
    },
    "kakao": {
        "client_id": os.getenv("KAKAO_OAUTH_REST_API_KEY", ""),
        "client_secret": os.getenv("KAKAO_OAUTH_CLIENT_SECRET", ""),  # 선택(보안 강화 시)
        "token_url": "https://kauth.kakao.com/oauth/token",
        "profile_url": "https://kapi.kakao.com/v2/user/me",
    },
    "google": {
        "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        "token_url": "https://oauth2.googleapis.com/token",
        "profile_url": "https://www.googleapis.com/oauth2/v3/userinfo",
    },
}

OAUTH_REQUEST_TIMEOUT = int(os.getenv("OAUTH_REQUEST_TIMEOUT", "10"))
