"""테이블명 단순화: users_user → users, users_social_account → social_accounts.

앱 접두어가 중복되어 읽기 불편했던 테이블명을 정리한다.
ALTER TABLE ... RENAME은 기존 FK/제약조건을 그대로 유지하므로 데이터 손실 없이 적용된다.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="user",
            table="users",
        ),
        migrations.AlterModelTable(
            name="socialaccount",
            table="social_accounts",
        ),
    ]
