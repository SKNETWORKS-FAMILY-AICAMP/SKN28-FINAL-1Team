"""신체치수(BodyMeasurement) 테이블 추가 — 설정 페이지 입력값, 사용자당 1행."""

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _measure_column(label: str) -> models.DecimalField:
    """models._measure_field와 동일한 정의 (cm/kg, 소수점 1자리, 최소 1)."""
    return models.DecimalField(
        blank=True,
        decimal_places=1,
        help_text=label,
        max_digits=4,
        null=True,
        validators=[django.core.validators.MinValueValidator(Decimal("1"))],
        verbose_name=label,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_alter_socialaccount_provider_apple"),
    ]

    operations = [
        migrations.CreateModel(
            name="BodyMeasurement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("height", _measure_column("키(cm)")),
                ("weight", _measure_column("몸무게(kg)")),
                ("chest", _measure_column("가슴둘레(cm)")),
                ("waist", _measure_column("허리둘레(cm)")),
                ("hip", _measure_column("엉덩이둘레(cm)")),
                ("thigh", _measure_column("허벅지둘레(cm)")),
                ("calf", _measure_column("종아리둘레(cm)")),
                ("arm", _measure_column("팔뚝둘레(cm)")),
                ("shoulder", _measure_column("어깨너비(cm)")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="생성 시각")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="수정 시각")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="body_measurement",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "신체치수",
                "verbose_name_plural": "신체치수",
                "db_table": "body_measurements",
            },
        ),
    ]
