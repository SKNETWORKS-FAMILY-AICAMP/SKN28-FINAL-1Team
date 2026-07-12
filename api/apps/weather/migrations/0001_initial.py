"""weather 초기 마이그레이션.

기존 collector/weather/weather_collector_db.py의 DDL을 Django로 이관한 것이다.
이미 init_schema로 테이블이 생성된 DB에는 `migrate --fake-initial`을 사용한다.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Now


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WeatherArea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("area_type", models.CharField(max_length=20)),
                ("name", models.CharField(max_length=200)),
                ("nx", models.SmallIntegerField(blank=True, null=True)),
                ("ny", models.SmallIntegerField(blank=True, null=True)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True)),
                ("sido", models.CharField(blank=True, max_length=60, null=True)),
                ("sigungu", models.CharField(blank=True, max_length=100, null=True)),
                ("eupmyeondong", models.CharField(blank=True, max_length=100, null=True)),
                ("address_label", models.CharField(blank=True, max_length=255, null=True)),
                ("reg_id", models.CharField(blank=True, max_length=30, null=True)),
                ("is_active", models.BooleanField(db_default=True, default=True)),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
            ],
            options={
                "verbose_name": "예보 구역",
                "verbose_name_plural": "예보 구역",
                "db_table": "weather_area",
            },
        ),
        migrations.CreateModel(
            name="WeatherNowcastRaw",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_datetime", models.DateTimeField()),
                ("collected_at", models.DateTimeField()),
                ("temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("precipitation_type_code", models.CharField(blank=True, max_length=20, null=True)),
                ("precipitation_type_label", models.CharField(blank=True, max_length=50, null=True)),
                ("precipitation_amount", models.CharField(blank=True, max_length=50, null=True)),
                ("humidity", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_speed", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_direction_deg", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_direction_label", models.CharField(blank=True, max_length=50, null=True)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
                ("area", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="nowcasts", to="weather.weatherarea")),
            ],
            options={"db_table": "weather_nowcast_raw"},
        ),
        migrations.CreateModel(
            name="WeatherVeryShortRaw",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_datetime", models.DateTimeField()),
                ("collected_at", models.DateTimeField()),
                ("forecast_date", models.DateField()),
                ("forecast_time", models.TimeField()),
                ("temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("sky_code", models.CharField(blank=True, max_length=20, null=True)),
                ("sky_label", models.CharField(blank=True, max_length=50, null=True)),
                ("precipitation_type_code", models.CharField(blank=True, max_length=20, null=True)),
                ("precipitation_type_label", models.CharField(blank=True, max_length=50, null=True)),
                ("precipitation_amount", models.CharField(blank=True, max_length=50, null=True)),
                ("humidity", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_speed", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_direction_deg", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_direction_label", models.CharField(blank=True, max_length=50, null=True)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
                ("area", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="very_shorts", to="weather.weatherarea")),
            ],
            options={"db_table": "weather_very_short_raw"},
        ),
        migrations.CreateModel(
            name="WeatherShortRaw",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_datetime", models.DateTimeField()),
                ("collected_at", models.DateTimeField()),
                ("forecast_date", models.DateField()),
                ("forecast_time", models.TimeField()),
                ("temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("min_temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("max_temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("sky_code", models.CharField(blank=True, max_length=20, null=True)),
                ("sky_label", models.CharField(blank=True, max_length=50, null=True)),
                ("precipitation_type_code", models.CharField(blank=True, max_length=20, null=True)),
                ("precipitation_type_label", models.CharField(blank=True, max_length=50, null=True)),
                ("precipitation_probability", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("precipitation_amount", models.CharField(blank=True, max_length=50, null=True)),
                ("humidity", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_speed", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_direction_deg", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("wind_direction_label", models.CharField(blank=True, max_length=50, null=True)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
                ("area", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shorts", to="weather.weatherarea")),
            ],
            options={"db_table": "weather_short_raw"},
        ),
        migrations.CreateModel(
            name="WeatherMidLandRaw",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_datetime", models.DateTimeField()),
                ("collected_at", models.DateTimeField()),
                ("forecast_date", models.DateField()),
                ("forecast_period", models.CharField(choices=[("AM", "Am"), ("PM", "Pm")], max_length=2)),
                ("sky_label", models.CharField(blank=True, max_length=100, null=True)),
                ("precipitation_probability", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
                ("area", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mid_lands", to="weather.weatherarea")),
            ],
            options={"db_table": "weather_mid_land_raw"},
        ),
        migrations.CreateModel(
            name="WeatherMidTempRaw",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_datetime", models.DateTimeField()),
                ("collected_at", models.DateTimeField()),
                ("forecast_date", models.DateField()),
                ("min_temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("max_temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_default=Now())),
                ("updated_at", models.DateTimeField(db_default=Now())),
                ("area", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mid_temps", to="weather.weatherarea")),
            ],
            options={"db_table": "weather_mid_temp_raw"},
        ),
        migrations.AddConstraint(
            model_name="weatherarea",
            constraint=models.UniqueConstraint(
                condition=Q(area_type="GRID"),
                fields=("area_type", "nx", "ny"),
                name="ux_weather_area_grid",
            ),
        ),
        migrations.AddConstraint(
            model_name="weatherarea",
            constraint=models.UniqueConstraint(
                condition=Q(area_type__in=["MID_LAND", "MID_TEMP"]),
                fields=("area_type", "reg_id"),
                name="ux_weather_area_mid",
            ),
        ),
        migrations.AddConstraint(
            model_name="weathernowcastraw",
            constraint=models.UniqueConstraint(fields=("area", "base_datetime"), name="uq_weather_nowcast"),
        ),
        migrations.AddConstraint(
            model_name="weatherveryshortraw",
            constraint=models.UniqueConstraint(
                fields=("area", "base_datetime", "forecast_date", "forecast_time"),
                name="uq_weather_very_short",
            ),
        ),
        migrations.AddConstraint(
            model_name="weathershortraw",
            constraint=models.UniqueConstraint(
                fields=("area", "base_datetime", "forecast_date", "forecast_time"),
                name="uq_weather_short",
            ),
        ),
        migrations.AddConstraint(
            model_name="weathermidlandraw",
            constraint=models.UniqueConstraint(
                fields=("area", "base_datetime", "forecast_date", "forecast_period"),
                name="uq_weather_mid_land",
            ),
        ),
        migrations.AddConstraint(
            model_name="weathermidlandraw",
            constraint=models.CheckConstraint(
                condition=Q(forecast_period__in=["AM", "PM"]),
                name="ck_weather_mid_land_period",
            ),
        ),
        migrations.AddConstraint(
            model_name="weathermidtempraw",
            constraint=models.UniqueConstraint(
                fields=("area", "base_datetime", "forecast_date"),
                name="uq_weather_mid_temp",
            ),
        ),
    ]
