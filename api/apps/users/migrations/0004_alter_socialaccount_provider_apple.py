"""apple을 SocialAccount.provider choices에 추가."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_alter_user_user_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialaccount",
            name="provider",
            field=models.CharField(
                choices=[
                    ("naver", "네이버"),
                    ("kakao", "카카오"),
                    ("google", "구글"),
                    ("apple", "애플"),
                ],
                max_length=20,
                verbose_name="제공사",
            ),
        ),
    ]
