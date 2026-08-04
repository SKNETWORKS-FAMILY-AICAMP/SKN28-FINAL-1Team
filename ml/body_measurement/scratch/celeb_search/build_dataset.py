"""
agency candidates에서 한국 여성 89명(+유재석 포함 90) 선별,
front 사진 다운로드, 사이즈 데이터 → celebrities 데이터셋 통합.

Strategy:
  1) agency 데이터 로드
  2) URL 기준 dedupe
  3) 한국 이름 / 한국어 tab 우선
  4) BMI 다양성 확보 (slim / normal / plus)
  5) N명 골라 front 사진 download
  6) 사이즈 → cm 정리 + weight 추정 (BMI 22 기준)
  7) celebrities_index.csv 와 머지
  8) all_measurements.csv 에 빈 pred 컬럼 추가
"""
import argparse
import csv
import json
import random
import re
import ssl
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ROOT = Path("/Users/vosnuevo/Shared/workspaces/SKN28-FINAL-1Team/ml/body_measurement")
CELEB_DIR = ROOT / "data/celebrities"
CELEB_DIR.mkdir(parents=True, exist_ok=True)
INDEX_CSV = CELEB_DIR / "celebrities_index.csv"
ALL_CSV = CELEB_DIR / "all_measurements.csv"


def download(url: str, out: Path, timeout: int = 30) -> bool:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://wavemodel.co.kr/"})
    try:
        with urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
            if r.status != 200:
                return False
            data = r.read()
            out.write_bytes(data)
            return True
    except Exception as e:
        print(f"  [DL ERR] {url}: {e}")
        return False


def is_korean_name(name: str) -> bool:
    """한글이 포함된 이름, 또는 흔한 한국 식 영문명 (e.g. Sumi, Cindy)"""
    if any("\uac00" <= c <= "\ud7a3" for c in name):
        return True
    # 한국어 tab에 있었던 이름들 패턴 (영문명 + 한국 성씨 패턴)
    korean_stage_names = {"SUMI", "CINDY", "SOMI", "MINI", "JIHO", "HAEUN", "SOO",
                          "YURI", "REI", "CHUNG DAESUN", "HOHYUN LEE"}
    if name.upper() in korean_stage_names:
        return True
    return False


def is_english_name(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z\s\-\.]+$", name))


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s\-]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agencies", default="scratch/celeb_search/agencies.json")
    ap.add_argument("--target", type=int, default=89, help="추가할 인원")
    ap.add_argument("--existing", type=int, default=11, help="기존 celebs 수")
    args = ap.parse_args()

    # 기존 celebrities_index.csv 로드
    existing = []
    if INDEX_CSV.exists():
        with INDEX_CSV.open() as f:
            existing = list(csv.DictReader(f))
    existing_ids = {row["subject_id"] for row in existing}
    print(f"기존 celebs: {len(existing)}명")

    # agency 데이터 로드
    with open(args.agencies) as f:
        agencies = json.load(f)
    print(f"agency candidates: {len(agencies)}명")

    # URL 기준 dedupe
    seen_urls = set()
    dedup = []
    for m in agencies:
        if m["url"] in seen_urls:
            continue
        seen_urls.add(m["url"])
        dedup.append(m)
    print(f"dedup 후: {len(dedup)}명")

    # 한국 이름 우선, 한국어 카테고리 우선
    # 점수: 한국 이름 +2, korea 카테고리 +3, asian 카테고리 +1, foreign women +0
    scored = []
    for m in dedup:
        score = 0
        if m["category"] == "korea":
            score += 5
        if m["category"] == "asian":
            score += 3
        if is_korean_name(m["name"]):
            score += 3
        if is_english_name(m["name"]):
            score += 0
        # 가슴 둘레로 plus/slim 구분 (한국 성인 여성 보통 76-90)
        bust = m["bust_cm"]
        if 80 <= bust <= 95:
            score += 1  # 일반 사이즈
        elif bust > 95:
            score += 0.5  # plus
        elif bust < 78:
            score += 0.5  # slim
        scored.append((score, m))
    scored.sort(key=lambda x: (-x[0], x[1]["name"]))

    # 우선 상위 N개
    top = [m for _, m in scored[:args.target * 2]]  # 여유분
    print(f"상위 후보: {len(top)}명")

    # 다양성: BMI 분포 조정
    # 키 165, 가슴 80-95가 많으니 골고루 뽑기
    # 우선 키 다양화: < 165, 165-170, 170-175, 175-180, 180+ 로 분할 후 균등
    by_height = {"<165": [], "165-170": [], "170-175": [], "175-180": [], "180+": []}
    for m in top:
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
    # 각 키대에서 1-2명씩, 우선 Korean 이름
    for bucket, ms in by_height.items():
        # Korean 이름 우선 정렬
        ms.sort(key=lambda m: (0 if is_korean_name(m["name"]) else 1, m["name"]))
        # 버킷에서 1/4만 가져오기
        take = max(2, args.target // 5)
        selected.extend(ms[:take])

    # 89명 맞추기
    if len(selected) > args.target:
        # 점수순 재정렬
        selected_with_score = [(s, m) for s, m in scored if m in selected]
        selected_with_score.sort(key=lambda x: -x[0])
        selected = [m for _, m in selected_with_score[:args.target]]
    elif len(selected) < args.target:
        # 부족하면 보충
        used_urls = {m["url"] for m in selected}
        for s, m in scored:
            if m["url"] in used_urls:
                continue
            selected.append(m)
            if len(selected) >= args.target:
                break

    selected = selected[:args.target]
    print(f"최종 선택: {len(selected)}명")
    print(f"  한국 이름: {sum(1 for m in selected if is_korean_name(m['name']))}")
    print(f"  키 분포: " + ", ".join(f"{b}={sum(1 for m in selected if m['height_cm'] < (165 if b=='<165' else 170 if b=='165-170' else 175 if b=='170-175' else 180 if b=='175-180' else 999)) and m['height_cm'] >= (0 if b=='<165' else 165 if b=='165-170' else 170 if b=='170-175' else 175 if b=='175-180' else 180)}" for b in by_height))

    # 사이즈 → cm 정규화, weight 추정
    new_rows = []
    for m in selected:
        sid = f"agency_{slugify(m['name'])}"
        if sid in existing_ids:
            continue
        # weight 추정: 한국 여성 BMI 평균 22, 키 다양화 위해 약간 변동
        # bust와 hip의 함수로 weight 추정 (SizeKorea 통계 기반)
        # 단순화: BMI = 20 + (bust - 78) * 0.2 + (hip - 88) * 0.1
        # 또는 그냥 BMI 22 고정
        bmi = 21.0  # 한국 모델 평균
        weight = round(bmi * (m["height_cm"] / 100) ** 2, 1)
        waist_hip = round(m["waist_cm"] / m["hip_cm"], 3)
        # category
        bust = m["bust_cm"]
        if bust > 95 or m["hip_cm"] > 100:
            cat = "plus_size_model"
        elif m["source"] == "wavemodel" or (m["category"] in ("asian", "korea")):
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
        new_rows.append((row, m))
        existing_ids.add(sid)

    # 사진 다운로드
    print(f"\n[*] {len(new_rows)}명 사진 다운로드 시작...")
    dl_ok, dl_fail = 0, 0
    for row, m in new_rows:
        sid = row["subject_id"]
        img_url = m["image_url"]
        if not img_url:
            dl_fail += 1
            continue
        out = CELEB_DIR / f"{sid}_front.jpg"
        if out.exists():
            dl_ok += 1
            continue
        if download(img_url, out):
            dl_ok += 1
        else:
            dl_fail += 1
        time.sleep(0.1)
    print(f"  download ok: {dl_ok}, fail: {dl_fail}")

    # CSV 머지
    with INDEX_CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subject_id", "gender", "height", "weight", "chest", "waist", "hip", "bmi", "waist_hip_ratio", "category", "source"])
        # 헤더는 이미 있으면 안 쓰기
        for row, m in new_rows:
            w.writerow(row)

    # all_measurements.csv 갱신 (기존 + 새 행, pred 컬럼 빈 값)
    if ALL_CSV.exists():
        with ALL_CSV.open() as f:
            old_rows = list(csv.DictReader(f))
    else:
        old_rows = []
    old_ids = {r["subject_id"] for r in old_rows}
    fields = ["subject_id", "gender", "height", "weight", "chest", "waist", "hip", "bmi", "waist_hip_ratio", "category", "source",
              "pred_chest", "pred_waist", "pred_hip", "err_chest", "err_waist", "err_hip"]
    with ALL_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        # 기존 행
        for r in old_rows:
            full = {k: r.get(k, "") for k in fields}
            w.writerow(full)
        # 새 행
        for row, m in new_rows:
            full = {k: row.get(k, "") for k in fields}
            w.writerow(full)
    print(f"  updated {INDEX_CSV}, {ALL_CSV}")
    print(f"\nDone. Total celebs: {len(existing) + len(new_rows)}명")


if __name__ == "__main__":
    main()
