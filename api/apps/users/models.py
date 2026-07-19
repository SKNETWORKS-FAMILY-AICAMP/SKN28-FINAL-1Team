"""사용자 및 소셜 계정 모델.

소셜 로그인(naver/kakao/google) 전용 서비스를 전제로 한다.
- User: 서비스 내부 식별/프로필. username은 "provider_고유ID" 형태로 자동 생성된다.
- SocialAccount: 제공사별 계정 연결. 한 User가 여러 제공사를 연결할 수 있다.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import AbstractUser, Permission
from django.core.validators import MinValueValidator
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
        APPLE = "apple", "애플"

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


def _measure_field(label: str) -> models.DecimalField:
    """신체 수치 필드 (cm/kg). 소수점 1자리, 1~999.9 범위."""
    return models.DecimalField(
        label,
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("1"))],
        help_text=label,
    )


class BodyMeasurement(models.Model):
    """사용자 신체치수 (설정 페이지 입력값). 사용자당 1행.

    기본 수치(키/몸무게)와 상세 둘레 수치를 한 행으로 관리한다.
    상세 수치는 전부 선택 입력이라 null을 허용하며, 추후 사진 기반 추론
    기능이 같은 컬럼을 추론값으로 갱신하는 것을 전제로 한다.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="body_measurement"
    )
    # 기본 수치
    height = _measure_field("키(cm)")
    weight = _measure_field("몸무게(kg)")
    # 상세 수치 (전부 선택)
    chest = _measure_field("가슴둘레(cm)")
    waist = _measure_field("허리둘레(cm)")
    hip = _measure_field("엉덩이둘레(cm)")
    thigh = _measure_field("허벅지둘레(cm)")
    calf = _measure_field("종아리둘레(cm)")
    arm = _measure_field("팔뚝둘레(cm)")
    shoulder = _measure_field("어깨너비(cm)")

    created_at = models.DateTimeField("생성 시각", auto_now_add=True)
    updated_at = models.DateTimeField("수정 시각", auto_now=True)

    class Meta:
        db_table = "body_measurements"
        verbose_name = "신체치수"
        verbose_name_plural = "신체치수"

    def __str__(self) -> str:
        return f"{self.user_id}의 신체치수"
