"""좌표 기반 현재 날씨 조회.

홈 화면 등에서 "사용자 위치 → 가까운 예보구역 → 현재 날씨" 흐름을 재사용할 수 있도록
서비스 계층으로 둔다 (fat model / thin view 원칙).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.db.models import Max
from django.utils import timezone

from apps.weather.models import WeatherArea, WeatherNowcastRaw

# 대한민국 대략적 위경도 범위 (제주/독도 포함 여유있게)
_KOREA_LAT_RANGE = (33.0, 39.0)
_KOREA_LON_RANGE = (124.0, 132.0)

# 국내 밖/잘못된 좌표일 때 대체할 기본 좌표 (서울시청)
_DEFAULT_LAT = 37.5665
_DEFAULT_LON = 126.9780

# 격자 후보를 좁히기 위한 사전 필터링 여유 범위(도) — 정확한 거리 계산 전 후보 수를 줄인다.
_BBOX_MARGIN_LAT = 0.5
_BBOX_MARGIN_LON = 0.6

# nowcast가 이 시간보다 오래되면 "최신 아님"으로 표시
_STALE_AFTER = timedelta(hours=2)

# 실황 강수형태(PTY) 라벨 → 5종 하늘상태 중 강수 계열로 단순화.
# "비/눈", "빗방울/눈날림" 같은 혼합 표기는 5종 상태에 없어 비로 합친다.
_SNOW_LABELS = {"눈", "눈날림"}
_NO_PRECIPITATION_LABEL = "강수 없음"

# 광역시/특별자치시는 시도명만 축약해서 보여주고, 그 외(도)는 시군구명을 보여준다.
_METRO_SIDO_ABBR = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
}


def resolve_coordinates(lat: Optional[str], lon: Optional[str]) -> tuple[float, float]:
    """요청 좌표를 검증하고, 없거나 국내 범위를 벗어나면 서울 좌표로 대체한다."""
    try:
        lat_f, lon_f = float(lat), float(lon)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _DEFAULT_LAT, _DEFAULT_LON

    lat_min, lat_max = _KOREA_LAT_RANGE
    lon_min, lon_max = _KOREA_LON_RANGE
    if not (lat_min <= lat_f <= lat_max and lon_min <= lon_f <= lon_max):
        return _DEFAULT_LAT, _DEFAULT_LON
    return lat_f, lon_f


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def find_nearest_area(lat: float, lon: float) -> Optional[WeatherArea]:
    """가장 가까운 격자(GRID) 예보구역을 찾는다."""
    base_qs = WeatherArea.objects.filter(
        area_type="GRID", is_active=True, latitude__isnull=False, longitude__isnull=False
    )
    candidates = list(
        base_qs.filter(
            latitude__gte=lat - _BBOX_MARGIN_LAT,
            latitude__lte=lat + _BBOX_MARGIN_LAT,
            longitude__gte=lon - _BBOX_MARGIN_LON,
            longitude__lte=lon + _BBOX_MARGIN_LON,
        )
    ) or list(base_qs)

    if not candidates:
        return None
    return min(
        candidates,
        key=lambda area: _haversine_km(lat, lon, float(area.latitude), float(area.longitude)),
    )


def format_region_label(area: WeatherArea) -> str:
    sido = (area.sido or "").strip()
    sigungu = (area.sigungu or "").strip()
    if sido in _METRO_SIDO_ABBR:
        return _METRO_SIDO_ABBR[sido]
    return sigungu or sido or area.name


def _round_temperature(temperature: Decimal) -> int:
    return int(temperature.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _resolve_sky_state(area: WeatherArea, nowcast: Optional[WeatherNowcastRaw]) -> Optional[str]:
    pty_label = nowcast.precipitation_type_label if nowcast else None
    if pty_label and pty_label != _NO_PRECIPITATION_LABEL:
        return "눈" if pty_label in _SNOW_LABELS else "비"
    return _nearest_sky_label(area)


def _nearest_sky_label(area: WeatherArea) -> Optional[str]:
    """가장 최근에 발표된 초단기예보(없으면 단기예보)에서, 지금과 가장 가까운 시각의 SKY를 찾는다."""
    rows = _latest_batch(area.very_shorts)
    if not rows:
        rows = _latest_batch(area.shorts)
    if not rows:
        return None

    now = timezone.localtime()
    tz = now.tzinfo

    def _distance_seconds(row) -> float:
        forecast_dt = timezone.make_aware(
            datetime.combine(row.forecast_date, row.forecast_time), tz
        )
        return abs((forecast_dt - now).total_seconds())

    return min(rows, key=_distance_seconds).sky_label


def _latest_batch(related_manager) -> list:
    latest_base_datetime = related_manager.aggregate(Max("base_datetime"))["base_datetime__max"]
    if not latest_base_datetime:
        return []
    return list(related_manager.filter(base_datetime=latest_base_datetime))


def get_current_weather(lat: float, lon: float) -> dict:
    """좌표에서 가장 가까운 구역의 현재 날씨(기온/하늘상태/최신성)를 반환한다."""
    area = find_nearest_area(lat, lon)
    if area is None:
        return {
            "region": None,
            "temperature": None,
            "sky_state": None,
            "is_stale": True,
            "observed_at": None,
        }

    nowcast = area.nowcasts.order_by("-base_datetime").first()
    temperature = None
    observed_at = None
    is_stale = True
    if nowcast is not None and nowcast.temperature is not None:
        temperature = _round_temperature(nowcast.temperature)
        observed_at = nowcast.base_datetime
        is_stale = (timezone.now() - observed_at) > _STALE_AFTER

    return {
        "region": format_region_label(area),
        "temperature": temperature,
        "sky_state": _resolve_sky_state(area, nowcast),
        "is_stale": is_stale,
        "observed_at": observed_at,
    }
