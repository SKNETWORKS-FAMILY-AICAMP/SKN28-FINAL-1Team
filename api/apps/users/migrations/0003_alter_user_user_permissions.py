"""M2M 테이블명 단순화: users_user_permissions → users_permissions.

PermissionsMixin이 자동 생성하는 M2M 테이블명을 users_groups와 짝을 맞춰 정리한다.
db_table만 변경되므로 스키마 에디터가 테이블 리네임으로 처리하며 데이터가 유지된다.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("users", "0002_rename_tables"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="user_permissions",
            field=models.ManyToManyField(
                blank=True,
                db_table="users_permissions",
                help_text="Specific permissions for this user.",
                related_name="user_set",
                related_query_name="user",
                to="auth.permission",
                verbose_name="user permissions",
            ),
        ),
    ]
