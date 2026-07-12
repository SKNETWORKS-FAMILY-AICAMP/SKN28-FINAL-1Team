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
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
