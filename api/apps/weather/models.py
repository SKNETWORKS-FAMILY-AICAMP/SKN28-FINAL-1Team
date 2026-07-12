"""기상청 수집 데이터 모델.

스키마 소유권은 Django migration에 있다. collector/weather는 raw SQL(psycopg2)로
upsert만 하므로, 모델 변경 시 weather_collector_db.py의 INSERT 컬럼도 함께 갱신한다.

collector가 INSERT 시 생략하는 컬럼(created_at/updated_at)은 db_default로
DB 기본값을 유지한다 (기존 DDL의 DEFAULT NOW()와 동일 동작).
"""

from django.db import models
from django.db.models import Q
from django.db.models.functions import Now


class WeatherArea(models.Model):
    """전국 수집 대상 격자(GRID) / 중기 예보구역(MID_LAND, MID_TEMP) 마스터."""

    area_type = models.CharField(max_length=20)  # GRID | MID_LAND | MID_TEMP
    name = models.CharField(max_length=200)
    nx = models.SmallIntegerField(null=True, blank=True)
    ny = models.SmallIntegerField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    sido = models.CharField(max_length=60, null=True, blank=True)
    sigungu = models.CharField(max_length=100, null=True, blank=True)
    eupmyeondong = models.CharField(max_length=100, null=True, blank=True)
    address_label = models.CharField(max_length=255, null=True, blank=True)
    reg_id = models.CharField(max_length=30, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "weather_area"
        verbose_name = "예보 구역"
        verbose_name_plural = "예보 구역"
        constraints = [
            # 기존 DDL의 부분 unique 인덱스와 동일 (collector upsert의 ON CONFLICT 대상)
            models.UniqueConstraint(
                fields=["area_type", "nx", "ny"],
                condition=Q(area_type="GRID"),
                name="ux_weather_area_grid",
            ),
            models.UniqueConstraint(
                fields=["area_type", "reg_id"],
                condition=Q(area_type__in=["MID_LAND", "MID_TEMP"]),
                name="ux_weather_area_mid",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.area_type}] {self.name}"


class WeatherNowcastRaw(models.Model):
    """실황 Raw."""

    area = models.ForeignKey(WeatherArea, on_delete=models.CASCADE, related_name="nowcasts")
    base_datetime = models.DateTimeField()
    collected_at = models.DateTimeField()
    temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    precipitation_type_code = models.CharField(max_length=20, null=True, blank=True)
    precipitation_type_label = models.CharField(max_length=50, null=True, blank=True)
    precipitation_amount = models.CharField(max_length=50, null=True, blank=True)
    humidity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_speed = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_direction_deg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_direction_label = models.CharField(max_length=50, null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "weather_nowcast_raw"
        constraints = [
            models.UniqueConstraint(
                fields=["area", "base_datetime"], name="uq_weather_nowcast"
            )
        ]


class WeatherVeryShortRaw(models.Model):
    """초단기예보 Raw."""

    area = models.ForeignKey(WeatherArea, on_delete=models.CASCADE, related_name="very_shorts")
    base_datetime = models.DateTimeField()
    collected_at = models.DateTimeField()
    forecast_date = models.DateField()
    forecast_time = models.TimeField()
    temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    sky_code = models.CharField(max_length=20, null=True, blank=True)
    sky_label = models.CharField(max_length=50, null=True, blank=True)
    precipitation_type_code = models.CharField(max_length=20, null=True, blank=True)
    precipitation_type_label = models.CharField(max_length=50, null=True, blank=True)
    precipitation_amount = models.CharField(max_length=50, null=True, blank=True)
    humidity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_speed = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_direction_deg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_direction_label = models.CharField(max_length=50, null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "weather_very_short_raw"
        constraints = [
            models.UniqueConstraint(
                fields=["area", "base_datetime", "forecast_date", "forecast_time"],
                name="uq_weather_very_short",
            )
        ]


class WeatherShortRaw(models.Model):
    """단기예보 Raw."""

    area = models.ForeignKey(WeatherArea, on_delete=models.CASCADE, related_name="shorts")
    base_datetime = models.DateTimeField()
    collected_at = models.DateTimeField()
    forecast_date = models.DateField()
    forecast_time = models.TimeField()
    temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    min_temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    sky_code = models.CharField(max_length=20, null=True, blank=True)
    sky_label = models.CharField(max_length=50, null=True, blank=True)
    precipitation_type_code = models.CharField(max_length=20, null=True, blank=True)
    precipitation_type_label = models.CharField(max_length=50, null=True, blank=True)
    precipitation_probability = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    precipitation_amount = models.CharField(max_length=50, null=True, blank=True)
    humidity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_speed = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_direction_deg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    wind_direction_label = models.CharField(max_length=50, null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "weather_short_raw"
        constraints = [
            models.UniqueConstraint(
                fields=["area", "base_datetime", "forecast_date", "forecast_time"],
                name="uq_weather_short",
            )
        ]


class WeatherMidLandRaw(models.Model):
    """중기 육상예보 Raw."""

    class ForecastPeriod(models.TextChoices):
        AM = "AM"
        PM = "PM"

    area = models.ForeignKey(WeatherArea, on_delete=models.CASCADE, related_name="mid_lands")
    base_datetime = models.DateTimeField()
    collected_at = models.DateTimeField()
    forecast_date = models.DateField()
    forecast_period = models.CharField(max_length=2, choices=ForecastPeriod.choices)
    sky_label = models.CharField(max_length=100, null=True, blank=True)
    precipitation_probability = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "weather_mid_land_raw"
        constraints = [
            models.UniqueConstraint(
                fields=["area", "base_datetime", "forecast_date", "forecast_period"],
                name="uq_weather_mid_land",
            ),
            models.CheckConstraint(
                condition=Q(forecast_period__in=["AM", "PM"]),
                name="ck_weather_mid_land_period",
            ),
        ]


class WeatherMidTempRaw(models.Model):
    """중기 기온예보 Raw."""

    area = models.ForeignKey(WeatherArea, on_delete=models.CASCADE, related_name="mid_temps")
    base_datetime = models.DateTimeField()
    collected_at = models.DateTimeField()
    forecast_date = models.DateField()
    min_temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "weather_mid_temp_raw"
        constraints = [
            models.UniqueConstraint(
                fields=["area", "base_datetime", "forecast_date"],
                name="uq_weather_mid_temp",
            )
        ]
