"""users 초기 마이그레이션.

커스텀 AUTH_USER_MODEL은 첫 migrate 전에 이 파일이 반드시 존재해야 한다
(admin/auth가 swappable 의존을 걸기 때문).
모델 변경 시에는 `python manage.py makemigrations users`로 후속 마이그레이션을 생성한다.
"""

import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("username", models.CharField(error_messages={"unique": "A user with that username already exists."}, help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.", max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name="username")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email address")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("nickname", models.CharField(blank=True, max_length=100, verbose_name="닉네임")),
                ("profile_image", models.URLField(blank=True, verbose_name="프로필 이미지")),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={
                "verbose_name": "사용자",
                "verbose_name_plural": "사용자",
                "db_table": "users_user",
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="SocialAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("naver", "네이버"), ("kakao", "카카오"), ("google", "구글")], max_length=20, verbose_name="제공사")),
                ("provider_user_id", models.CharField(max_length=255, verbose_name="제공사 유저 ID")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="제공사 이메일")),
                ("extra_data", models.JSONField(blank=True, default=dict, verbose_name="원본 프로필")),
                ("connected_at", models.DateTimeField(auto_now_add=True, verbose_name="연결 시각")),
                ("last_login_at", models.DateTimeField(auto_now=True, verbose_name="마지막 로그인")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="social_accounts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "소셜 계정",
                "verbose_name_plural": "소셜 계정",
                "db_table": "users_social_account",
            },
        ),
        migrations.AddConstraint(
            model_name="socialaccount",
            constraint=models.UniqueConstraint(fields=("provider", "provider_user_id"), name="uq_social_provider_user"),
        ),
    ]
