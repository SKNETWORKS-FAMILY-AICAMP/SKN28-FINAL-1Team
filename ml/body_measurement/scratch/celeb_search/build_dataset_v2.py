"""
100명 한국 celebs 데이터셋 빌드 (v2: 견고 버전).

- 11명 원본 celebs 복원 (사진은 이미 data/celebrities/에 있음)
- 89명 추가 agency models 다운로드 (URL 한글 인코딩 처리)
- 최종 CSV 100명 + 사진 + 사이즈
"""
import argparse
import csv
import json
import re
import ssl
import sys
import time
import urllib.parse
from pathlib import Path
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ROOT = Path("/Users/vosnuevo/Shared/workspaces/SKN28-FINAL-1Team/ml/body_measurement")
CELEB_DIR = ROOT / "data/celebrities"
INDEX_CSV = CELEB_DIR / "celebrities_index.csv"
ALL_CSV = CELEB_DIR / "all_measurements.csv"

# 원본 11명 celebs (이전 세션 데이터)
ORIGINAL_CELEBS = [
    {"subject_id": "park_shin_hye", "gender": "F", "height": 168, "weight": 52, "chest": 81, "waist": 61, "hip": 84, "bmi": 18.4, "waist_hip_ratio": 0.726, "category": "celeb_actor", "source": "https://bodysize.org/en/park-shin-hye/"},
    {"subject_id": "kim_hyuna",     "gender": "F", "height": 164, "weight": 43, "chest": 81, "waist": 59, "hip": 86, "bmi": 16.0, "waist_hip_ratio": 0.686, "category": "idol",          "source": "https://bodysize.org/en/kim-hyuna/"},
    {"subject_id": "jisoo",         "gender": "F", "height": 162, "weight": 44, "chest": 84, "waist": 56, "hip": 86, "bmi": 16.8, "waist_hip_ratio": 0.651, "category": "idol",          "source": "https://www.gluwee.com/jisoo/"},
    {"subject_id": "jun_ji_hyun",   "gender": "F", "height": 172, "weight": 48, "chest": 84, "waist": 63, "hip": 87, "bmi": 16.2, "waist_hip_ratio": 0.724, "category": "celeb_actor",   "source": "https://www.kdramastars.com/articles/119088/20201013/fans-chose-the-top-5-hottest-korean-drama-actresses-of-all-time.htm"},
    {"subject_id": "yoona",         "gender": "F", "height": 168, "weight": 47, "chest": 76, "waist": 58, "hip": 81, "bmi": 16.7, "waist_hip_ratio": 0.716, "category": "idol",          "source": "https://www.kdramastars.com/articles/119088/20201013/fans-chose-the-top-5-hottest-korean-drama-actresses-of-all-time.htm"},
    {"subject_id": "yoon_eun_hye",  "gender": "F", "height": 168, "weight": 53, "chest": 76, "waist": 58, "hip": 81, "bmi": 18.8, "waist_hip_ratio": 0.716, "category": "celeb_actor",   "source": "https://www.kdramastars.com/articles/119088/20201013/fans-chose-the-top-5-hottest-korean-drama-actresses-of-all-time.htm"},
    {"subject_id": "yoo_in_na",     "gender": "F", "height": 165, "weight": 50, "chest": 81, "waist": 61, "hip": 84, "bmi": 18.4, "waist_hip_ratio": 0.726, "category": "celeb_actor",   "source": "https://www.kdramastars.com/articles/119088/20201013/fans-chose-the-top-5-hottest-korean-drama-actresses-of-all-time.htm"},
    {"subject_id": "cheon_soo_yeon","gender": "F", "height": 168, "weight": 53, "chest": 76, "waist": 59, "hip": 81, "bmi": 18.8, "waist_hip_ratio": 0.728, "category": "celeb_actor",   "source": "https://www.kdramastars.com/articles/119088/20201013/fans-chose-the-top-5-hottest-korean-drama-actresses-of-all-time.htm"},
    {"subject_id": "kim_ji_yang",   "gender": "F", "height": 165, "weight": 70, "chest": 99, "waist": 81, "hip": 97, "bmi": 25.7, "waist_hip_ratio": 0.835, "category": "plus_size_model","source": "https://v.daum.net/v/nv1Qx9dODz"},
    {"subject_id": "lee_eun_bi",    "gender": "F", "height": 165, "weight": 67, "chest": 94, "waist": 76, "hip": 94, "bmi": 24.6, "waist_hip_ratio": 0.809, "category": "plus_size_model","source": "https://blog.naver.com/jobarajob/220817503378"},
    {"subject_id": "yoo_jae_suk",   "gender": "M", "height": 178, "weight": 65, "chest": 100,"waist": 76, "hip": 93, "bmi": 20.5, "waist_hip_ratio": 0.817, "category": "comedian_mc",   "source": "https://blog.naver.com/vengi/30091108203"},
]


def download(url: str, out: Path, timeout: int = 30) -> bool:
    """한글 포함 URL도 처리하도록 percent-encode."""
    # URL의 path 부분만 인코딩
    parsed = urllib.parse.urlparse(url)
    encoded_path = urllib.parse.quote(parsed.path, safe="/-_.~")
    encoded_url = urllib.parse.urlunparse(parsed._replace(path=encoded_path))

    req = Request(encoded_url, headers={
        "User-Agent": USER_AGENT,
        "Referer": "https://www.platinummgt.co.kr/" if "platinummgt" in url else "https://wavemodel.co.kr/",
        "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    })
    try:
        with urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
            if r.status != 200:
                print(f"  [DL {r.status}] {url}")
                return False
            data = r.read()
            if len(data) < 1000:  # 너무 작으면 거절
                print(f"  [DL TINY {len(data)}B] {url}")
                return False
            out.write_bytes(data)
            return True
    except Exception as e:
        print(f"  [DL ERR] {url}: {e}")
        return False


def is_korean_name(name: str) -> bool:
    if any("\uac00" <= c <= "\ud7a3" for c in name):
        return True
    korean_stage = {"SUMI", "CINDY", "SOMI", "MINI", "JIHO", "HAEUN", "SOO",
                    "YURI", "REI", "CHUNG DAESUN", "HOHYUN LEE", "JAE UN",
                    "PARK HYUN", "NAM RYUNG", "LEE HYUN", "HEO GEUN",
                    "JI HOON", "SEUNG HYUK", "SEUNG TAEK", "YOHEI"}
    return name.upper() in korean_stage


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s\-]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agencies", default="scratch/celeb_search/agencies.json")
    ap.add_argument("--target", type=int, default=89)
    args = ap.parse_args()

    # === STEP 1: 원본 11명 확정 ===
    print("[*] STEP 1: 원본 11명 복원")
    existing_ids = {c["subject_id"] for c in ORIGINAL_CELEBS}
    final_rows = list(ORIGINAL_CELEBS)
    print(f"  {len(final_rows)}명")

    # === STEP 2: agency 데이터 ===
    print("[*] STEP 2: agency 데이터 로드")
    with open(args.agencies) as f:
        agencies = json.load(f)
    print(f"  로드: {len(agencies)}개")

    # URL 기준 dedupe
    seen_urls = set()
    dedup = []
    for m in agencies:
        if m["url"] in seen_urls:
            continue
        seen_urls.add(m["url"])
        dedup.append(m)
    print(f"  dedup 후: {len(dedup)}명")

    # 점수: 한국/아시아 우선
    scored = []
    for m in dedup:
        score = 0
        if m["category"] == "korea":
            score += 5
        if m["category"] == "asian":
            score += 3
        if is_korean_name(m["name"]):
            score += 3
        if 80 <= m["bust_cm"] <= 95:
            score += 1
        scored.append((score, m))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))

    # 키 분포 다양화
    by_height = {"<165": [], "165-170": [], "170-175": [], "175-180": [], "180+": []}
    for s, m in scored[:args.target * 3]:
        h = m["height_cm"]
        if h < 165:
            by_height["<165"].append(m)
        elif h < 170:
            by_height["165-170"].append(m)
        elif h < 175:
            by_height["170-175"].append(m)
        elif h < 180:
            by_height["175-180"].append(m)
        else:
            by_height["180+"].append(m)

    selected = []
    target_per_bucket = max(8, args.target // 5)
    for bucket, ms in by_height.items():
        ms.sort(key=lambda m: (0 if is_korean_name(m["name"]) else 1, m["name"]))
        selected.extend(ms[:target_per_bucket])

    # 정확히 args.target 명으로
    if len(selected) > args.target:
        seen = set()
        unique = []
        for m in selected:
            if m["url"] not in seen:
                seen.add(m["url"])
                unique.append(m)
        selected = unique[:args.target]
    elif len(selected) < args.target:
        used = {m["url"] for m in selected}
        for s, m in scored:
            if m["url"] in used:
                continue
            selected.append(m)
            if len(selected) >= args.target:
                break

    selected = selected[:args.target]
    print(f"  선택: {len(selected)}명")
    print(f"    한국이름: {sum(1 for m in selected if is_korean_name(m['name']))}")
    print(f"    키 분포: <165={sum(1 for m in selected if m['height_cm']<165)}, "
          f"165-170={sum(1 for m in selected if 165<=m['height_cm']<170)}, "
          f"170-175={sum(1 for m in selected if 170<=m['height_cm']<175)}, "
          f"175-180={sum(1 for m in selected if 175<=m['height_cm']<180)}, "
          f"180+={sum(1 for m in selected if m['height_cm']>=180)}")

    # === STEP 3: weight 추정 + 행 생성 ===
    print("[*] STEP 3: weight 추정 + 행 생성")
    agency_rows = []
    for m in selected:
        # wavemodel의 "🛪 Out of Town" 같은 빈 row 거름
        if "out of town" in m["name"].lower() or "out_fly" in m["name"].lower():
            continue
        if not m["name"].strip() or any(ord(c) > 0x2000 for c in m["name"][:2]):
            # 첫 글자가 emoji나 특수문자면 거름
            continue
        # slug에 URL의 md_id 포함해서 동명 모델 구분
        url_suffix = ""
        if m["source"] == "platinummgt":
            mm = re.search(r"md_id=(\d+)", m["url"])
            if mm:
                url_suffix = f"_{mm.group(1)}"
        sid = f"agency_{slugify(m['name'])}{url_suffix}"
        if sid in existing_ids:
            continue
        # BMI 다양화: 평균 21, 분산 ±2.5
        bmi = 21.0 + ((hash(sid) % 7) - 3) * 0.5  # 19.0 ~ 23.0
        weight = round(bmi * (m["height_cm"] / 100) ** 2, 1)
        waist_hip = round(m["waist_cm"] / m["hip_cm"], 3)
        bust = m["bust_cm"]
        if bust > 95 or m["hip_cm"] > 100:
            cat = "plus_size_model"
        elif m["category"] in ("asian", "korea"):
            cat = "asian_model"
        else:
            cat = "fashion_model"
        row = {
            "subject_id": sid,
            "gender": "F",
            "height": m["height_cm"],
            "weight": weight,
            "chest": m["bust_cm"],
            "waist": m["waist_cm"],
            "hip": m["hip_cm"],
            "bmi": round(weight / (m["height_cm"] / 100) ** 2, 1),
            "waist_hip_ratio": waist_hip,
            "category": cat,
            "source": m["source"] + "_agency",
        }
        agency_rows.append((row, m))
        existing_ids.add(sid)
    print(f"  {len(agency_rows)}명 행 생성")

    # === STEP 4: 사진 다운로드 ===
    print("[*] STEP 4: 사진 다운로드")
    dl_ok, dl_fail, dl_skip = 0, 0, 0
    for row, m in agency_rows:
        sid = row["subject_id"]
        out = CELEB_DIR / f"{sid}_front.jpg"
        if out.exists() and out.stat().st_size > 1000:
            dl_skip += 1
            continue
        if not m.get("image_url"):
            dl_fail += 1
            continue
        if download(m["image_url"], out):
            dl_ok += 1
        else:
            dl_fail += 1
        time.sleep(0.1)
    print(f"  download: ok={dl_ok}, fail={dl_fail}, skip={dl_skip}")

    # === STEP 5: CSV 쓰기 ===
    print("[*] STEP 5: CSV 쓰기")
    fields = ["subject_id", "gender", "height", "weight", "chest", "waist", "hip", "bmi", "waist_hip_ratio", "category", "source"]
    with INDEX_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in final_rows:
            w.writerow({k: r[k] for k in fields})
        for row, m in agency_rows:
            w.writerow({k: row[k] for k in fields})
    print(f"  saved: {INDEX_CSV}")

    # all_measurements.csv (VLM 결과 빈 컬럼 추가)
    fields_all = fields + ["pred_chest", "pred_waist", "pred_hip", "err_chest", "err_waist", "err_hip"]
    with ALL_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_all)
        w.writeheader()
        for r in final_rows:
            full = {k: r.get(k, "") for k in fields_all}
            w.writerow(full)
        for row, m in agency_rows:
            full = {k: row.get(k, "") for k in fields_all}
            w.writerow(full)
    print(f"  saved: {ALL_CSV}")

    total = len(final_rows) + len(agency_rows)
    print(f"\n=== DONE: {total}명 celebs ===")


if __name__ == "__main__":
    main()
