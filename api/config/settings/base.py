"""
공통 설정. 환경별 차이는 dev.py / prod.py에서 오버라이드한다.

환경변수는 프로젝트 루트(SKN28-FINAL-1Team/)의 .env 하나로 관리한다.
시크릿은 코드에 하드코딩하지 않는다 (CLAUDE.md 규칙).
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# api/config/settings/base.py → BASE_DIR = api/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# 루트 .env (api/의 상위 = 프로젝트 루트)
load_dotenv(BASE_DIR.parent / ".env")

# ML 추론 코드는 ml/ 아래에 두고 웹 계층이 import해서 쓴다 (CLAUDE.md §7).
# ml/을 경로에 올려 `from body_measurement.src import inference` 로 접근한다.
ML_ROOT = Path(os.getenv("ML_ROOT") or (BASE_DIR.parent / "ml"))
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

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
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    # local apps
    "apps.users",
    "apps.catalog",
    "apps.weather",
    "apps.home",
    "apps.wardrobe",
    "apps.recommend",
    "apps.style_calendar",
]

# ------------------------------------------------------------
# 로깅
#
# 설정이 없으면 Django 기본 LOGGING이 적용되는데, 그 console 핸들러에는
# require_debug_true 필터가 걸려 있어 DEBUG=False(prod)에서는 아무것도
# 출력되지 않는다. 또 apps.* 로거는 핸들러 없는 root로 떨어져
# logging.lastResort(WARNING 이상, 포맷 없음)만 stderr로 나간다.
# → 여기서 명시적으로 stdout 핸들러를 붙여 DEBUG 여부와 무관하게 남긴다.
#
# 요청 단위 액세스 로그는 Django가 아니라 gunicorn이 담당한다
# (docker-compose.yml / Dockerfile의 --access-logfile -).
# ------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    # Django/서드파티가 이미 만들어 둔 로거를 죽이지 않는다.
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            # gunicorn --capture-output이 stdout/stderr를 에러 로그로 모은다.
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        # 애플리케이션 코드 (apps.users, apps.recommend, ...)
        "apps": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO").upper(),
            "propagate": False,
        },
        # 4xx/5xx 응답과 처리되지 않은 예외. 기본은 ERROR라 400/404가 안 보인다.
        "django.request": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_REQUEST_LOG_LEVEL", "WARNING").upper(),
            "propagate": False,
        },
        # SQL 쿼리 로그. 기본은 끔 — 필요할 때 DJANGO_DB_LOG_LEVEL=DEBUG.
        "django.db.backends": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_DB_LOG_LEVEL", "WARNING").upper(),
            "propagate": False,
        },
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # CORS: 응답을 생성할 수 있는 미들웨어(CommonMiddleware 등)보다 위에 있어야
    # preflight(OPTIONS)와 에러 응답에도 CORS 헤더가 붙는다.
    "corsheaders.middleware.CorsMiddleware",
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
        # token 방식 로그인(네이티브 앱 SDK) 검증용 앱 ID (숫자).
        # 다른 카카오 앱에서 발급된 access_token으로 로그인하는 것을 차단한다.
        "app_id": os.getenv("KAKAO_APP_ID", ""),
        "token_url": "https://kauth.kakao.com/oauth/token",
        "token_info_url": "https://kapi.kakao.com/v1/user/access_token_info",
        "profile_url": "https://kapi.kakao.com/v2/user/me",
    },
    "google": {
        "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        "token_url": "https://oauth2.googleapis.com/token",
        # token 방식 로그인(네이티브 앱 SDK) 검증용. aud(발급 대상 client_id)를 대조한다.
        "token_info_url": "https://www.googleapis.com/oauth2/v3/tokeninfo",
        "profile_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        # 네이티브 앱 SDK가 받아오는 토큰의 aud는 웹이 아니라 그 플랫폼의 클라이언트 ID다.
        # 웹 하나만 대조하면 앱 로그인이 전부 막히므로, 같은 프로젝트의 클라이언트를 모두 허용한다.
        "allowed_client_ids": [
            client_id
            for client_id in (
                os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
                os.getenv("GOOGLE_OAUTH_IOS_CLIENT_ID", ""),
                os.getenv("GOOGLE_OAUTH_ANDROID_CLIENT_ID", ""),
            )
            if client_id
        ],
    },
    # 애플은 client_secret을 정적 문자열이 아닌 ES256 JWT로 동적 생성한다.
    # profile_url 없음 — 사용자 정보는 id_token(JWT) 디코딩으로 획득한다.
    "apple": {
        "client_id":   os.getenv("APPLE_CLIENT_ID", ""),    # Service ID (com.example.app)
        "team_id":     os.getenv("APPLE_TEAM_ID", ""),      # 10자리 팀 ID
        "key_id":      os.getenv("APPLE_KEY_ID", ""),       # 개인키 Key ID
        "private_key": os.getenv("APPLE_PRIVATE_KEY", ""),  # PEM 전체 문자열 (\n 포함)
        "token_url":   "https://appleid.apple.com/auth/token",
    },
}

OAUTH_REQUEST_TIMEOUT = int(os.getenv("OAUTH_REQUEST_TIMEOUT", "10"))

# ------------------------------------------------------------
# CORS (브라우저 교차 출처 요청 허용)
# 콤마 구분, 스킴 포함 origin만 (경로 없음). 예:
#   CORS_ALLOWED_ORIGINS=https://skn-1st-mobile.expo.app,http://localhost:19006
# ------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
# ------------------------------------------------------------
# 옷장 (wardrobe) — S3 / 처리 큐
# 상세 값은 apps/wardrobe/services/* 에서 환경변수로 직접 읽는다.
# 필수: WARDROBE_S3_BUCKET, REDIS_URL, WARDROBE_INTERNAL_TOKEN,
#       WARDROBE_CALLBACK_URL
# ------------------------------------------------------------

# ------------------------------------------------------------
# 스타일 캘린더 (style_calendar) — S3
# 상세 값은 apps/style_calendar/services/storage.py에서 읽는다.
# 필수: CALENDAR_S3_BUCKET(미설정 시 WARDROBE_S3_BUCKET 사용)
# 사진 처리 큐와 callback은 기존 옷장 업로드 흐름을 그대로 사용한다.
# ------------------------------------------------------------

# ------------------------------------------------------------
# Qdrant 벡터 DB (apps.recommend)
# 컬렉션 스키마는 apps/recommend/services/qdrant.py가 소유하고
# `manage.py init_qdrant`로 생성한다.
# ------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "10"))
# 임베딩 모델 차원 (FashionSigLIP=768, BGE-M3=1024). 모델 교체 시에만 변경.
QDRANT_IMAGE_VECTOR_DIM = int(os.getenv("QDRANT_IMAGE_VECTOR_DIM", "768"))
QDRANT_TEXT_VECTOR_DIM = int(os.getenv("QDRANT_TEXT_VECTOR_DIM", "1024"))

# Gemini 기반 코디 사진 평가
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_API_BASE_URL = os.getenv(
    "GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com"
).rstrip("/")
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
