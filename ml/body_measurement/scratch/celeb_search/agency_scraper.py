"""
한국 모델 에이전시 일괄 스크레이퍼.

소스:
  - wavemodel.co.kr/model/  (WOMEN, ASIAN 탭 → 한국/아시아 모델)
  - platinummgt.co.kr       (WOMEN ca_id2=2, KOREA ca_id2=4)

각 모델:
  - 이름
  - 키(cm)
  - 가슴/허리/엉덩이 (cm, platinummgt는 inch→cm 변환)
  - 썸네일 이미지 URL (450x600 또는 wp-content 직접 URL)

사용법:
    python3 agency_scraper.py --out agencies.json
"""
import argparse
import json
import re
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

IN_TO_CM = 2.54

# macOS python: CERTIFICATE_VERIFY_FAILED 우회
_SSL_CTX = ssl.create_default_context()
try:
    _SSL_CTX.set_ciphers("DEFAULT@SECLEVEL=1")
except Exception:
    pass
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,ko;q=0.8"})
    with urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        if r.status != 200:
            return ""
        return r.read().decode("utf-8", errors="replace")


# === Wave Model 파서 ===
# 실제 HTML 구조 순서:
#   <h2 class="ult-new-ib-title...">SONYA - UPCOMING</h2>
#   <p>Height 173<br>Bust 80<br>Waist 58<br>Hips 88<br>Shoe 240</p>
#   <a class="ult-new-ib-link" href="..." title="..."></a>
#   <img class="ult-new-ib-img" src="..." />

WAVE_NAME_RE = re.compile(
    r'<h2[^>]+class="ult-new-ib-title[^"]*"[^>]*>([^<]+)</h2>.*?'
    r'<p>\s*Height\s+(\d+)\s*<br[^>]*>\s*(?:Bust|Chest)\s+(\d+)\s*<br[^>]*>\s*Waist\s+(\d+)\s*<br[^>]*>\s*Hips\s+(\d+)\s*<br[^>]*>\s*Shoe\s+(\d+)\s*</p>.*?'
    r'<a[^>]+class="ult-new-ib-link"[^>]+href="([^"]+)"',
    re.DOTALL
)
WAVE_IMG_RE = re.compile(r'<img[^>]+class="ult-new-ib-img"[^>]+src="([^"]+)"')


def parse_wavemodel(html: str, category: str) -> list:
    """WOMEN / ASIAN / MEN 탭 데이터를 파싱."""
    out = []
    img_urls = [m.group(1) for m in WAVE_IMG_RE.finditer(html)]
    for i, m in enumerate(WAVE_NAME_RE.finditer(html)):
        try:
            name, h, b, w, hip, shoe, url = m.groups()
            # 이름에서 "-UPCOMING" 같은 suffix 제거
            clean_name = re.sub(r"\s*-\s*UPCOMING\s*$", "", name, flags=re.IGNORECASE).strip()
            clean_name = re.sub(r"\s*-\s*COMING\s+SOON\s*$", "", clean_name, flags=re.IGNORECASE).strip()
            out.append({
                "source": "wavemodel",
                "category": category,
                "name": clean_name,
                "url": url.strip(),
                "image_url": img_urls[i] if i < len(img_urls) else None,
                "height_cm": int(h),
                "bust_cm": int(b),
                "waist_cm": int(w),
                "hip_cm": int(hip),
                "shoe_mm": int(shoe),
            })
        except Exception as e:
            print(f"  [WARN] wavemodel block parse fail: {e}", file=sys.stderr)
    return out


# === Platinum Management 파서 ===
# 예: <li class="grid-item" data-filter="female">
#       <a href="https://www.platinummgt.co.kr/page/?pid=model_view&md_id=580&ca_id2=2" class="show_motion">
#         <span class="img">
#           <img src=".../thumb-3555977450_..._450x600.jpg" ...>
#         </span>
#         <em>ZHENIA</em>
#         <div class="description">
#           <em>ZHENIA</em>
#           <ul>
#             <li><i>ACTIVITY</i><span>07.09 - 09.10</span></li>
#             <li><i>HEIGHT</i><span>171</span></li>
#             <li><i>BUST</i><span>30.5</span></li>
#             <li><i>WAIST</i><span>24</span></li>
#             <li><i>HIP</i><span>34.5</span></li>
#             <li><i>SHOES</i><span>250~255</span></li>
#             ...

PLATINUM_BLOCK_RE = re.compile(
    r'<li\s+class="grid-item"[^>]*>\s*'
    r'<a[^>]+href="([^"]+)"[^>]*>.*?'
    r'<img\s+src="([^"]+)"[^>]*>.*?'
    r'<em>([^<]+)</em>.*?'
    r'<i>HEIGHT</i><span>([\d.]+)</span>.*?'
    r'<i>BUST</i><span>([\d.]+)</span>.*?'
    r'<i>WAIST</i><span>([\d.]+)</span>.*?'
    r'<i>HIP</i><span>([\d.]+)</span>.*?'
    r'<i>SHOES</i><span>([\d~]+)</span>',
    re.DOTALL
)


def parse_platinum(html: str, category: str) -> list:
    out = []
    for m in PLATINUM_BLOCK_RE.finditer(html):
        try:
            url, img, name, h, b, w, hip, shoe = m.groups()
            # 인치 → cm (1 inch = 2.54cm)
            bust_cm = round(float(b) * IN_TO_CM, 1)
            waist_cm = round(float(w) * IN_TO_CM, 1)
            hip_cm = round(float(hip) * IN_TO_CM, 1)
            # 신발 mm 파싱 (250~255 -> 250)
            shoe_mm = int(shoe.split("~")[0])
            # img URL은 thumb size 450x600, 원본은 _450x600 제거
            full_img = re.sub(r'_[45]0x[56]00\.', '.', img)
            out.append({
                "source": "platinummgt",
                "category": category,
                "name": name.strip(),
                "url": url.strip(),
                "image_url": full_img,
                "thumb_url": img,
                "height_cm": int(h),
                "bust_cm": bust_cm,
                "waist_cm": waist_cm,
                "hip_cm": hip_cm,
                "shoe_mm": shoe_mm,
            })
        except Exception as e:
            print(f"  [WARN] platinum block parse fail: {e}", file=sys.stderr)
    return out


# === 메인 ===
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()

    all_models = []

    # --- wavemodel.co.kr: WOMEN, ASIAN, MEN 모두 ---
    print("[*] wavemodel.co.kr/model/ fetching...")
    try:
        html = fetch("https://wavemodel.co.kr/model/")
        time.sleep(args.delay)
        # WOMEN 탭은 #1671375308146-4, MEN은 #1671375308160-7, ASIAN은 #1761038682571-2-5
        # 일단 페이지 전체에서 모두 추출 (탭 콘텐츠는 한 페이지에 모두 있음)
        women = parse_wavemodel(html, "women")
        asian = parse_wavemodel(html, "asian")
        men = parse_wavemodel(html, "men")
        # 중복 제거는 일단 안 함 (탭별로 같은 모델이 표시될 수 있음)
        # 하지만 같은 모델이 다른 탭에 있을 일은 거의 없음
        print(f"    women: {len(women)}, asian: {len(asian)}, men: {len(men)}")
        all_models.extend(women)
        all_models.extend(asian)
        all_models.extend(men)
    except Exception as e:
        print(f"  [ERR] wavemodel: {e}", file=sys.stderr)

    # --- platinummgt.co.kr: WOMEN, KOREA ---
    for ca_id, cat_label in [(2, "women"), (4, "korea")]:
        url = f"https://www.platinummgt.co.kr/page/?pid=model_list&ca_id2={ca_id}"
        print(f"[*] {url} fetching...")
        try:
            html = fetch(url)
            time.sleep(args.delay)
            models = parse_platinum(html, cat_label)
            print(f"    {cat_label}: {len(models)} models")
            all_models.extend(models)
        except Exception as e:
            print(f"  [ERR] {url}: {e}", file=sys.stderr)

    # --- 저장 ---
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_models, ensure_ascii=False, indent=2))
    print(f"\n[*] Total {len(all_models)} models saved → {out_path}")
    print(f"  by source: wavemodel={sum(1 for m in all_models if m['source']=='wavemodel')}, "
          f"platinummgt={sum(1 for m in all_models if m['source']=='platinummgt')}")
    print(f"  by category: " + ", ".join(
        f"{c}={sum(1 for m in all_models if m['category']==c)}"
        for c in sorted({m['category'] for m in all_models})
    ))


if __name__ == "__main__":
    main()
