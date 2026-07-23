"""개발 환경 설정."""

from .base import *  # noqa: F401,F403

DEBUG = True

# DJANGO_ALLOWED_HOSTS 환경변수(콤마 구분)가 있으면 사용, 없으면 로컬 기본값.
# base.py에서 이미 환경변수를 파싱하므로 비어 있을 때만 기본값으로 대체한다.
if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# 개발 편의: 브라우저에서 API 탐색 가능
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
