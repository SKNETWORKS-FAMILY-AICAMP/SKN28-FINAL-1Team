import apps.chat.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0014_wardrobe_scope_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatrun",
            name="focus_slots",
            field=models.JSONField(
                blank=True,
                db_comment=(
                    "LLM 분석으로 확정한 초점 추천 슬롯 JSON 배열 "
                    "(TOP/BOTTOM/OUTER/DRESS/SHOES/ACCESSORY, 최대 3개)"
                ),
                default=list,
                validators=[apps.chat.models.validate_focus_slots],
            ),
        ),
    ]

