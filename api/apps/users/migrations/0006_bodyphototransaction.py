"""사진 측정 트랜잭션(BodyPhotoTransaction) 테이블 추가 — 사용자당 진행중 1건 제약."""

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_bodymeasurement"),
    ]

    operations = [
        migrations.CreateModel(
            name="BodyPhotoTransaction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("in_progress", "진행중"),
                            ("succeeded", "성공"),
                            ("failed", "실패"),
                        ],
                        default="in_progress",
                        max_length=20,
                        verbose_name="상태",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="생성 시각"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="수정 시각"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="body_photo_transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "사진 측정 트랜잭션",
                "verbose_name_plural": "사진 측정 트랜잭션",
                "db_table": "body_photo_transactions",
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status", "in_progress")),
                        fields=("user",),
                        name="uq_body_photo_tx_in_progress",
                    )
                ],
            },
        ),
    ]
