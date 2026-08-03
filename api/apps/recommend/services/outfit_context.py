from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.users.models import BodyMeasurement
from apps.users.services.pursuit import get_pursuit
from apps.weather.services import get_current_weather, resolve_coordinates


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

    return {
        "weather": get_current_weather(resolved_lat, resolved_lon),
        "pursuit": pursuit,
        "body": body,
        "personalized": is_authenticated,
    }
