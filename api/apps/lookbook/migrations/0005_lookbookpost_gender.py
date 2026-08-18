from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lookbook", "0004_merge_curated_public_feed"),
    ]

    operations = [
        migrations.AddField(
            model_name="lookbookpost",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("WOMAN", "여성"), ("MAN", "남성")],
                db_comment="룩 성별 구분 (WOMAN/MAN, 기존 미분류 데이터는 NULL)",
                max_length=8,
                null=True,
            ),
        ),
    ]
