from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from apps.recommend.services.gender import normalize_gender
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
    """체형 행을 스냅샷 JSON으로 만든다.

    성별만 따로 다룬다. 아래 수치 필드는 "값이 없으면 None"이 맞지만, 성별에
    같은 규칙을 적용했다가 사고가 났다. 미입력 성별("")이 ``value or None``에
    걸려 None이 되고, 리트리버 호출부의 ``str(...)``을 지나며 문자열 "None"으로
    굳어, 성별 하드 필터가 아무 예외 없이 사라졌다. 성별은 언제나 문자열이다.
    """
    if measurement is None:
        return None
    fields = (
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
    data: dict[str, Any] = {
        field: float(value) if isinstance(value, Decimal) else (value or None)
        for field in fields
        if (value := getattr(measurement, field)) is not None
    }
    data["gender"] = normalize_gender(measurement.gender)
    return data


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
