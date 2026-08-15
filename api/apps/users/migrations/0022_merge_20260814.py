"""머지: User 예산 갈래(0018)와 BodyMeasurement 측정값 갈래(0021)를 합친다.

두 갈래는 서로 다른 테이블(User / body_measurements)만 건드려
실제 스키마 충돌은 없으므로 빈 operations로 리프를 하나로 모은다.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_user_category_budgets"),
        ("users", "0021_alter_bodymeasurement_leg_length_and_more"),
    ]

    operations = []
