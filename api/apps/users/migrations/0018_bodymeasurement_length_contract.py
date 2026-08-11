"""허벅지·종아리 둘레/팔뚝 컬럼을 제거하고 길이 계약으로 전환한다."""

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


def _length_field(label: str) -> models.DecimalField:
    return models.DecimalField(
        blank=True,
        db_comment=label,
        decimal_places=1,
        help_text=label,
        max_digits=4,
        null=True,
        validators=[django.core.validators.MinValueValidator(Decimal("1"))],
        verbose_name=label,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0017_merge_email_auth_body_ratio"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="bodymeasurement",
            name="thigh",
        ),
        migrations.RemoveField(
            model_name="bodymeasurement",
            name="calf",
        ),
        migrations.RemoveField(
            model_name="bodymeasurement",
            name="arm",
        ),
        migrations.AddField(
            model_name="bodymeasurement",
            name="thigh_length",
            field=_length_field("패션용 허벅지 길이감(cm, 샅선/인심 라인→무릎뼈)"),
        ),
        migrations.AddField(
            model_name="bodymeasurement",
            name="calf_length",
            field=_length_field("패션용 종아리 길이감(cm, 무릎뼈→복사뼈/발목)"),
        ),
        migrations.AddField(
            model_name="bodymeasurement",
            name="torso_length",
            field=_length_field("패션용 상체 길이감(cm, 어깨선→골반점)"),
        ),
        migrations.AddField(
            model_name="bodymeasurement",
            name="leg_length",
            field=_length_field("패션용 하체 길이감(cm, 샅선/인심 라인→복사뼈/발목)"),
        ),
        migrations.AlterField(
            model_name="bodymeasurement",
            name="neck_length",
            field=models.DecimalField(
                blank=True,
                db_comment="패션용 목 길이감(cm, 정면 기준 턱밑/턱끝 라인→목앞/쇄골 라인)",
                decimal_places=1,
                help_text="패션용 목 길이감(cm, 정면 기준 턱밑/턱끝 라인→목앞/쇄골 라인)",
                max_digits=4,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("1"))],
                verbose_name="패션용 목 길이감(cm)",
            ),
        ),
        migrations.AlterField(
            model_name="bodymeasurement",
            name="thigh_calf_ratio",
            field=models.DecimalField(
                blank=True,
                db_comment="패션용 허벅지 길이감 / 종아리 길이감 비율",
                decimal_places=3,
                help_text="패션용 허벅지 길이감 / 종아리 길이감 비율",
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.1")),
                    django.core.validators.MaxValueValidator(Decimal("9.999")),
                ],
                verbose_name="허벅지/종아리 길이감 비율",
            ),
        ),
        migrations.AlterField(
            model_name="bodymeasurement",
            name="torso_leg_ratio",
            field=models.DecimalField(
                blank=True,
                db_comment="패션용 상체 길이감 / 하체 길이감 비율",
                decimal_places=3,
                help_text="패션용 상체 길이감 / 하체 길이감 비율",
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.1")),
                    django.core.validators.MaxValueValidator(Decimal("9.999")),
                ],
                verbose_name="상하체 길이감 비율",
            ),
        ),
        migrations.AlterModelTableComment(
            name="bodymeasurement",
            table_comment="사용자 신체치수 (기본 정보·상세 치수·체형 지표, 사용자당 1행)",
        ),
    ]
