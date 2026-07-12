"""
프로덕션(AWS) 설정.

시크릿은 AWS Secrets Manager / SSM Parameter Store에서 환경변수로 주입한다.
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

if not os.getenv("DJANGO_SECRET_KEY"):
    raise RuntimeError("DJANGO_SECRET_KEY 환경변수가 필요합니다.")

if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("DJANGO_ALLOWED_HOSTS 환경변수가 필요합니다 (콤마 구분).")

# 프록시(ALB) 뒤에서 HTTPS 인식
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# 로컬 도커에서 http로 테스트할 때는 DJANGO_SECURE_SSL_REDIRECT=false로 끈다.
_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "true").lower() in {"1", "true", "yes"}
SECURE_SSL_REDIRECT = _SSL_REDIRECT
SESSION_COOKIE_SECURE = _SSL_REDIRECT
CSRF_COOKIE_SECURE = _SSL_REDIRECT
