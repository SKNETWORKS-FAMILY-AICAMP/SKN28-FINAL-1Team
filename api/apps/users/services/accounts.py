"""소셜 프로필 → User/SocialAccount 매핑 (fat model / thin view 원칙의 서비스 계층)."""

from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.users.models import SocialAccount, User
from apps.users.services.oauth import SocialProfile


@transaction.atomic
def get_or_create_user(profile: SocialProfile) -> tuple[User, bool]:
    """
    소셜 프로필로 사용자 조회/생성.

    반환: (user, created)
    - 동일 (provider, provider_user_id)가 있으면 기존 사용자 반환 + 프로필 갱신
    - 없으면 새 User + SocialAccount 생성. 이메일 기반 자동 연결은 하지 않는다
      (제공사 간 이메일 소유 검증이 다르므로 보안상 명시적 연결만 허용).
    """
    try:
        account = SocialAccount.objects.select_related("user").get(
            provider=profile.provider, provider_user_id=profile.provider_user_id
        )
        account.email = profile.email
        account.extra_data = profile.raw
        account.save(update_fields=["email", "extra_data", "last_login_at"])
        _refresh_profile(account.user, profile)
        return account.user, False
    except SocialAccount.DoesNotExist:
        pass

    try:
        # savepoint: 동시 최초 로그인 경합 시 아래 except에서 안전하게 재조회
        with transaction.atomic():
            user = User(
                username=f"{profile.provider}_{profile.provider_user_id}",
                email=profile.email,
                nickname=profile.nickname,
                profile_image=profile.profile_image,
            )
            user.set_unusable_password()  # 소셜 전용 계정
            user.save()

            SocialAccount.objects.create(
                user=user,
                provider=profile.provider,
                provider_user_id=profile.provider_user_id,
                email=profile.email,
                extra_data=profile.raw,
            )
            return user, True
    except IntegrityError:
        # 같은 계정의 동시 요청이 먼저 생성한 경우
        account = SocialAccount.objects.select_related("user").get(
            provider=profile.provider, provider_user_id=profile.provider_user_id
        )
        return account.user, False


def _refresh_profile(user: User, profile: SocialProfile) -> None:
    """로그인 시 닉네임/프로필 이미지 최신화 (비어 있는 값은 덮어쓰지 않음)."""
    fields: list[str] = []
    if profile.nickname and user.nickname != profile.nickname:
        user.nickname = profile.nickname
        fields.append("nickname")
    if profile.profile_image and user.profile_image != profile.profile_image:
        user.profile_image = profile.profile_image
        fields.append("profile_image")
    if fields:
        user.save(update_fields=fields)
