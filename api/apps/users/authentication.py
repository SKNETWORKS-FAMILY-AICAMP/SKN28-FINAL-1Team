"""개발 전용 자동 로그인 인증.

`config.settings.noauth`에서만 사용한다. Authorization 헤더 없이 들어온
모든 요청을 개발용 유저로 자동 인증해, 소셜 로그인 절차 없이 보호된
API를 호출할 수 있게 한다. 헤더에 JWT가 있으면 기존 JWT 인증이 우선한다.

프로덕션 유입 방지를 위해 DEBUG=True + AUTO_LOGIN_ENABLED=True가 아니면
명시적으로 기동을 실패시킨다.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.authentication import BaseAuthentication

from apps.users.models import User

DEV_USERNAME = "dev_autologin"
DEV_NICKNAME = "개발용유저"


class AutoLoginAuthentication(BaseAuthentication):
    """모든 요청을 개발용 유저로 인증한다 (noauth 설정 전용)."""

    def authenticate(self, request):
        # noauth 외 설정에서 클래스만 복사·참조하는 실수를 조용히 통과시키지 않는다.
        if not settings.DEBUG or not getattr(settings, "AUTO_LOGIN_ENABLED", False):
            raise ImproperlyConfigured(
                "AutoLoginAuthentication은 DEBUG=True + AUTO_LOGIN_ENABLED=True "
                "환경(config.settings.noauth)에서만 사용할 수 있습니다."
            )

        user, created = User.objects.get_or_create(
            username=DEV_USERNAME,
            defaults={"nickname": DEV_NICKNAME},
        )
        if created:
            # 소셜 전용 계정과 동일하게 password 로그인 불가 처리
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return (user, None)
