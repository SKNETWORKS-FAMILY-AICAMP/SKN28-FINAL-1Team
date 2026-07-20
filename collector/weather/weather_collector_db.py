"""
Weather collector for 전국 자동수집 + PostgreSQL 저장.

이 파일은 기존 weather_grid_all_to_csv.py 테스트 코드를 DB 저장형 collector로 재구성한 버전이다.
- WeatherArea: 전국 수집 대상 격자/중기 예보구역 마스터
- WeatherNowcastRaw: 실황 Raw
- WeatherVeryShortRaw: 초단기예보 Raw
- WeatherShortRaw: 단기예보 Raw
- WeatherMidLandRaw: 중기 육상예보 Raw
- WeatherMidTempRaw: 중기 기온예보 Raw

주의
- 테이블 스키마는 Django migration(api/apps/weather)이 소유한다. collector는 upsert만 한다.
  실행 전에 api에서 `python manage.py migrate`가 적용되어 있어야 한다.
- 단기/중기 APIHub URL은 계정에서 신청한 하위 API URL과 다를 수 있으므로 .env에서 반드시 확인한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2.extras import Json, execute_values
except ImportError:  # pragma: no cover - Docker/서버에서 설치 필요
    psycopg2 = None
    Json = None
    execute_values = None


# ============================================================
# 기본 설정
# ============================================================

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

AUTH_KEY = os.getenv("KMA_AUTH_KEY", "").strip()
AUTH_PARAM_NAME = os.getenv("KMA_AUTH_PARAM_NAME", "authKey").strip() or "authKey"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_NAME = os.getenv("POSTGRES_DB", os.getenv("DB_NAME", "weather_db"))
DB_USER = os.getenv("POSTGRES_USER", os.getenv("DB_USER", "postgres"))
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", os.getenv("DB_PASSWORD", ""))
DB_HOST = os.getenv("POSTGRES_HOST", os.getenv("DB_HOST", "localhost"))
DB_PORT = os.getenv("POSTGRES_PORT", os.getenv("DB_PORT", "5432"))

GRID_FILE_PATH = Path(os.getenv("GRID_FILE_PATH", "data/동네예보지점좌표(위경도)_202601.xlsx"))
MID_LAND_AREA_FILE = Path(os.getenv("MID_LAND_AREA_FILE", "data/mid_land_areas.json"))
MID_TEMP_AREA_FILE = Path(os.getenv("MID_TEMP_AREA_FILE", "data/mid_temp_areas.json"))

# APIHub 격자자료 URL. 실제 신청한 API URL이 다르면 .env에서 덮어쓴다.
ODAM_GRID_URL = os.getenv(
    "ODAM_GRID_URL",
    "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_odam_grd",
)
VSRT_GRID_URL = os.getenv(
    "VSRT_GRID_URL",
    "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_vsrt_grd",
)
SHRT_GRID_URL = os.getenv(
    "SHRT_GRID_URL",
    "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_shrt_grd",
)

# 중기 API는 신청/제공 방식에 따라 URL이 다를 수 있으므로 환경변수로 받는다.
MID_LAND_URL = os.getenv("MID_LAND_URL", "").strip()
MID_TEMP_URL = os.getenv("MID_TEMP_URL", "").strip()

# 기상청 동네예보 격자 크기
NX_SIZE = int(os.getenv("KMA_NX_SIZE", "149"))
NY_SIZE = int(os.getenv("KMA_NY_SIZE", "253"))
TOTAL_GRID_SIZE = NX_SIZE * NY_SIZE
Y_REVERSE = os.getenv("Y_REVERSE", "false").lower() in {"1", "true", "yes", "y"}

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("COLLECTOR_MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("COLLECTOR_RETRY_DELAY_SECONDS", "300"))
SCHEDULER_POLL_SECONDS = int(os.getenv("SCHEDULER_POLL_SECONDS", "30"))

VERY_SHORT_FORECAST_HOURS = int(os.getenv("VERY_SHORT_FORECAST_HOURS", "6"))
SHORT_FORECAST_HOURS = int(os.getenv("SHORT_FORECAST_HOURS", "72"))
SHORT_FORECAST_STEP_HOURS = int(os.getenv("SHORT_FORECAST_STEP_HOURS", "3"))

NOWCAST_VARS = [v.strip() for v in os.getenv("NOWCAST_VARS", "T1H,PTY,RN1,REH,WSD,VEC").split(",") if v.strip()]
VERY_SHORT_VARS = [v.strip() for v in os.getenv("VERY_SHORT_VARS", "T1H,SKY,PTY,RN1,REH,WSD,VEC").split(",") if v.strip()]
SHORT_VARS = [v.strip() for v in os.getenv("SHORT_VARS", "TMP,TMN,TMX,SKY,PTY,POP,PCP,REH,WSD,VEC").split(",") if v.strip()]

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("weather_collector")


# ============================================================
# 코드 변환표
# ============================================================

PTY_CODE = {
    "0": "강수 없음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
    "5": "빗방울",
    "6": "빗방울/눈날림",
    "7": "눈날림",
}

SKY_CODE = {
    "1": "맑음",
    "3": "구름많음",
    "4": "흐림",
}

WIND_DIRECTIONS = [
    "북", "북북동", "북동", "동북동",
    "동", "동남동", "남동", "남남동",
    "남", "남남서", "남서", "서남서",
    "서", "서북서", "북서", "북북서",
]


# ============================================================
# 공통 유틸
# ============================================================


def now_kst() -> datetime:
    return datetime.now(KST)


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def clean_code_value(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text in {"", "nan", "None"}:
        return None
    try:
        num = float(text)
        if num == -99:
            return None
        if num.is_integer():
            return str(int(num))
        return str(num)
    except ValueError:
        return text


def clean_numeric_value(value: Any) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        num = float(text)
        if num == -99:
            return None
        return num
    except ValueError:
        return None


def translate_pty(value: Any) -> Optional[str]:
    code = clean_code_value(value)
    if not code:
        return None
    return PTY_CODE.get(code, f"알 수 없음({code})")


def translate_sky(value: Any) -> Optional[str]:
    code = clean_code_value(value)
    if not code:
        return None
    return SKY_CODE.get(code, f"알 수 없음({code})")


def wind_direction_ko(value: Any) -> Optional[str]:
    deg = clean_numeric_value(value)
    if deg is None:
        return None
    idx = int((deg + 11.25) // 22.5) % 16
    return WIND_DIRECTIONS[idx]


def dt_to_tmfc(value: datetime) -> str:
    return value.astimezone(KST).strftime("%Y%m%d%H%M")


def dt_to_tmef(value: datetime) -> str:
    return value.astimezone(KST).strftime("%Y%m%d%H")


def date_time_from_tmef(tmef: str) -> Tuple[date, dtime]:
    dt = datetime.strptime(tmef, "%Y%m%d%H").replace(tzinfo=KST)
    return dt.date(), dt.time()


def find_column(df: pd.DataFrame, candidates: Sequence[str], required: bool = True) -> Optional[str]:
    columns = list(df.columns)
    for candidate in candidates:
        if candidate in columns:
            return candidate
    for col in columns:
        for candidate in candidates:
            if candidate in str(col):
                return col
    if required:
        raise KeyError(f"컬럼을 찾지 못했습니다. 후보={candidates}, 실제={columns}")
    return None


# ============================================================
# 기준시각 계산
# ============================================================


def latest_hourly_base(now: Optional[datetime] = None, delay_minutes: int = 10) -> datetime:
    """매시 00분 기준 자료를 delay_minutes 뒤 수집한다고 보고 최신 기준시각 계산."""
    now = now or now_kst()
    target = now - timedelta(minutes=delay_minutes)
    return target.replace(minute=0, second=0, microsecond=0)


def latest_very_short_base(now: Optional[datetime] = None) -> datetime:
    """초단기예보: 매시 30분 발표, 45분 수집 기준."""
    now = now or now_kst()
    target = now - timedelta(minutes=15)
    if target.minute >= 30:
        return target.replace(minute=30, second=0, microsecond=0)
    prev = target - timedelta(hours=1)
    return prev.replace(minute=30, second=0, microsecond=0)


def latest_short_base(now: Optional[datetime] = None) -> datetime:
    """단기예보: 02/05/08/11/14/17/20/23시 발표, 15분 후 수집 기준."""
    now = now or now_kst()
    target = now - timedelta(minutes=15)
    base_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    today = target.date()
    for hour in reversed(base_hours):
        candidate = datetime.combine(today, dtime(hour, 0), tzinfo=KST)
        if candidate <= target:
            return candidate
    yesterday = today - timedelta(days=1)
    return datetime.combine(yesterday, dtime(23, 0), tzinfo=KST)


def latest_mid_base(now: Optional[datetime] = None) -> datetime:
    """중기예보: 06/18시 발표, 15분 후 수집 기준."""
    now = now or now_kst()
    target = now - timedelta(minutes=15)
    today = target.date()
    for hour in [18, 6]:
        candidate = datetime.combine(today, dtime(hour, 0), tzinfo=KST)
        if candidate <= target:
            return candidate
    yesterday = today - timedelta(days=1)
    return datetime.combine(yesterday, dtime(18, 0), tzinfo=KST)


def forecast_hours(base_dt: datetime, hours: int, step_hours: int = 1) -> List[datetime]:
    return [base_dt + timedelta(hours=h) for h in range(step_hours, hours + 1, step_hours)]


# ============================================================
# DB 연결 및 테스트용 스키마 생성
# ============================================================


def get_connection():
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2가 설치되어 있지 않습니다. Docker/서버 requirements에 psycopg2-binary를 추가하세요."
        )
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )


def ensure_schema(conn) -> None:
    """weather 테이블 존재 확인. 스키마는 Django migration(api/apps/weather)이 관리한다."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.weather_area')")
        exists = cur.fetchone()[0] is not None
    if not exists:
        raise RuntimeError(
            "weather_area 테이블이 없습니다. 스키마는 Django migration이 관리합니다. "
            "api 컨테이너(또는 api/에서 `python manage.py migrate`)를 먼저 실행하세요."
        )
    logger.info("스키마 확인 완료 (weather_area 존재)")


# ============================================================
# WeatherArea 동기화
# ============================================================


def load_grid_area_dataframe() -> pd.DataFrame:
    if not GRID_FILE_PATH.exists():
        raise FileNotFoundError(f"GRID_FILE_PATH 파일을 찾지 못했습니다: {GRID_FILE_PATH}")

    df = pd.read_excel(GRID_FILE_PATH)
    df.columns = [str(col).strip() for col in df.columns]

    x_col = find_column(df, ["격자 X", "격자X", "X", "nx"])
    y_col = find_column(df, ["격자 Y", "격자Y", "Y", "ny"])
    depth1_col = find_column(df, ["1단계", "시도", "시도명"])
    depth2_col = find_column(df, ["2단계", "시군구", "시군구명"])
    depth3_col = find_column(df, ["3단계", "읍면동", "읍면동명"], required=False)
    # "위도"/"경도" 부분매칭만 쓰면 도(度) 정수만 있는 "위도(시)"/"경도(시)" 컬럼이
    # "위도(초/100)"/"경도(초/100)"(소수점 좌표)보다 먼저 걸려서 좌표가 정수로 잘린다.
    # 소수점 컬럼을 후보 1순위로 둬서 정확 매칭이 먼저 잡히게 한다.
    lat_col = find_column(df, ["위도(초/100)", "위도", "lat", "latitude"], required=False)
    lon_col = find_column(df, ["경도(초/100)", "경도", "lon", "lng", "longitude"], required=False)

    rows: List[Dict[str, Any]] = []
    for (nx, ny), group in df.groupby([x_col, y_col]):
        first = group.iloc[0]
        names = []
        for _, row in group.iterrows():
            sido = clean_text(row.get(depth1_col, ""))
            sigungu = clean_text(row.get(depth2_col, ""))
            eup = clean_text(row.get(depth3_col, "")) if depth3_col else ""
            name = " ".join(part for part in [sido, sigungu, eup] if part)
            if name and name not in names:
                names.append(name)

        sido = clean_text(first.get(depth1_col, ""))
        sigungu = clean_text(first.get(depth2_col, ""))
        eup = clean_text(first.get(depth3_col, "")) if depth3_col else ""
        address = names[0] if names else " ".join(part for part in [sido, sigungu, eup] if part)

        rows.append({
            "area_type": "GRID",
            "name": address or f"GRID {int(nx)},{int(ny)}",
            "nx": int(nx),
            "ny": int(ny),
            "latitude": clean_numeric_value(first.get(lat_col)) if lat_col else None,
            "longitude": clean_numeric_value(first.get(lon_col)) if lon_col else None,
            "sido": sido or None,
            "sigungu": sigungu or None,
            "eupmyeondong": eup or None,
            "address_label": address or None,
            "reg_id": None,
            "is_active": True,
        })

    result = pd.DataFrame(rows).sort_values(["sido", "sigungu", "eupmyeondong", "nx", "ny"])
    logger.info("GRID WeatherArea 로드 완료: %s개", len(result))
    return result


def load_mid_area_file(path: Path, area_type: str) -> List[Dict[str, Any]]:
    """
    중기 예보구역 JSON 파일 형식 예시:
    [
      {"name": "서울", "reg_id": "11B10101", "sido": "서울특별시"}
    ]
    """
    if not path.exists():
        logger.warning("%s 파일이 없어 %s WeatherArea 동기화를 건너뜁니다.", path, area_type)
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for item in data:
        reg_id = item.get("reg_id") or item.get("regId")
        name = item.get("name") or item.get("address_label") or reg_id
        if not reg_id:
            raise ValueError(f"{path} 항목에 reg_id가 없습니다: {item}")
        rows.append({
            "area_type": area_type,
            "name": name,
            "nx": None,
            "ny": None,
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "sido": item.get("sido"),
            "sigungu": item.get("sigungu"),
            "eupmyeondong": item.get("eupmyeondong"),
            "address_label": item.get("address_label") or name,
            "reg_id": reg_id,
            "is_active": item.get("is_active", True),
        })
    return rows


def sync_weather_areas(conn, include_grid: bool = True, include_mid: bool = True) -> None:
    rows: List[Dict[str, Any]] = []
    if include_grid:
        rows.extend(load_grid_area_dataframe().to_dict("records"))
    if include_mid:
        rows.extend(load_mid_area_file(MID_LAND_AREA_FILE, "MID_LAND"))
        rows.extend(load_mid_area_file(MID_TEMP_AREA_FILE, "MID_TEMP"))

    if not rows:
        logger.warning("동기화할 WeatherArea 데이터가 없습니다.")
        return

    grid_rows = [r for r in rows if r["area_type"] == "GRID"]
    mid_rows = [r for r in rows if r["area_type"] in {"MID_LAND", "MID_TEMP"}]

    with conn.cursor() as cur:
        if grid_rows:
            values = [(
                r["area_type"], r["name"], r["nx"], r["ny"], r["latitude"], r["longitude"],
                r["sido"], r["sigungu"], r["eupmyeondong"], r["address_label"], r["reg_id"], r["is_active"],
            ) for r in grid_rows]
            sql = """
            INSERT INTO weather_area (
                area_type, name, nx, ny, latitude, longitude, sido, sigungu, eupmyeondong,
                address_label, reg_id, is_active
            ) VALUES %s
            ON CONFLICT (area_type, nx, ny) WHERE area_type = 'GRID'
            DO UPDATE SET
                name = EXCLUDED.name,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                sido = EXCLUDED.sido,
                sigungu = EXCLUDED.sigungu,
                eupmyeondong = EXCLUDED.eupmyeondong,
                address_label = EXCLUDED.address_label,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """
            execute_values(cur, sql, values)

        if mid_rows:
            values = [(
                r["area_type"], r["name"], r["nx"], r["ny"], r["latitude"], r["longitude"],
                r["sido"], r["sigungu"], r["eupmyeondong"], r["address_label"], r["reg_id"], r["is_active"],
            ) for r in mid_rows]
            sql = """
            INSERT INTO weather_area (
                area_type, name, nx, ny, latitude, longitude, sido, sigungu, eupmyeondong,
                address_label, reg_id, is_active
            ) VALUES %s
            ON CONFLICT (area_type, reg_id) WHERE area_type IN ('MID_LAND', 'MID_TEMP')
            DO UPDATE SET
                name = EXCLUDED.name,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                sido = EXCLUDED.sido,
                sigungu = EXCLUDED.sigungu,
                eupmyeondong = EXCLUDED.eupmyeondong,
                address_label = EXCLUDED.address_label,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """
            execute_values(cur, sql, values)

    conn.commit()
    logger.info("WeatherArea 동기화 완료: GRID=%s, MID=%s", len(grid_rows), len(mid_rows))


@dataclass(frozen=True)
class Area:
    id: int
    area_type: str
    nx: Optional[int]
    ny: Optional[int]
    reg_id: Optional[str]
    name: str


def get_active_areas(conn, area_type: str) -> List[Area]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, area_type, nx, ny, reg_id, name
            FROM weather_area
            WHERE area_type = %s AND is_active = TRUE
            ORDER BY id
            """,
            (area_type,),
        )
        return [Area(*row) for row in cur.fetchall()]


# ============================================================
# API 호출/파싱
# ============================================================


def request_text(url: str, params: Dict[str, Any]) -> Tuple[str, str]:
    if not AUTH_KEY:
        raise ValueError("KMA_AUTH_KEY가 없습니다. .env 또는 Docker env에 설정하세요.")
    request_params = params.copy()
    request_params[AUTH_PARAM_NAME] = AUTH_KEY

    response = requests.get(url, params=request_params, timeout=REQUEST_TIMEOUT)
    logger.info("요청 URL: %s", response.url)
    logger.info("HTTP 상태코드: %s", response.status_code)
    if response.status_code != 200:
        logger.error("응답 앞부분: %s", response.text[:2000])
        response.raise_for_status()
    return response.text, response.url


def request_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    text, _ = request_text(url, params)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON 응답 파싱 실패. 응답 앞부분={text[:1000]}") from exc


def parse_grid_text(text: str, var_name: str, y_reverse: bool = False) -> pd.DataFrame:
    values = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(values) < TOTAL_GRID_SIZE:
        logger.error("%s 응답 숫자 개수=%s, 필요=%s", var_name, len(values), TOTAL_GRID_SIZE)
        logger.error("응답 앞부분: %s", text[:3000])
        raise RuntimeError(f"{var_name} 격자자료 값 개수가 부족합니다.")
    if len(values) > TOTAL_GRID_SIZE:
        logger.warning("%s 응답 숫자 개수=%s, 필요한 앞쪽 %s개만 사용", var_name, len(values), TOTAL_GRID_SIZE)
    values = values[:TOTAL_GRID_SIZE]

    rows = []
    idx = 0
    y_range = range(NY_SIZE, 0, -1) if y_reverse else range(1, NY_SIZE + 1)
    for y in y_range:
        for x in range(1, NX_SIZE + 1):
            rows.append({"nx": x, "ny": y, var_name: values[idx]})
            idx += 1
    return pd.DataFrame(rows)


def fetch_grid_var(url: str, var_name: str, tmfc: str, tmef: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    params = {"tmfc": tmfc, "vars": var_name}
    if tmef:
        params["tmef"] = tmef
    text, request_url = request_text(url, params)
    return parse_grid_text(text, var_name, y_reverse=Y_REVERSE), request_url


def merge_weather_frames(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    result: Optional[pd.DataFrame] = None
    for df in frames:
        result = df if result is None else result.merge(df, on=["nx", "ny"], how="outer")
    if result is None:
        raise ValueError("병합할 DataFrame이 없습니다.")
    return result


def fetch_grid_bundle(url: str, vars_: Sequence[str], tmfc: str, tmef: Optional[str] = None) -> Tuple[pd.DataFrame, Dict[str, str]]:
    frames = []
    request_urls: Dict[str, str] = {}
    for var in vars_:
        logger.info("격자 변수 수집: var=%s, tmfc=%s, tmef=%s", var, tmfc, tmef)
        df, request_url = fetch_grid_var(url, var, tmfc, tmef)
        frames.append(df)
        request_urls[var] = request_url
    return merge_weather_frames(frames), request_urls


def grid_area_id_map(conn) -> Dict[Tuple[int, int], int]:
    areas = get_active_areas(conn, "GRID")
    return {(a.nx, a.ny): a.id for a in areas if a.nx is not None and a.ny is not None}


# ============================================================
# Raw 테이블 저장
# ============================================================


def upsert_nowcast_rows(conn, rows: Sequence[Tuple[Any, ...]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    sql = """
    INSERT INTO weather_nowcast_raw (
        area_id, base_datetime, collected_at, temperature,
        precipitation_type_code, precipitation_type_label, precipitation_amount,
        humidity, wind_speed, wind_direction_deg, wind_direction_label, raw_data
    ) VALUES %s
    ON CONFLICT (area_id, base_datetime)
    DO UPDATE SET
        collected_at = EXCLUDED.collected_at,
        temperature = EXCLUDED.temperature,
        precipitation_type_code = EXCLUDED.precipitation_type_code,
        precipitation_type_label = EXCLUDED.precipitation_type_label,
        precipitation_amount = EXCLUDED.precipitation_amount,
        humidity = EXCLUDED.humidity,
        wind_speed = EXCLUDED.wind_speed,
        wind_direction_deg = EXCLUDED.wind_direction_deg,
        wind_direction_label = EXCLUDED.wind_direction_label,
        raw_data = EXCLUDED.raw_data,
        updated_at = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows), 0


def upsert_very_short_rows(conn, rows: Sequence[Tuple[Any, ...]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    sql = """
    INSERT INTO weather_very_short_raw (
        area_id, base_datetime, collected_at, forecast_date, forecast_time,
        temperature, sky_code, sky_label,
        precipitation_type_code, precipitation_type_label, precipitation_amount,
        humidity, wind_speed, wind_direction_deg, wind_direction_label, raw_data
    ) VALUES %s
    ON CONFLICT (area_id, base_datetime, forecast_date, forecast_time)
    DO UPDATE SET
        collected_at = EXCLUDED.collected_at,
        temperature = EXCLUDED.temperature,
        sky_code = EXCLUDED.sky_code,
        sky_label = EXCLUDED.sky_label,
        precipitation_type_code = EXCLUDED.precipitation_type_code,
        precipitation_type_label = EXCLUDED.precipitation_type_label,
        precipitation_amount = EXCLUDED.precipitation_amount,
        humidity = EXCLUDED.humidity,
        wind_speed = EXCLUDED.wind_speed,
        wind_direction_deg = EXCLUDED.wind_direction_deg,
        wind_direction_label = EXCLUDED.wind_direction_label,
        raw_data = EXCLUDED.raw_data,
        updated_at = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows), 0


def upsert_short_rows(conn, rows: Sequence[Tuple[Any, ...]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    sql = """
    INSERT INTO weather_short_raw (
        area_id, base_datetime, collected_at, forecast_date, forecast_time,
        temperature, min_temperature, max_temperature, sky_code, sky_label,
        precipitation_type_code, precipitation_type_label, precipitation_probability,
        precipitation_amount, humidity, wind_speed, wind_direction_deg,
        wind_direction_label, raw_data
    ) VALUES %s
    ON CONFLICT (area_id, base_datetime, forecast_date, forecast_time)
    DO UPDATE SET
        collected_at = EXCLUDED.collected_at,
        temperature = EXCLUDED.temperature,
        min_temperature = EXCLUDED.min_temperature,
        max_temperature = EXCLUDED.max_temperature,
        sky_code = EXCLUDED.sky_code,
        sky_label = EXCLUDED.sky_label,
        precipitation_type_code = EXCLUDED.precipitation_type_code,
        precipitation_type_label = EXCLUDED.precipitation_type_label,
        precipitation_probability = EXCLUDED.precipitation_probability,
        precipitation_amount = EXCLUDED.precipitation_amount,
        humidity = EXCLUDED.humidity,
        wind_speed = EXCLUDED.wind_speed,
        wind_direction_deg = EXCLUDED.wind_direction_deg,
        wind_direction_label = EXCLUDED.wind_direction_label,
        raw_data = EXCLUDED.raw_data,
        updated_at = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows), 0


def upsert_mid_land_rows(conn, rows: Sequence[Tuple[Any, ...]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    sql = """
    INSERT INTO weather_mid_land_raw (
        area_id, base_datetime, collected_at, forecast_date, forecast_period,
        sky_label, precipitation_probability, raw_data
    ) VALUES %s
    ON CONFLICT (area_id, base_datetime, forecast_date, forecast_period)
    DO UPDATE SET
        collected_at = EXCLUDED.collected_at,
        sky_label = EXCLUDED.sky_label,
        precipitation_probability = EXCLUDED.precipitation_probability,
        raw_data = EXCLUDED.raw_data,
        updated_at = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows), 0


def upsert_mid_temp_rows(conn, rows: Sequence[Tuple[Any, ...]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    sql = """
    INSERT INTO weather_mid_temp_raw (
        area_id, base_datetime, collected_at, forecast_date,
        min_temperature, max_temperature, raw_data
    ) VALUES %s
    ON CONFLICT (area_id, base_datetime, forecast_date)
    DO UPDATE SET
        collected_at = EXCLUDED.collected_at,
        min_temperature = EXCLUDED.min_temperature,
        max_temperature = EXCLUDED.max_temperature,
        raw_data = EXCLUDED.raw_data,
        updated_at = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows), 0


# ============================================================
# Collector 구현
# ============================================================


def collect_nowcast(conn, base_dt: Optional[datetime] = None) -> int:
    base_dt = base_dt or latest_hourly_base(delay_minutes=10)
    tmfc = dt_to_tmfc(base_dt)
    collected_at = now_kst()

    area_map = grid_area_id_map(conn)
    if not area_map:
        raise RuntimeError("GRID WeatherArea가 없습니다. 먼저 sync-areas를 실행하세요.")

    bundle, request_urls = fetch_grid_bundle(ODAM_GRID_URL, NOWCAST_VARS, tmfc)
    rows = []
    for record in bundle.to_dict("records"):
        key = (int(record["nx"]), int(record["ny"]))
        area_id = area_map.get(key)
        if area_id is None:
            continue
        pty_code = clean_code_value(record.get("PTY"))
        vec = clean_numeric_value(record.get("VEC"))
        raw = {
            "api": "ODAM_GRID",
            "tmfc": tmfc,
            "nx": key[0],
            "ny": key[1],
            "values": {var: record.get(var) for var in NOWCAST_VARS},
            "request_urls": request_urls,
        }
        rows.append((
            area_id,
            base_dt,
            collected_at,
            clean_numeric_value(record.get("T1H")),
            pty_code,
            translate_pty(pty_code),
            str(record.get("RN1")) if record.get("RN1") not in (None, "") else None,
            clean_numeric_value(record.get("REH")),
            clean_numeric_value(record.get("WSD")),
            vec,
            wind_direction_ko(vec),
            Json(raw),
        ))
    upsert_nowcast_rows(conn, rows)
    logger.info("WeatherNowcastRaw 저장 완료: %s rows", len(rows))
    return len(rows)


def collect_very_short(conn, base_dt: Optional[datetime] = None) -> int:
    base_dt = base_dt or latest_very_short_base()
    tmfc = dt_to_tmfc(base_dt)
    collected_at = now_kst()
    area_map = grid_area_id_map(conn)
    if not area_map:
        raise RuntimeError("GRID WeatherArea가 없습니다. 먼저 sync-areas를 실행하세요.")

    total_rows = 0
    for target_dt in forecast_hours(base_dt, VERY_SHORT_FORECAST_HOURS, step_hours=1):
        tmef = dt_to_tmef(target_dt)
        forecast_date, forecast_time = date_time_from_tmef(tmef)
        bundle, request_urls = fetch_grid_bundle(VSRT_GRID_URL, VERY_SHORT_VARS, tmfc, tmef)

        rows = []
        for record in bundle.to_dict("records"):
            key = (int(record["nx"]), int(record["ny"]))
            area_id = area_map.get(key)
            if area_id is None:
                continue
            sky_code = clean_code_value(record.get("SKY"))
            pty_code = clean_code_value(record.get("PTY"))
            vec = clean_numeric_value(record.get("VEC"))
            raw = {
                "api": "VSRT_GRID",
                "tmfc": tmfc,
                "tmef": tmef,
                "nx": key[0],
                "ny": key[1],
                "values": {var: record.get(var) for var in VERY_SHORT_VARS},
                "request_urls": request_urls,
            }
            rows.append((
                area_id,
                base_dt,
                collected_at,
                forecast_date,
                forecast_time,
                clean_numeric_value(record.get("T1H")),
                sky_code,
                translate_sky(sky_code),
                pty_code,
                translate_pty(pty_code),
                str(record.get("RN1")) if record.get("RN1") not in (None, "") else None,
                clean_numeric_value(record.get("REH")),
                clean_numeric_value(record.get("WSD")),
                vec,
                wind_direction_ko(vec),
                Json(raw),
            ))
        upsert_very_short_rows(conn, rows)
        total_rows += len(rows)
        logger.info("WeatherVeryShortRaw 저장 완료: tmef=%s, %s rows", tmef, len(rows))
    return total_rows


def collect_short(conn, base_dt: Optional[datetime] = None) -> int:
    """
    단기 격자자료 collector.
    SHRT_GRID_URL이 실제 신청 API URL과 다르면 .env에서 수정해야 한다.
    """
    base_dt = base_dt or latest_short_base()
    tmfc = dt_to_tmfc(base_dt)
    collected_at = now_kst()
    area_map = grid_area_id_map(conn)
    if not area_map:
        raise RuntimeError("GRID WeatherArea가 없습니다. 먼저 sync-areas를 실행하세요.")

    total_rows = 0
    for target_dt in forecast_hours(base_dt, SHORT_FORECAST_HOURS, step_hours=SHORT_FORECAST_STEP_HOURS):
        tmef = dt_to_tmef(target_dt)
        forecast_date, forecast_time = date_time_from_tmef(tmef)
        bundle, request_urls = fetch_grid_bundle(SHRT_GRID_URL, SHORT_VARS, tmfc, tmef)

        rows = []
        for record in bundle.to_dict("records"):
            key = (int(record["nx"]), int(record["ny"]))
            area_id = area_map.get(key)
            if area_id is None:
                continue
            sky_code = clean_code_value(record.get("SKY"))
            pty_code = clean_code_value(record.get("PTY"))
            vec = clean_numeric_value(record.get("VEC"))
            raw = {
                "api": "SHRT_GRID",
                "tmfc": tmfc,
                "tmef": tmef,
                "nx": key[0],
                "ny": key[1],
                "values": {var: record.get(var) for var in SHORT_VARS},
                "request_urls": request_urls,
            }
            rows.append((
                area_id,
                base_dt,
                collected_at,
                forecast_date,
                forecast_time,
                clean_numeric_value(record.get("TMP")),
                clean_numeric_value(record.get("TMN")),
                clean_numeric_value(record.get("TMX")),
                sky_code,
                translate_sky(sky_code),
                pty_code,
                translate_pty(pty_code),
                clean_numeric_value(record.get("POP")),
                str(record.get("PCP")) if record.get("PCP") not in (None, "") else None,
                clean_numeric_value(record.get("REH")),
                clean_numeric_value(record.get("WSD")),
                vec,
                wind_direction_ko(vec),
                Json(raw),
            ))
        upsert_short_rows(conn, rows)
        total_rows += len(rows)
        logger.info("WeatherShortRaw 저장 완료: tmef=%s, %s rows", tmef, len(rows))
    return total_rows


def extract_item_from_mid_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """공공데이터포털/일반 JSON 응답을 최대한 유연하게 처리."""
    body = data.get("response", {}).get("body", {}) if isinstance(data, dict) else {}
    items = body.get("items", {}).get("item") if isinstance(body, dict) else None
    if isinstance(items, list):
        return items[0] if items else {}
    if isinstance(items, dict):
        return items
    if isinstance(data, dict) and any(k.startswith("wf") or k.startswith("ta") for k in data.keys()):
        return data
    raise RuntimeError(f"중기 응답 item 추출 실패: {str(data)[:1000]}")



def tmfc_hour(value: datetime) -> str:
    return value.astimezone(KST).strftime("%Y%m%d%H")


def parse_kma_ymdhm(value: str) -> datetime:
    text = str(value).strip()
    if len(text) >= 12:
        return datetime.strptime(text[:12], "%Y%m%d%H%M").replace(tzinfo=KST)
    if len(text) >= 10:
        return datetime.strptime(text[:10], "%Y%m%d%H").replace(tzinfo=KST)
    raise ValueError(f"기상청 시각 파싱 실패: {value}")


def mid_tmef_range(base_dt: datetime, start_offset: int = 4, end_offset: int = 7) -> Tuple[str, str]:
    return (
        (base_dt + timedelta(days=start_offset)).strftime("%Y%m%d"),
        (base_dt + timedelta(days=end_offset)).strftime("%Y%m%d"),
    )


def nullable_number(value):
    value = clean_numeric_value(value)
    if value == "":
        return None
    return value


def parse_typ01_mid_text(text: str) -> List[Dict[str, Any]]:
    """
    APIHub typ01 중기예보 텍스트 응답 파서.

    예시:
    #START7777
    # REG_ID TM_FC TM_EF MOD STN C SKY PRE CONF WF RN_ST
    11B00000 202607100600 202607140000 A02 109 2 WB04 WB00 없음 "흐림" 40
    """
    rows: List[Dict[str, Any]] = []
    header: Optional[List[str]] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#START") or line.startswith("#END"):
            continue

        if line.startswith("#"):
            candidate = line.lstrip("#").strip()
            if "REG_ID" in candidate and "TM_FC" in candidate and "TM_EF" in candidate:
                header = candidate.split()
            continue

        if header is None:
            continue

        try:
            parts = shlex.split(line)
        except ValueError:
            logger.warning("typ01 중기 응답 행 파싱 실패: %s", line[:500])
            continue

        if len(parts) < 3:
            continue

        row: Dict[str, Any] = {}

        for idx, key in enumerate(header):
            row[key] = parts[idx] if idx < len(parts) else ""

        if len(parts) > len(header):
            for extra_idx, value in enumerate(parts[len(header):], start=1):
                row[f"EXTRA_{extra_idx}"] = value

        row["_raw_parts"] = parts
        rows.append(row)

    return rows


def request_typ01_mid_rows(url: str, area: Area, base_dt: datetime) -> List[Dict[str, Any]]:
    if not area.reg_id:
        return []

    tmef1, tmef2 = mid_tmef_range(base_dt)

    params = {
        "reg": area.reg_id,
        "tmfc1": tmfc_hour(base_dt),
        "tmfc2": tmfc_hour(base_dt),
        "tmef1": tmef1,
        "tmef2": tmef2,
        "disp": "0",
        "help": "0",
    }

    text, request_url = request_text(url, params)

    rows = parse_typ01_mid_text(text)
    rows = [row for row in rows if row.get("REG_ID") == area.reg_id]

    for row in rows:
        row["_request_url"] = request_url

    return rows


def collect_mid_land(conn, base_dt: Optional[datetime] = None) -> int:
    if not MID_LAND_URL:
        raise RuntimeError("MID_LAND_URL이 없습니다. 중기 육상예보 API URL을 .env에 설정하세요.")

    base_dt = base_dt or latest_mid_base()
    collected_at = now_kst()

    areas = get_active_areas(conn, "MID_LAND")
    if not areas:
        raise RuntimeError("MID_LAND WeatherArea가 없습니다. mid_land_areas.json 동기화가 필요합니다.")

    all_rows = []

    for area in areas:
        for item in request_typ01_mid_rows(MID_LAND_URL, area, base_dt):
            try:
                tm_fc_dt = parse_kma_ymdhm(item["TM_FC"])
                tm_ef_dt = parse_kma_ymdhm(item["TM_EF"])
            except Exception:
                logger.warning("중기 육상 시각 파싱 실패: %s", item)
                continue

            forecast_date = tm_ef_dt.date()
            day_offset = (forecast_date - base_dt.date()).days

            if not 4 <= day_offset <= 7:
                continue

            forecast_period = "AM" if tm_ef_dt.hour < 12 else "PM"

            raw = {
                "api": "MID_LAND_TYP01",
                "tmFc": item.get("TM_FC"),
                "tmEf": item.get("TM_EF"),
                "regId": area.reg_id,
                "values": item,
                "request_url": item.get("_request_url"),
            }

            all_rows.append((
                area.id,
                tm_fc_dt,
                collected_at,
                forecast_date,
                forecast_period,
                item.get("WF"),
                nullable_number(item.get("RN_ST")),
                Json(raw),
            ))

    upsert_mid_land_rows(conn, all_rows)
    logger.info("WeatherMidLandRaw 저장 완료: %s rows", len(all_rows))
    return len(all_rows)


def pick_first_value(item: Dict[str, Any], candidates: List[str]):
    for key in candidates:
        if key in item and item.get(key) not in [None, ""]:
            return item.get(key)
    return None


def collect_mid_temp(conn, base_dt: Optional[datetime] = None) -> int:
    if not MID_TEMP_URL:
        raise RuntimeError("MID_TEMP_URL이 없습니다. 중기 기온예보 API URL을 .env에 설정하세요.")

    base_dt = base_dt or latest_mid_base()
    collected_at = now_kst()

    areas = get_active_areas(conn, "MID_TEMP")
    if not areas:
        raise RuntimeError("MID_TEMP WeatherArea가 없습니다. mid_temp_areas.json 동기화가 필요합니다.")

    all_rows = []

    min_candidates = [
        "MIN", "TMN", "TA_MIN", "TAMIN", "MIN_TA", "MN", "TA_MIN3"
    ]
    max_candidates = [
        "MAX", "TMX", "TA_MAX", "TAMAX", "MAX_TA", "MX", "TA_MAX3"
    ]

    for area in areas:
        for item in request_typ01_mid_rows(MID_TEMP_URL, area, base_dt):
            try:
                tm_fc_dt = parse_kma_ymdhm(item["TM_FC"])
                tm_ef_dt = parse_kma_ymdhm(item["TM_EF"])
            except Exception:
                logger.warning("중기 기온 시각 파싱 실패: %s", item)
                continue

            forecast_date = tm_ef_dt.date()
            day_offset = (forecast_date - base_dt.date()).days

            if not 4 <= day_offset <= 7:
                continue

            min_value = pick_first_value(item, min_candidates)
            max_value = pick_first_value(item, max_candidates)

            raw = {
                "api": "MID_TEMP_TYP01",
                "tmFc": item.get("TM_FC"),
                "tmEf": item.get("TM_EF"),
                "regId": area.reg_id,
                "values": item,
                "request_url": item.get("_request_url"),
            }

            all_rows.append((
                area.id,
                tm_fc_dt,
                collected_at,
                forecast_date,
                nullable_number(min_value),
                nullable_number(max_value),
                Json(raw),
            ))

    upsert_mid_temp_rows(conn, all_rows)
    logger.info("WeatherMidTempRaw 저장 완료: %s rows", len(all_rows))
    return len(all_rows)

COLLECTOR_BY_JOB = {
    "nowcast": collect_nowcast,
    "very_short": collect_very_short,
    "short": collect_short,
    "mid_land": collect_mid_land,
    "mid_temp": collect_mid_temp,
}


# ============================================================
# 재시도/스케줄러
# ============================================================


def run_with_retry(job_name: str, conn, max_retries: int = MAX_RETRIES) -> int:
    if job_name not in COLLECTOR_BY_JOB:
        raise ValueError(f"알 수 없는 job: {job_name}")
    last_error: Optional[BaseException] = None
    for attempt in range(max_retries + 1):
        try:
            logger.info("수집 시작: job=%s, attempt=%s", job_name, attempt + 1)
            rows = COLLECTOR_BY_JOB[job_name](conn)
            logger.info("수집 성공: job=%s, rows=%s", job_name, rows)
            return rows
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            last_error = exc
            logger.exception("수집 실패: job=%s, attempt=%s/%s", job_name, attempt + 1, max_retries + 1)
            if attempt < max_retries:
                logger.info("%s초 후 재시도합니다.", RETRY_DELAY_SECONDS)
                time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"{job_name} 최종 실패") from last_error


def jobs_due_at(current: datetime) -> List[str]:
    hour = current.hour
    minute = current.minute
    jobs: List[str] = []
    if minute == 10:
        jobs.append("nowcast")
    if minute == 45:
        jobs.append("very_short")
    if minute == 15 and hour in {2, 5, 8, 11, 14, 17, 20, 23}:
        jobs.append("short")
    if minute == 15 and hour in {6, 18}:
        jobs.extend(["mid_land", "mid_temp"])
    return jobs


def run_scheduler(conn) -> None:
    logger.info("collector scheduler 시작. KST 기준 고정 수집 시각에 실행합니다.")
    last_run_keys: set[Tuple[str, str]] = set()
    while True:
        current = now_kst().replace(second=0, microsecond=0)
        due_jobs = jobs_due_at(current)
        for job_name in due_jobs:
            run_key = (job_name, current.isoformat())
            if run_key in last_run_keys:
                continue
            last_run_keys.add(run_key)
            run_with_retry(job_name, conn)
        # 메모리 무한 증가 방지: 최근 2일 키만 남길 필요가 있지만 하루 job 수가 적어 간단히 크기 제한만 둔다.
        if len(last_run_keys) > 500:
            last_run_keys = set(list(last_run_keys)[-200:])
        time.sleep(SCHEDULER_POLL_SECONDS)


# ============================================================
# CLI
# ============================================================


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KMA weather DB collector")
    parser.add_argument("--sync-areas", action="store_true", help="WeatherArea 마스터 동기화")
    parser.add_argument(
        "--job",
        choices=["nowcast", "very_short", "short", "mid_land", "mid_temp", "all"],
        help="한 번 실행할 수집 job",
    )
    parser.add_argument("--scheduler", action="store_true", help="고정 스케줄에 따라 계속 자동수집")
    parser.add_argument("--no-grid", action="store_true", help="sync-areas 시 GRID 동기화 제외")
    parser.add_argument("--no-mid", action="store_true", help="sync-areas 시 MID_LAND/MID_TEMP 동기화 제외")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    conn = get_connection()
    try:
        ensure_schema(conn)  # 스키마는 Django migration이 관리. 없으면 즉시 실패.
        if args.sync_areas:
            sync_weather_areas(conn, include_grid=not args.no_grid, include_mid=not args.no_mid)
        if args.job:
            if args.job == "all":
                for job in ["nowcast", "very_short", "short", "mid_land", "mid_temp"]:
                    run_with_retry(job, conn)
            else:
                run_with_retry(args.job, conn)
        if args.scheduler:
            run_scheduler(conn)
        if not any([args.sync_areas, args.job, args.scheduler]):
            logger.info("실행할 작업이 없습니다. --help를 확인하세요.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
