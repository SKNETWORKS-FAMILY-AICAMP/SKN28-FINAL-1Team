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

SPECTACULAR_SETTINGS = {
    "TITLE": "SKN28 Fashion Recommendation API",
    "DESCRIPTION": "SKN28 개인화 패션 추천 서비스 API 문서",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}
