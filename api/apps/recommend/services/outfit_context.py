from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from apps.users.models import BodyMeasurement
from apps.users.services.pursuit import get_pursuit
from apps.weather.services import get_current_weather, resolve_coordinates


def _json_safe(value: Any) -> Any:
    """컨텍스트를 순수 JSON 타입으로 변환한다.

    weather의 observed_at은 datetime이라 응답 직렬화(JSONField)를 통과하지 못한다.
    실황 데이터가 없는 환경에서는 None이라 드러나지 않지만, weather-collector가
    도는 서버에서는 값이 채워져 503으로 이어진다.
    """
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _serialize_measurement(measurement: BodyMeasurement | None) -> dict | None:
    if measurement is None:
        return None
    fields = (
        "gender",
        "height",
        "weight",
        "chest",
        "waist",
        "hip",
        "thigh",
        "calf",
        "arm",
        "shoulder",
    )
    return {
        field: float(value) if isinstance(value, Decimal) else (value or None)
        for field in fields
        if (value := getattr(measurement, field)) is not None
    }


def build_analysis_context(
    user,
    *,
    lat: float | None,
    lon: float | None,
) -> dict[str, Any]:
    resolved_lat, resolved_lon = resolve_coordinates(lat, lon)
    is_authenticated = bool(user and user.is_authenticated)

    pursuit = None
    body = None
    if is_authenticated:
        pursuit = get_pursuit(user)
        body = _serialize_measurement(
            BodyMeasurement.objects.filter(user=user).first()
        )

    return _json_safe(
        {
            "weather": get_current_weather(resolved_lat, resolved_lon),
            "pursuit": pursuit,
            "body": body,
            "personalized": is_authenticated,
        }
    )
