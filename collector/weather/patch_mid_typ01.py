from pathlib import Path

target = Path("weather_collector_db.py")

text = target.read_text(encoding="utf-8")

if "import shlex" not in text:
    text = text.replace("import re\n", "import re\nimport shlex\n")

start = text.index("def collect_mid_land")
end = text.index("\nCOLLECTOR_BY_JOB", start)

replacement = r'''
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
'''

text = text[:start] + replacement + text[end:]

target.write_text(text, encoding="utf-8")

print("patch complete: collect_mid_land / collect_mid_temp replaced for typ01 APIHub")