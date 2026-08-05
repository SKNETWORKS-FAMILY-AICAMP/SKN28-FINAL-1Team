"""
bodysize.org 한국 연예인 일괄 fetcher.

Usage:
    python3 bodysize_fetcher.py --input candidates.txt --out candidates_parsed.json

각 후보 이름에 대해:
  - https://bodysize.org/en/<slug>/ 페이지를 가져옴
  - Height, Weight, Breast/Bust, Waist, Hips (cm) 파싱
  - 모두 있는 사람만 candidates_parsed.json에 기록
"""
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# 인치/파운드 변환
LB_TO_KG = 0.45359237
IN_TO_CM = 2.54


def name_to_slug(name: str) -> str:
    """'IU' -> 'iu', 'Park Shin-hye' -> 'park-shin-hye', 'BLACKPINK Rose' -> 'rose' (보조 후보)"""
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def fetch_page(slug: str) -> tuple:
    """(slug, status, html) 반환. status: 'ok' | '404' | 'err'"""
    url = f"https://bodysize.org/en/{slug}/"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urlopen(req, timeout=20) as r:
            if r.status != 200:
                return (slug, f"http_{r.status}", None)
            html = r.read().decode("utf-8", errors="replace")
            return (slug, "ok", html)
    except HTTPError as e:
        return (slug, f"http_{e.code}", None)
    except Exception as e:
        return (slug, "err", None)


# 페이지에서 cm 값 파싱
# 예: "Height|5 ft 6 in / 168 cm|"
#     "Weight|115 lb / 52 kg|"
#     "Breast/Bust size|31 in / 81 cm|"
#     "Waist size|24 in / 61 cm|"
#     "Hips size|33 in / 84 cm|"

# (Korean field name) -> regex pattern
FIELDS = {
    "height":   re.compile(r"Height[^|]*?(\d{2,3})\s*cm", re.IGNORECASE),
    "weight":   re.compile(r"Weight[^|]*?(\d{2,3})\s*kg", re.IGNORECASE),
    "chest":    re.compile(r"(?:Breast|Bust)\s*/?\s*Bust\s*size[^|]*?(\d{2,3})\s*cm", re.IGNORECASE),
    "waist":    re.compile(r"Waist\s*size[^|]*?(\d{2,3})\s*cm", re.IGNORECASE),
    "hip":      re.compile(r"Hips\s*size[^|]*?(\d{2,3})\s*cm", re.IGNORECASE),
    # 한국어 버전 (fallback)
    "height_ko": re.compile(r"신장[^|]*?(\d{2,3})\s*cm"),
    "weight_ko": re.compile(r"체중[^|]*?(\d{2,3})\s*kg"),
}

NAME_RE = re.compile(r"<title>([^<]+?)(?:\s*[\|·•\-]|\s*$)", re.IGNORECASE)


def parse_page(html: str) -> dict:
    out = {}
    for k, pat in FIELDS.items():
        m = pat.search(html)
        if m:
            try:
                out[k.replace("_ko", "")] = int(m.group(1))
            except ValueError:
                pass

    # 타이틀에서 이름 추출
    m = NAME_RE.search(html)
    if m:
        title = m.group(1).strip()
        out["page_title"] = title

    # 카테고리 감지
    if re.search(r"\b(?:Singer|K-pop idol|rapper)\b", html, re.IGNORECASE):
        out["category_hint"] = "idol"
    elif re.search(r"\b(?:actress|model|comedian|actor)\b", html, re.IGNORECASE):
        out["category_hint"] = "celeb_actor"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="한 줄 = 한 후보 이름 또는 슬러그")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--delay", type=float, default=0.2, help="호출 간 sleep(sec)")
    ap.add_argument("--limit", type=int, default=0, help="0=전부, N=앞 N개만")
    args = ap.parse_args()

    cands = []
    for line in Path(args.input).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cands.append(line)
    if args.limit > 0:
        cands = cands[:args.limit]
    print(f"후보 {len(cands)}명 일괄 fetch (workers={args.workers})")

    results = []
    ok, nf, err = 0, 0, 0
    parsed_5 = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        future_map = {ex.submit(fetch_page, name_to_slug(c)): c for c in cands}
        for fut in as_completed(future_map):
            cname = future_map[fut]
            slug, status, html = fut.result()
            if status != "ok":
                if "404" in status:
                    nf += 1
                else:
                    err += 1
                results.append({"input": cname, "slug": slug, "status": status})
                continue
            data = parse_page(html)
            ok += 1
            have_5 = all(k in data for k in ("height", "weight", "chest", "waist", "hip"))
            if have_5:
                parsed_5 += 1
            data["input"] = cname
            data["slug"] = slug
            data["url"] = f"https://bodysize.org/en/{slug}/"
            data["status"] = "ok"
            data["has_all_5"] = have_5
            results.append(data)
            time.sleep(args.delay)

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n=== 요약 ===")
    print(f"  ok:        {ok}")
    print(f"  not_found: {nf}")
    print(f"  errors:    {err}")
    print(f"  has_all_5: {parsed_5}")
    print(f"saved: {args.out}")


if __name__ == "__main__":
    main()
