"""사용자 및 소셜 계정 모델.

소셜 로그인(naver/kakao/google) 전용 서비스를 전제로 한다.
- User: 서비스 내부 식별/프로필. username은 "provider_고유ID" 형태로 자동 생성된다.
- SocialAccount: 제공사별 계정 연결. 한 User가 여러 제공사를 연결할 수 있다.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    # 소셜 로그인 전용이므로 password는 사용하지 않는다 (set_unusable_password).
    nickname = models.CharField("닉네임", max_length=100, blank=True)
    profile_image = models.URLField("프로필 이미지", blank=True)

    # PermissionsMixin의 필드를 재정의해 자동 M2M 테이블명(users_user_permissions)을
    # users_permissions로 단순화한다. db_table 외 옵션은 원본과 동일하게 유지한다.
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
        related_name="user_set",
        related_query_name="user",
        db_table="users_permissions",
    )

    class Meta:
        db_table = "users"
        verbose_name = "사용자"
        verbose_name_plural = "사용자"

    def __str__(self) -> str:
        return self.nickname or self.username


class SocialAccount(models.Model):
    class Provider(models.TextChoices):
        NAVER = "naver", "네이버"
        KAKAO = "kakao", "카카오"
        GOOGLE = "google", "구글"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="social_accounts"
    )
    provider = models.CharField("제공사", max_length=20, choices=Provider.choices)
    provider_user_id = models.CharField("제공사 유저 ID", max_length=255)
    email = models.EmailField("제공사 이메일", blank=True)
    # 제공사 원본 프로필 (디버깅/추가 필드 대비)
    extra_data = models.JSONField("원본 프로필", default=dict, blank=True)
    connected_at = models.DateTimeField("연결 시각", auto_now_add=True)
    last_login_at = models.DateTimeField("마지막 로그인", auto_now=True)

    class Meta:
        db_table = "social_accounts"
        verbose_name = "소셜 계정"
        verbose_name_plural = "소셜 계정"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                name="uq_social_provider_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_user_id}"
