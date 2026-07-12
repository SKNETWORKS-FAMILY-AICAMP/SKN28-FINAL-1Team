"""catalog 초기 마이그레이션.

기존 collector/naver/db.py의 DDL을 Django로 이관한 것이다.
이미 init_schema로 테이블이 생성된 DB에는 `migrate --fake-initial`을 사용한다.
"""

import django.contrib.postgres.fields
import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Now


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="NaverProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("naver_product_id", models.CharField(max_length=40, unique=True)),
                ("product_type", models.SmallIntegerField(blank=True, null=True)),
                ("title", models.CharField(max_length=500)),
                ("title_raw", models.CharField(blank=True, max_length=500, null=True)),
                ("link", models.TextField(blank=True, null=True)),
                ("image_url", models.TextField(blank=True, null=True)),
                ("lprice", models.IntegerField(blank=True, null=True)),
                ("hprice", models.IntegerField(blank=True, null=True)),
                ("mall_name", models.CharField(blank=True, max_length=200, null=True)),
                ("brand", models.CharField(blank=True, max_length=200, null=True)),
                ("maker", models.CharField(blank=True, max_length=200, null=True)),
                ("naver_category1", models.CharField(blank=True, max_length=100, null=True)),
                ("naver_category2", models.CharField(blank=True, max_length=100, null=True)),
                ("naver_category3", models.CharField(blank=True, max_length=100, null=True)),
                ("naver_category4", models.CharField(blank=True, max_length=100, null=True)),
                ("category_large", models.CharField(max_length=30)),
                ("category_small", models.CharField(max_length=50)),
                ("category_source", models.CharField(db_default="keyword", default="keyword", max_length=20)),
                ("season", django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ("style", django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ("color", django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ("pattern", django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ("fit", models.CharField(blank=True, max_length=30, null=True)),
                ("material", django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ("sleeve", models.CharField(blank=True, max_length=20, null=True)),
                ("length", models.CharField(blank=True, max_length=20, null=True)),
                ("usage", django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), blank=True, default=list, size=None)),
                ("layer_role", models.CharField(blank=True, max_length=30, null=True)),
                ("layer_order", models.SmallIntegerField(blank=True, null=True)),
                ("tag_source", models.JSONField(blank=True, default=dict)),
                ("tagging_status", models.CharField(db_default="pending", default="pending", max_length=20)),
                ("tagging_model", models.CharField(blank=True, max_length=60, null=True)),
                ("tagging_used_image", models.BooleanField(db_default=False, default=False)),
                ("tagged_at", models.DateTimeField(blank=True, null=True)),
                ("search_keyword", models.CharField(blank=True, max_length=100, null=True)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("collected_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
            ],
            options={
                "verbose_name": "네이버 상품",
                "verbose_name_plural": "네이버 상품",
                "db_table": "naver_product",
            },
        ),
        migrations.CreateModel(
            name="NaverProductSize",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("size_label", models.CharField(max_length=30)),
                ("size_system", models.CharField(blank=True, max_length=20, null=True)),
                ("total_length", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("shoulder_width", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("chest_width", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("sleeve_length", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("waist_width", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("hip_width", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("rise", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("thigh_width", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("hem_width", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("foot_length_mm", models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True)),
                ("extra_measurements", models.JSONField(blank=True, default=dict)),
                ("source", models.CharField(db_default="manual", default="manual", max_length=30)),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sizes", to="catalog.naverproduct")),
            ],
            options={
                "verbose_name": "상품 사이즈",
                "verbose_name_plural": "상품 사이즈",
                "db_table": "naver_product_size",
            },
        ),
        migrations.AddIndex(
            model_name="naverproduct",
            index=models.Index(fields=["category_large", "category_small"], name="ix_naver_product_category"),
        ),
        migrations.AddIndex(
            model_name="naverproduct",
            index=models.Index(fields=["tagging_status"], name="ix_naver_product_tag_status"),
        ),
        migrations.AddIndex(
            model_name="naverproduct",
            index=django.contrib.postgres.indexes.GinIndex(fields=["season"], name="ix_naver_product_season"),
        ),
        migrations.AddIndex(
            model_name="naverproduct",
            index=django.contrib.postgres.indexes.GinIndex(fields=["style"], name="ix_naver_product_style"),
        ),
        migrations.AddConstraint(
            model_name="naverproductsize",
            constraint=models.UniqueConstraint(fields=("product", "size_label"), name="uq_naver_product_size_label"),
        ),
    ]
