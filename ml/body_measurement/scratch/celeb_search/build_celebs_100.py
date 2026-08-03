"""
한국 연예인 100명 bodysize.org 일괄 fetcher.

각 후보에 대해:
  1) bodysize 페이지 파싱 → H/W/C/W/H
  2) large-photo URL 추출 (전신 사진)
  3) portrait URL 추출 (얼굴/측면 참고용)
  4) 사진 다운로드 + 사이즈 CSV 갱신

Usage:
    python3 build_celebs_100.py
"""
import argparse
import csv
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ROOT = Path("/Users/vosnuevo/Shared/workspaces/SKN28-FINAL-1Team/ml/body_measurement")
CELEB_DIR = ROOT / "data/celebrities"
INDEX_CSV = CELEB_DIR / "celebrities_index.csv"
ALL_CSV = CELEB_DIR / "all_measurements.csv"

# 원본 11명 (front+side 이미 있음)
ORIGINAL_CELEBS = [
    {"subject_id": "park_shin_hye", "gender": "F", "height": 168, "weight": 52, "chest": 81, "waist": 61, "hip": 84, "bmi": 18.4, "waist_hip_ratio": 0.726, "category": "celeb_actor", "source": "https://bodysize.org/en/park-shin-hye/", "front_img": "https://bodysize.org/wp-content/uploads/2018/05/Park-Shin-hye-426x640.jpg"},
    {"subject_id": "kim_hyuna",     "gender": "F", "height": 164, "weight": 43, "chest": 81, "waist": 59, "hip": 86, "bmi": 16.0, "waist_hip_ratio": 0.686, "category": "idol",          "source": "https://bodysize.org/en/kim-hyuna/"},
    {"subject_id": "jisoo",         "gender": "F", "height": 162, "weight": 44, "chest": 84, "waist": 56, "hip": 86, "bmi": 16.8, "waist_hip_ratio": 0.651, "category": "idol",          "source": "https://www.gluwee.com/jisoo/"},
    {"subject_id": "jun_ji_hyun",   "gender": "F", "height": 172, "weight": 48, "chest": 84, "waist": 63, "hip": 87, "bmi": 16.2, "waist_hip_ratio": 0.724, "category": "celeb_actor",   "source": "https://bodysize.org/en/jun-ji-hyun/"},
    {"subject_id": "yoona",         "gender": "F", "height": 168, "weight": 47, "chest": 76, "waist": 58, "hip": 81, "bmi": 16.7, "waist_hip_ratio": 0.716, "category": "idol",          "source": "https://bodysize.org/en/yoona/"},
    {"subject_id": "yoon_eun_hye",  "gender": "F", "height": 168, "weight": 53, "chest": 76, "waist": 58, "hip": 81, "bmi": 18.8, "waist_hip_ratio": 0.716, "category": "celeb_actor",   "source": "https://bodysize.org/en/yoon-eun-hye/"},
    {"subject_id": "yoo_in_na",     "gender": "F", "height": 165, "weight": 50, "chest": 81, "waist": 61, "hip": 84, "bmi": 18.4, "waist_hip_ratio": 0.726, "category": "celeb_actor",   "source": "https://bodysize.org/en/yoo-in-na/"},
    {"subject_id": "cheon_soo_yeon","gender": "F", "height": 168, "weight": 53, "chest": 76, "waist": 59, "hip": 81, "bmi": 18.8, "waist_hip_ratio": 0.728, "category": "celeb_actor",   "source": "https://bodysize.org/en/song-ji-hyo/", "alias": "song_ji_hyo"},
    {"subject_id": "kim_ji_yang",   "gender": "F", "height": 165, "weight": 70, "chest": 99, "waist": 81, "hip": 97, "bmi": 25.7, "waist_hip_ratio": 0.835, "category": "plus_size_model","source": "https://v.daum.net/v/nv1Qx9dODz"},
    {"subject_id": "lee_eun_bi",    "gender": "F", "height": 165, "weight": 67, "chest": 94, "waist": 76, "hip": 94, "bmi": 24.6, "waist_hip_ratio": 0.809, "category": "plus_size_model","source": "https://blog.naver.com/jobarajob/220817503378"},
    {"subject_id": "yoo_jae_suk",   "gender": "M", "height": 178, "weight": 65, "chest": 100,"waist": 76, "hip": 93, "bmi": 20.5, "waist_hip_ratio": 0.817, "category": "comedian_mc",   "source": "https://bodysize.org/en/yoo-jae-suk/"},
]

# 한국 연예인 200+ 후보 (slim/medium/plus 다 포함)
# 형식: ([slugs...], display_name, category, gender)
# 각 이름마다 여러 슬러그를 시도해서 하나라도 작동하면 사용
KOREAN_CELEBS = [
    # === 슬림 아이돌/배우 (BMI 16-20) ===
    (["iu", "lee-ji-eun"], "IU", "idol", "F"),
    (["suzy", "miss-a-suzy", "suzy-bae"], "Suzy", "idol", "F"),
    (["jisoo", "blackpink-jisoo", "kim-jisoo"], "Jisoo", "idol", "F"),
    (["lisa", "lalisa", "lisa-manoban"], "Lisa", "idol", "F"),
    (["rose", "rose-blackpink", "roseanne-park"], "Rosé", "idol", "F"),
    (["jennie", "jennie-kim", "jennie-ruby-jane"], "Jennie", "idol", "F"),
    (["taeyeon", "kim-taeyeon", "girls-generation-taeyeon"], "Taeyeon", "idol", "F"),
    (["jessica-jung", "jessica", "jessica-snl"], "Jessica", "idol", "F"),
    (["kwon-yuri", "yuri-snsd", "yuri-kwon"], "Kwon Yuri", "idol", "F"),
    (["hyoyeon", "hyo-yeon", "hyoyeon-snsd"], "Hyoyeon", "idol", "F"),
    (["seohyun", "seo-hyun", "seohyun-snsd"], "Seohyun", "idol", "F"),
    (["sunny", "lee-sunny", "sunny-snsd"], "Sunny", "idol", "F"),
    (["tiffany", "tiffany-young", "tiffany-hwang"], "Tiffany", "idol", "F"),
    (["soyou", "kang-soyou"], "Soyou", "idol", "F"),
    (["hyolyn", "hyorin", "hyolyn-system"], "Hyorin", "idol", "F"),
    (["hwasa", "ahn-hwasa", "mamamoo-hwasa"], "Hwasa", "idol", "F"),
    (["moonbyul", "moon-byul-yi"], "Moonbyul", "idol", "F"),
    (["wheein", "whee-in", "jung-wheein"], "Wheein", "idol", "F"),
    (["cl", "lee-cl", "chl-ee"], "CL", "idol", "F"),
    (["somi", "jeon-somi", "somi-jeon"], "Jeon Somi", "idol", "F"),
    (["nayeon", "im-nayeon"], "Nayeon", "idol", "F"),
    (["dahyun", "kim-dahyun"], "Dahyun", "idol", "F"),
    (["chaeyoung", "son-chaeyoung"], "Chaeyoung", "idol", "F"),
    (["tzuyu", "choi-tzuyu"], "Tzuyu", "idol", "F"),
    (["jihyo", "park-jihyo"], "Jihyo", "idol", "F"),
    (["lia", "lalisa-manoban-no-lia-itzy-lia"], "Lia", "idol", "F"),
    (["yeji", "yeji-itzy"], "Yeji", "idol", "F"),
    (["ryujin", "ryujin-itzy"], "Ryujin", "idol", "F"),
    (["winter", "winter-aespa", "kim-minjeong"], "Winter", "idol", "F"),
    (["karina", "karina-aespa", "karina-yoo"], "Karina", "idol", "F"),
    (["irene", "irene-red-velvet", "bae-joohyun"], "Irene", "idol", "F"),
    (["wendy", "wendy-red-velvet", "son-seungwan"], "Wendy", "idol", "F"),
    (["joy", "joy-red-velvet", "park-sooyoung"], "Joy", "idol", "F"),
    (["miyeon", "miyeon-g-idle"], "Miyeon", "idol", "F"),
    (["hye-su-kim", "kim-hye-soo", "hye-su-kim"], "Kim Hye-soo", "celeb_actor", "F"),
    (["song-hye-kyo", "song-hye-kyo-actress"], "Song Hye-kyo", "celeb_actor", "F"),
    (["lee-sung-kyung", "leeseungkyung"], "Lee Sung-kyung", "celeb_actor", "F"),
    (["han-hyo-joo", "han-hyojoo", "hyo-joo"], "Han Hyo-joo", "celeb_actor", "F"),
    (["park-min-young", "park-minyoung"], "Park Min-young", "celeb_actor", "F"),
    (["kim-go-eun", "kim-goeun"], "Kim Go-eun", "celeb_actor", "F"),
    (["kim-yoo-jung", "kim-yoojung"], "Kim Yoo-jung", "celeb_actor", "F"),
    (["moon-ga-young", "moon-gayoung"], "Moon Ga-young", "celeb_actor", "F"),
    (["chae-soo-bin", "chae-soobin", "bae-soo-bin"], "Chae Soo-bin", "celeb_actor", "F"),
    (["park-bo-young", "park-boyoung"], "Park Bo-young", "celeb_actor", "F"),
    (["yoo-in-na", "yoo-inna"], "Yoo In-na", "celeb_actor", "F"),
    (["shin-hye-sun", "shin-hyesun"], "Shin Hye-sun", "celeb_actor", "F"),
    (["go-ara", "goara", "ara-go"], "Go Ara", "celeb_actor", "F"),
    (["seo-ye-ji", "seo-yeji"], "Seo Ye-ji", "celeb_actor", "F"),
    (["han-hye-jin", "han-hyejin"], "Han Hye-jin", "celeb_actor", "F"),
    (["yoon-eun-hye", "yoon-eunhye", "eun-hye-yoon"], "Yoon Eun-hye", "celeb_actor", "F"),
    (["lee-min-jung", "lee-minjung"], "Lee Min-jung", "celeb_actor", "F"),
    (["moon-chae-won", "moon-chaewon"], "Moon Chae-won", "celeb_actor", "F"),
    (["shin-min-a", "shin-mina", "min-a-shin"], "Shin Min-a", "celeb_actor", "F"),
    (["han-ji-min", "han-jimin", "jimin-han"], "Han Ji-min", "celeb_actor", "F"),
    (["gong-hyo-jin", "gong-hyojin", "hyo-jin-gong"], "Gong Hyo-jin", "celeb_actor", "F"),
    (["oh-in-hye", "oh-inhye"], "Oh In-hye", "celeb_actor", "F"),
    (["kim-sae-ron", "kim-saeron", "sae-ron"], "Kim Sae-ron", "celeb_actor", "F"),
    (["yunjin-kim", "yunjin-kim", "yoon-jin-kim"], "Yunjin Kim", "celeb_actor", "F"),
    (["park-ji-yeon", "park-jiyeon"], "Park Ji-yeon", "celeb_actor", "F"),
    (["kim-tae-hee", "kim-taehee", "tae-hee"], "Kim Tae-hee", "celeb_actor", "F"),
    (["gong-ji-cheol", "gong-jicheol", "gong-ji-chul"], "Gong Ji-cheol", "celeb_actor", "M"),
    (["jo-in-sung", "jo-insung"], "Jo In-sung", "celeb_actor", "M"),
    (["lee-byung-hun", "lee-byunghun"], "Lee Byung-hun", "celeb_actor", "M"),
    (["so-ji-sub", "so-jisub"], "So Ji-sub", "celeb_actor", "M"),
    (["kim-soo-hyun", "kim-soohyun"], "Kim Soo-hyun", "celeb_actor", "M"),
    (["hyun-bin", "hyunbin"], "Hyun Bin", "celeb_actor", "M"),
    (["won-bin", "wonbin"], "Won Bin", "celeb_actor", "M"),
    (["lee-min-ho", "lee-minho"], "Lee Min-ho", "celeb_actor", "M"),
    (["song-joong-ki", "song-joongki"], "Song Joong-ki", "celeb_actor", "M"),
    (["park-seo-joon", "park-seojoon"], "Park Seo-joon", "celeb_actor", "M"),
    (["yoo-jae-suk", "yoo-jaesuk"], "Yoo Jae-suk", "comedian_mc", "M"),
    (["kang-ho-dong", "kanghodong"], "Kang Ho-dong", "comedian_mc", "M"),
    (["lee-kwang-soo", "lee-kwangsoo"], "Lee Kwang-soo", "celeb_actor", "M"),
    (["rain", "rain-jung"], "Rain", "idol", "M"),
    (["song-ji-hyo", "song-jihyo"], "Song Ji-hyo", "celeb_actor", "F"),
    (["kim-jong-kook", "kim-jongkook"], "Kim Jong-kook", "idol", "M"),
    (["haha", "ha-ha", "haha-singer"], "Haha", "comedian_mc", "M"),
    (["ji-suk-jin", "ji-sukjin"], "Ji Suk-jin", "comedian_mc", "M"),
    (["lee-kyung-kyu", "lee-kyungkyu"], "Lee Kyung-kyu", "comedian_mc", "M"),
    (["park-myeong-su", "park-myeongsu"], "Park Myeong-su", "comedian_mc", "M"),
    (["shin-dong-yup", "shin-dongyup"], "Shin Dong-yup", "comedian_mc", "M"),
    (["jun-hyun-moo", "jun-hyunmoo"], "Jun Hyun-moo", "comedian_mc", "M"),
    (["yang-se-hyung", "yang-sehyung"], "Yang Se-hyung", "comedian_mc", "M"),
    # === Plus size / 다양성 ===
    (["kim-ji-yang", "kim-jiyang"], "Kim Ji-yang", "plus_size_model", "F"),
    (["lee-eun-bi", "lee-eunbi"], "Lee Eun-bi", "plus_size_model", "F"),
    # === 일반 배우 추가 ===
    (["han-ji-hye", "han-jihye"], "Han Ji-hye", "celeb_actor", "F"),
    (["o-yeon-ah", "oh-yeonah", "yeonah"], "Oh Yeon-ah", "celeb_actor", "F"),
    (["lee-young-ae", "lee-youngae"], "Lee Young-ae", "celeb_actor", "F"),
    (["jeon-ji-hyun", "jeon-jihyun"], "Jun Ji-hyun", "celeb_actor", "F"),
    (["cho-yoon-hee", "cho-yoonhee"], "Cho Yoon-hee", "celeb_actor", "F"),
    (["seol-in-ah", "seol-inah", "seol-in-ah"], "Seol In-ah", "celeb_actor", "F"),
    (["yoon-chae-na", "yoon-chaena"], "Yoon Chae-na", "celeb_actor", "F"),
    (["kim-yoo-jin", "kim-yoojin"], "Kim Yoo-jin", "celeb_actor", "F"),
    (["im-young-ah", "lim-youngah"], "Im Young-ah", "celeb_actor", "F"),
    # 추가 K-pop
    (["minzy", "minzy-2ne1"], "Minzy", "idol", "F"),
    (["bora", "bora-sistar"], "Bora", "idol", "F"),
    (["hani", "hani-exid", "ahn-hee-yeon"], "Hani", "idol", "F"),
    (["solji", "solji-exid"], "Solji", "idol", "F"),
    (["le", "le-exid"], "LE", "idol", "F"),
    (["hyuna", "hyuna-4minute", "kim-hyuna"], "Hyuna", "idol", "F"),
    (["jiyoon", "jiyoon-4minute"], "Jiyoon", "idol", "F"),
    (["sohyun", "sohyun-4minute"], "Sohyun", "idol", "F"),
    (["gayoon", "gayoon-2ne1"], "Gayoon", "idol", "F"),
    (["park-sandara", "sandara-park", "dara"], "Sandara Park", "idol", "F"),
    (["momo", "momo-twice"], "Momo", "idol", "F"),
    (["sana", "sana-twice"], "Sana", "idol", "F"),
    (["mina", "mina-twice"], "Mina", "idol", "F"),
    (["jeongyeon", "jeongyeon-twice"], "Jeongyeon", "idol", "F"),
    (["chaeryeong", "chaeryeong-itzy"], "Chaeryeong", "idol", "F"),
    (["yuna", "yuna-itzy"], "Yuna", "idol", "F"),
    (["seulgi", "seulgi-red-velvet"], "Seulgi", "idol", "F"),
    (["yeri", "yeri-red-velvet"], "Yeri", "idol", "F"),
    (["giselle", "giselle-aespa"], "Giselle", "idol", "F"),
    (["ningning", "ningning-aespa"], "NingNing", "idol", "F"),
    (["yuqi", "yuqi-gidle"], "Yuqi", "idol", "F"),
    (["shuhua", "shuhua-gidle"], "Shuhua", "idol", "F"),
    (["minnie", "minnie-gidle"], "Minnie", "idol", "F"),
    (["soyoon", "soyoon-gidle"], "Soyeon", "idol", "F"),
    (["haewon", "haewon-nmixx"], "Haewon", "idol", "F"),
    (["lily", "lily-nmixx"], "Lily", "idol", "F"),
    (["wonyoung", "jang-wonyoung", "wonyoung-ive"], "Wonyoung", "idol", "F"),
    (["yujin-ive", "ahn-yujin"], "Ahn Yujin", "idol", "F"),
    (["rei", "rei-ive"], "Rei", "idol", "F"),
    (["gaeul", "gaeul-ive"], "Gaeul", "idol", "F"),
    (["liz", "liz-ive"], "Liz", "idol", "F"),
    (["leeseo", "leeseo-ive"], "Leeseo", "idol", "F"),
    (["kazuha", "kazuha-le-sserafim"], "Kazuha", "idol", "F"),
    (["sakura", "sakura-le-sserafim"], "Sakura", "idol", "F"),
    (["yunjin", "yunjin-le-sserafim"], "Yunjin", "idol", "F"),
    (["chaewon", "chaewon-le-sserafim"], "Chaewon", "idol", "F"),
    (["eunchae", "eunchae-le-sserafim"], "Eunchae", "idol", "F"),
]


def fetch(url: str, timeout: int = 20) -> str:
    encoded = urllib.parse.quote(url, safe=':/?=&-_.~')
    req = urllib.request.Request(encoded, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
            if r.status != 200:
                return ""
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


# bodysize.org 페이지 파싱
def parse_bodysize(html: str, slug: str) -> dict:
    """키/몸무게/가슴/허리/엉덩이 + 이미지 URL 추출."""
    out = {"slug": slug, "url": f"https://bodysize.org/en/{slug}/"}

    # H/W
    m = re.search(r"Height[^<]*<td>\s*(\d+)\s*ft\s*(\d+)\s*in\s*/\s*(\d+)\s*cm", html)
    if not m:
        m = re.search(r"Height</th>\s*<td>([^<]+)</td>", html)
    if m:
        if len(m.groups()) >= 3 and m.group(3):
            out["height_cm"] = int(m.group(3))
        else:
            cm = re.search(r"(\d+)\s*cm", m.group(1))
            if cm:
                out["height_cm"] = int(cm.group(1))

    m = re.search(r"Weight[^<]*<td>\s*(\d+)\s*lb\s*/\s*(\d+)\s*kg", html)
    if not m:
        m = re.search(r"Weight</th>\s*<td>([^<]+)</td>", html)
    if m:
        if len(m.groups()) >= 2 and m.group(2):
            out["weight_kg"] = int(m.group(2))
        else:
            kg = re.search(r"(\d+)\s*kg", m.group(1))
            if kg:
                out["weight_kg"] = int(kg.group(1))

    # C/W/H
    for label, key in [("Breast/Bust size", "bust_cm"),
                       ("Waist size", "waist_cm"),
                       ("Hips size", "hip_cm")]:
        m = re.search(rf"{re.escape(label)}</th>\s*<td>([^<]+)</td>", html)
        if m:
            cm = re.search(r"(\d+)\s*cm", m.group(1))
            if cm:
                out[key] = int(cm.group(1))

    # portrait image (얼굴)
    portrait_m = re.search(r'<div class="portrait">\s*<img[^>]+src="([^"]+)"', html)
    if portrait_m:
        out["portrait_img"] = portrait_m.group(1)

    # large-photo (전신)
    large_m = re.search(r'<div class="large-photo">.*?data-src="([^"]+)"', html, re.DOTALL)
    if not large_m:
        large_m = re.search(r'<div class="large-photo">.*?srcset="([^"]+)"', html, re.DOTALL)
    if large_m:
        out["large_img"] = large_m.group(1)

    return out


def download(url: str, out: Path, timeout: int = 30) -> bool:
    if not url:
        return False
    if out.exists() and out.stat().st_size > 1000:
        return True
    # 상대 URL을 절대 URL로 변환
    if url.startswith("/"):
        url = "https://bodysize.org" + url
    encoded = urllib.parse.quote(url, safe=':/?=&-_.~')
    req = urllib.request.Request(encoded, headers={"User-Agent": USER_AGENT, "Referer": "https://bodysize.org/"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
            if r.status != 200:
                return False
            data = r.read()
            if len(data) < 1000:
                return False
            out.write_bytes(data)
            return True
    except Exception:
        return False


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s\-]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s


def main():
    # === STEP 1: 원본 11명 확정 ===
    final_rows = list(ORIGINAL_CELEBS)
    existing_ids = {c["subject_id"] for c in final_rows}
    print(f"[1] 원본 11명 확정: {len(final_rows)}명")

    # === STEP 2: bodysize.org에서 후보 100+명 fetch ===
    print(f"[2] bodysize.org 일괄 fetch: {len(KOREAN_CELEBS)}명 후보 (각각 여러 slug 시도)")
    # 각 이름별로 모든 slug 시도해서 작동하는 것만 채택
    tasks = []  # (url, name, cat, gen, slug)
    for slugs, name, cat, gen in KOREAN_CELEBS:
        for slug in slugs:
            tasks.append((f"https://bodysize.org/en/{slug}/", name, cat, gen, slug))

    parsed_by_name = {}  # name → (cat, gen, parsed_data, slug_used)
    with ThreadPoolExecutor(max_workers=8) as ex:
        future_map = {ex.submit(fetch, url): (url, name, cat, gen, slug)
                      for url, name, cat, gen, slug in tasks}
        for fut in as_completed(future_map):
            url, name, cat, gen, slug = future_map[fut]
            html = fut.result()
            if not html:
                continue
            data = parse_bodysize(html, slug)
            if not all(k in data for k in ("height_cm", "weight_kg", "bust_cm", "waist_cm", "hip_cm")):
                continue
            if name in parsed_by_name:
                continue  # 이미 성공한 slug 있음
            data["display_name"] = name
            data["category"] = cat
            data["gender"] = gen
            parsed_by_name[name] = data
    parsed = list(parsed_by_name.values())
    print(f"  파싱 성공: {len(parsed)}명 (중복 제거 후)")
    print(f"  키 분포: " + ", ".join(f"h={c.get('height_cm','?')}" for c in parsed[:5]))

    # === STEP 3: 89명 선정 (다양성) ===
    # 11원본 + 89 = 100
    target = 89
    # 1) 카테고리 다양화
    by_cat = {}
    for p in parsed:
        by_cat.setdefault(p["category"], []).append(p)
    print(f"  카테고리: {[(k, len(v)) for k, v in sorted(by_cat.items())]}")

    # 카테고리별 quota: celeb_actor 35, idol 35, plus 8, comedian 11
    quota = {"celeb_actor": 35, "idol": 35, "plus_size_model": 8, "comedian_mc": 11}

    selected = []
    used_slugs = set()
    for cat, q in quota.items():
        ms = by_cat.get(cat, [])
        # 큰 가슴(plus) > 작은 가슴(slim) 순
        ms.sort(key=lambda m: (0 if m["bust_cm"] > 90 else 1, -m.get("bust_cm", 0)))
        for m in ms:
            if m["slug"] in used_slugs:
                continue
            selected.append(m)
            used_slugs.add(m["slug"])
            if len([x for x in selected if x["category"] == cat]) >= q:
                break

    if len(selected) < target:
        # 부족하면 나머지 카테고리에서 보충
        for m in parsed:
            if m["slug"] in used_slugs:
                continue
            selected.append(m)
            used_slugs.add(m["slug"])
            if len(selected) >= target:
                break

    selected = selected[:target]
    print(f"  최종 선택: {len(selected)}명")
    print(f"    키 분포: <160={sum(1 for m in selected if m['height_cm']<160)}, "
          f"160-170={sum(1 for m in selected if 160<=m['height_cm']<170)}, "
          f"170-180={sum(1 for m in selected if 170<=m['height_cm']<180)}, "
          f"180+={sum(1 for m in selected if m['height_cm']>=180)}")
    print(f"    bust 분포: <76={sum(1 for m in selected if m['bust_cm']<76)}, "
          f"76-90={sum(1 for m in selected if 76<=m['bust_cm']<90)}, "
          f"90+={sum(1 for m in selected if m['bust_cm']>=90)}")

    # === STEP 4: 사진 다운로드 (large-photo 전신 우선, 없으면 portrait) ===
    print(f"[4] 사진 다운로드")
    dl_ok, dl_fail = 0, 0
    for m in selected:
        sid = slugify(m["display_name"])
        if sid in existing_ids:
            continue
        front_url = m.get("large_img") or m.get("portrait_img")
        out = CELEB_DIR / f"{sid}_front.jpg"
        if download(front_url, out):
            dl_ok += 1
        else:
            dl_fail += 1
        time.sleep(0.1)
    print(f"  download: ok={dl_ok}, fail={dl_fail}")

    # === STEP 5: 행 생성 ===
    print(f"[5] 행 생성")
    new_rows = []
    for m in selected:
        sid = slugify(m["display_name"])
        if sid in existing_ids:
            continue
        bmi = round(m["weight_kg"] / (m["height_cm"] / 100) ** 2, 1)
        waist_hip = round(m["waist_cm"] / m["hip_cm"], 3)
        new_rows.append({
            "subject_id": sid,
            "gender": m["gender"],
            "height": m["height_cm"],
            "weight": m["weight_kg"],
            "chest": m["bust_cm"],
            "waist": m["waist_cm"],
            "hip": m["hip_cm"],
            "bmi": bmi,
            "waist_hip_ratio": waist_hip,
            "category": m["category"],
            "source": m["url"],
        })
        existing_ids.add(sid)

    # === STEP 6: CSV 쓰기 ===
    print(f"[6] CSV 쓰기")
    fields = ["subject_id", "gender", "height", "weight", "chest", "waist", "hip", "bmi", "waist_hip_ratio", "category", "source"]
    with INDEX_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in final_rows:
            w.writerow({k: r[k] for k in fields})
        for r in new_rows:
            w.writerow({k: r[k] for k in fields})

    fields_all = fields + ["pred_chest", "pred_waist", "pred_hip", "err_chest", "err_waist", "err_hip"]
    with ALL_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_all)
        w.writeheader()
        for r in final_rows:
            full = {k: r.get(k, "") for k in fields_all}
            w.writerow(full)
        for r in new_rows:
            full = {k: r.get(k, "") for k in fields_all}
            w.writerow(full)

    total = len(final_rows) + len(new_rows)
    print(f"\n=== DONE: {total}명 celebs ===")
    print(f"  {INDEX_CSV}")
    print(f"  {ALL_CSV}")


if __name__ == "__main__":
    main()
