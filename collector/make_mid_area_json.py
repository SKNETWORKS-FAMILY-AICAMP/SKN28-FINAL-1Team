"""중기예보 예보구역 코드 엑셀을 weather_collector_db.py용 JSON으로 변환한다.

사용 예:
  python make_mid_area_json.py \
    --xlsx data/중기예보_중기기온예보구역코드_2025.12.xlsx \
    --out-dir data
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

# APIHub 중기예보 개요에서 실제 중기 육상예보 지점으로 쓰는 10개 권역.
MID_LAND_CODE_ORDER = [
    "11B00000",  # 서울·인천·경기도
    "11D10000",  # 강원도영서
    "11D20000",  # 강원도영동
    "11C10000",  # 충청북도
    "11C20000",  # 대전·세종·충청남도
    "11F10000",  # 전북자치도
    "11F20000",  # 광주·전라남도
    "11H10000",  # 대구·경상북도
    "11H20000",  # 부산·울산·경상남도
    "11G00000",  # 제주도
]

MID_LAND_LABELS = {
    "11B00000": "서울·인천·경기도",
    "11D10000": "강원도영서",
    "11D20000": "강원도영동",
    "11C10000": "충청북도",
    "11C20000": "대전·세종·충청남도",
    "11F10000": "전북자치도",
    "11F20000": "광주·전라남도",
    "11H10000": "대구·경상북도",
    "11H20000": "부산·울산·경상남도",
    "11G00000": "제주도",
}


def clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def find_column(columns, candidates):
    cols = [str(c).strip() for c in columns]
    for candidate in candidates:
        if candidate in cols:
            return candidate
    for col in cols:
        for candidate in candidates:
            if candidate in col:
                return col
    raise KeyError(f"컬럼을 찾지 못했습니다. candidates={candidates}, columns={cols}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", required=True, help="중기예보 예보구역 코드 엑셀 경로")
    parser.add_argument("--out-dir", default="data", help="mid_land_areas.json / mid_temp_areas.json 저장 폴더")
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(xlsx_path)
    df.columns = [str(c).strip() for c in df.columns]

    code_col = find_column(df.columns, ["예보구역코드", "reg_id", "regId", "REG_ID"])
    name_col = find_column(df.columns, ["구역명", "지역명", "name", "REG_NAME"])
    type_col = find_column(df.columns, ["특성", "REG_SP", "area_type"])

    mid_land = []
    mid_temp = []

    for _, row in df.iterrows():
        code = clean(row.get(code_col))
        name = clean(row.get(name_col))
        feature = clean(row.get(type_col))
        if not code or not name or not feature:
            continue

        if feature == "A" and code in MID_LAND_CODE_ORDER:
            label = MID_LAND_LABELS.get(code, name)
            mid_land.append({
                "name": label,
                "reg_id": code,
                "address_label": label,
                "is_active": True,
            })
        elif feature == "C":
            mid_temp.append({
                "name": name,
                "reg_id": code,
                "address_label": name,
                "is_active": True,
            })

    order = {code: idx for idx, code in enumerate(MID_LAND_CODE_ORDER)}
    mid_land.sort(key=lambda item: order.get(item["reg_id"], 999))
    mid_temp.sort(key=lambda item: item["reg_id"])

    land_path = out_dir / "mid_land_areas.json"
    temp_path = out_dir / "mid_temp_areas.json"

    land_path.write_text(json.dumps(mid_land, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.write_text(json.dumps(mid_temp, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"saved: {land_path} ({len(mid_land)} rows)")
    print(f"saved: {temp_path} ({len(mid_temp)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
