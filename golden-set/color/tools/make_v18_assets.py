"""v3 18색 자산 일괄 생성.

color_rules.json v2 (18색: 17 v2 + Blue 신규) → 4 카테고리 분류 → JSON 2개 + 차트 4장 + outfit batch 18개.

4 카테고리 분류 규칙 (color_rules.json attributes 기준):
- WARM: temperature == 'warm'
- COOL: temperature == 'cool'
- NEUTRAL: temperature == 'neutral' (Black, White, Charcoal, Navy, Gray, Cream, Beige, Brown, Blue)
- MUTED: visual_effect == '축소' AND chroma < 35 (저채도 색)

Blue(#2A5CAA, cool, accent) → a3d73bd commit에 따라 NEUTRAL 폴백 위치였으므로 NEUTRAL.

사용법:
    python make_v18_assets.py
"""
from __future__ import annotations
import json
import math
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent  # golden-set/color/tools/
COLOR_ROOT = TOOLS.parent  # golden-set/color/
RULES = COLOR_ROOT / "rules"
IMAGES = COLOR_ROOT / "images"
OUTFITS = IMAGES / "outfits"
CHARTS = IMAGES / "combination_charts"
GRIDS = OUTFITS / "v6_grids"
BATCHES = GRIDS / "_batches"

# 12 pants (실사용 데이터 기반 8 필수 + 4 추가)
PANTS = [
    {"name": "Denim",        "hex": "#4A6FA5", "tier": "essential"},
    {"name": "White",        "hex": "#FFFFFF", "tier": "essential"},
    {"name": "Black",        "hex": "#1E1E2E", "tier": "essential"},
    {"name": "Beige",        "hex": "#D9C3A5", "tier": "essential"},
    {"name": "Ivory",        "hex": "#F2E8D5", "tier": "essential"},
    {"name": "Brown",        "hex": "#6B4F3A", "tier": "essential"},
    {"name": "Khaki",        "hex": "#8B7355", "tier": "essential"},
    {"name": "Navy",         "hex": "#1B2444", "tier": "essential"},
    {"name": "Medium Gray",  "hex": "#808080", "tier": "extra"},
    {"name": "Light Denim",  "hex": "#A0BCD8", "tier": "extra"},
    {"name": "Dark Denim",   "hex": "#2C3E50", "tier": "extra"},
    {"name": "Olive",        "hex": "#6B6B45", "tier": "extra"},
]

CATEGORY_PALETTE_SIZE = {"main": 8, "complement": 5, "muted": 2}


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def categorize(attr: dict) -> str:
    """color_rules.json attributes 1개 → 4 카테고리 중 1개.

    규칙 (role + 온도 + chroma):
    - role == 'semi_neutral' (Brown, Olive) → MUTED
    - temperature == 'warm' → WARM
    - temperature == 'cool' AND chroma >= 35 → COOL  (Blue, Forest Green, Lavender)
    - temperature == 'cool' AND chroma < 25 → MUTED  (Charcoal, Light Blue, Navy, Teal)
    - temperature == 'neutral' → NEUTRAL  (Black, Gray, White)
    """
    role = attr.get("role", "neutral")
    t = attr.get("temperature", "neutral")
    c = attr.get("chroma", 0.0)
    if role == "semi_neutral":
        return "MUTED"
    if t == "warm":
        return "WARM"
    if t == "cool":
        return "COOL" if c >= 35 else "MUTED"
    return "NEUTRAL"


def load_v2_palette() -> dict:
    """color_rules.json v2 (18색) attributes dict."""
    with open(RULES / "color_rules.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["attributes"]


def build_category_palettes(attrs: dict) -> dict:
    """4 카테고리(WARM/COOL/NEUTRAL/MUTED) × {main, complement, muted} 구조.

    v3 단순화: 카테고리당 main = 카테고리 내 색상 모두, complement = NEUTRAL 5색,
    muted = MUTED 카테고리 2색. Michael 84 차트보다 단순화된 18색 버전.
    """
    buckets: dict[str, list[str]] = {"WARM": [], "COOL": [], "NEUTRAL": [], "MUTED": []}
    for name, a in attrs.items():
        cat = categorize(a)
        buckets[cat].append(name)

    neutral_all = sorted(buckets["NEUTRAL"])
    muted_all = sorted(buckets["MUTED"])

    result = {}
    for cat, names in buckets.items():
        if not names:
            continue
        result[cat] = {
            "main": sorted(names)[: CATEGORY_PALETTE_SIZE["main"]],
            "complement": neutral_all[: CATEGORY_PALETTE_SIZE["complement"]],
            "muted": muted_all[: CATEGORY_PALETTE_SIZE["muted"]],
        }
    return result


def build_combination_matches(attrs: dict) -> dict:
    """18색 × 12 pants = 216쌍 grade (R1~R6 룰 기반).

    단순화:
    - 둘 다 neutral → recommended
    - 한쪽 neutral → recommended
    - 둘 다 accent + chroma>=45 + hue차>=150 → avoid
    - 명도차 < 18 → caution
    - 보색 + chroma<25 → allowed
    - 웜·쿨 혼합 → caution
    """
    pairs: list[dict] = []
    for top_name, top_a in attrs.items():
        for pant in PANTS:
            top_hue = top_a.get("hue", 0.0)
            top_chroma = top_a.get("chroma", 0.0)
            top_role = top_a.get("role", "neutral")
            pant_rgb = hex_to_rgb(pant["hex"])
            # pant lightness (YIQ)
            pant_l = (pant_rgb[0] * 299 + pant_rgb[1] * 587 + pant_rgb[2] * 114) / 1000
            top_l = top_a.get("lightness", 50.0)
            l_diff = abs(top_l - pant_l)
            grade = "recommended"
            reason = []
            if top_role == "neutral" or pant["tier"] == "essential":
                pass  # already recommended
            if top_chroma >= 45 and abs(top_hue - 220) >= 150:  # arbitrary
                grade = "avoid"
                reason.append("R3: 고채도+보색")
            elif l_diff < 18:
                grade = "caution"
                reason.append("R4: 명도 뭉개짐")
            if top_a.get("temperature") == "warm" and pant["name"] in ("Navy", "Black", "Charcoal"):
                if grade == "recommended":
                    grade = "caution"
                reason.append("R6: 웜·쿨 혼합")
            pairs.append({
                "top": top_name,
                "pant": pant["name"],
                "pant_hex": pant["hex"],
                "grade": grade,
                "reasons": reason,
            })
    return {"version": "v2.1", "total_pairs": len(pairs), "pairs": pairs}


def render_chart_png(category: str, palette: dict, attrs: dict, out_path: Path) -> None:
    """4 카테고리 메인컬러 + 컴플리멘트리 + muted 차트 PNG (PIL).

    단순 그리드: main 행 + complement 행 + muted 행. 색깔 칩 + 이름.
    """
    from PIL import Image, ImageDraw, ImageFont
    cell_w, cell_h = 110, 70
    rows = [
        ("main", palette[category]["main"]),
        ("complement", palette[category]["complement"]),
        ("muted", palette[category]["muted"]),
    ]
    cols = max(len(r[1]) for r in rows)
    pad = 16
    title_h = 40
    label_h = 24
    W = pad + cols * (cell_w + 6) + pad
    H = title_h + sum(cell_h + label_h + 6 for _ in rows) + pad

    img = Image.new("RGB", (W, H), "#FAFAFA")
    draw = ImageDraw.Draw(img)

    # title
    try:
        title_font = ImageFont.truetype("arial.ttf", 22)
        body_font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    draw.text((pad, 8), f"{category} 18색 팔레트", fill="#1A1A1A", font=title_font)

    y = title_h
    for label, names in rows:
        # row label
        draw.text((pad, y + cell_h // 2 - 6), label, fill="#666", font=body_font)
        x = pad + 60
        for name in names:
            a = attrs.get(name)
            if not a:
                continue
            draw.rectangle(
                (x, y, x + cell_w, y + cell_h),
                fill=a["hex"],
                outline="#DDDDDD",
            )
            # hex text (white if dark, black if light)
            r, g, b = hex_to_rgb(a["hex"])
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            text_color = "#FFFFFF" if lum < 128 else "#1A1A1A"
            draw.text((x + 6, y + 6), name, fill=text_color, font=body_font)
            draw.text(
                (x + 6, y + cell_h - 16),
                a["hex"],
                fill=text_color,
                font=body_font,
            )
            x += cell_w + 6
        y += cell_h + label_h + 6

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def build_outfit_batch(attrs: dict, batch_size: int = 10) -> list[dict]:
    """outfit 18장 image_synthesize batch JSON.

    각 outfit = 1 top (T-shirt 단색) + 12 pants 매칭 flat-lay 1장.
    prompt: Pinterest 스타일, white background, top-down flat-lay, T-shirt + chinos.
    """
    ref_path = "golden-set/color/images/reference/pinterest_ref.jpg"
    requests = []
    for i, (name, a) in enumerate(attrs.items()):
        prompt = (
            f"Top-down flat-lay product photo on pure white background. "
            f"Crew-neck T-shirt in {name} ({a['hex']}) placed on top, "
            f"below it 12 folded pants arranged in a 3x4 grid showing: "
            f"Denim, White, Black, Beige, Ivory, Brown, Khaki, Navy, "
            f"Medium Gray, Light Denim, Dark Denim, Olive. "
            f"Even soft studio lighting, no shadows, no text, no model. "
            f"Style like Pinterest fashion flat-lay, 1:1 square."
        )
        out_path = f"golden-set/color/images/outfits/v6_grids/outfit_v6_{name.lower().replace(' ', '_')}.png"
        requests.append({
            "prompt": prompt,
            "output_file_path": out_path,
            "input_file_paths": [ref_path],
            "aspect_ratio": "1:1",
            "resolution": "2K",
        })
    # batch_size 단위로 분할
    batches = []
    for i in range(0, len(requests), batch_size):
        batches.append({
            "batch_index": i // batch_size,
            "count": min(batch_size, len(requests) - i),
            "requests": requests[i : i + batch_size],
        })
    return batches


def main() -> None:
    try:
        attrs = load_v2_palette()
        print(f"[load] color_rules.json v2 attributes: {len(attrs)} colors")
        # Blue 위치 확인
        if "Blue" in attrs:
            print(f"[blue] {attrs['Blue']['hex']} role={attrs['Blue']['role']} "
                  f"temp={attrs['Blue']['temperature']} chroma={attrs['Blue']['chroma']}")

        # 1) category_palettes.json
        palettes = build_category_palettes(attrs)
        with open(RULES / "category_palettes.json", "w", encoding="utf-8") as f:
            json.dump({"version": "v3", "colors_total": len(attrs),
                       "category_palettes": palettes}, f, ensure_ascii=False, indent=2)
        print(f"[json] category_palettes.json → {sum(len(p['main']) for p in palettes.values())} mains in {len(palettes)} categories")

        # 2) combination_matches.json
        matches = build_combination_matches(attrs)
        with open(RULES / "combination_matches.json", "w", encoding="utf-8") as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)
        by_grade = {}
        for p in matches["pairs"]:
            by_grade[p["grade"]] = by_grade.get(p["grade"], 0) + 1
        print(f"[json] combination_matches.json → {matches['total_pairs']} pairs: {by_grade}")

        # 3) 차트 4장 PIL PNG
        CHARTS.mkdir(parents=True, exist_ok=True)
        for cat in palettes.keys():
            out = CHARTS / f"chart_{cat.lower()}.png"
            render_chart_png(cat, palettes, attrs, out)
            print(f"[chart] {out.name} → {out.stat().st_size} bytes")

        # 4) outfit batch JSON
        BATCHES.mkdir(parents=True, exist_ok=True)
        batches = build_outfit_batch(attrs, batch_size=10)
        for b in batches:
            out = BATCHES / f"v6_batch_{b['batch_index']:02d}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(b, f, ensure_ascii=False, indent=2)
            print(f"[batch] {out.name} → {b['count']} requests")

        print("[done] v3 18색 자산 생성 완료")
    except Exception as e:
        import traceback
        print(f"[ERR] {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
