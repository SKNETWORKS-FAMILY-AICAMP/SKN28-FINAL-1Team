"""v5: 4 카테고리 (Warm/Cool/Neutral/Muted) × Michael 84 스타일 조합 차트 렌더링.

각 카테고리마다 1장 차트:
  - 행: 메인컬러 (8-10개)
  - 열: Main | 5 Complementary | 2 Muted/Tonal (8개)
  - 각 셀: 색상 원 + 메인컬러 이름 + hex

이미지 사이즈: 1600x1400 (헤더 + 10행 × 8열 + 카테고리 타이틀)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ============================================================================
# 설정
# ============================================================================

REPO_ROOT = Path(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team")
CATEGORY_JSON = REPO_ROOT / "docs" / "golden-set" / "rules" / "category_palettes.json"
MATCHES_JSON = REPO_ROOT / "docs" / "golden-set" / "rules" / "combination_matches.json"
OUT_DIR = REPO_ROOT / "docs" / "golden-set" / "outfits" / "combination_charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 차트 크기
IMG_WIDTH = 1600
HEADER_HEIGHT = 220
ROW_HEIGHT = 110
LEFT_LABEL_WIDTH = 220
COL_LABEL_HEIGHT = 50
CELL_PADDING = 12
CIRCLE_RADIUS = 38

# 색상
BG = (255, 255, 255)
TEXT_DARK = (40, 40, 40)
TEXT_GRAY = (120, 120, 120)
HEADER_BG = (245, 245, 245)
LINE_GRAY = (220, 220, 220)


def load_fonts() -> dict:
    """PIL 폰트 로드 (Windows 기본)."""
    font_paths = [
        r"C:\Windows\Fonts\malgun.ttf",  # 맑은 고딕 (한글)
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    fonts = {}
    for fp in font_paths:
        if Path(fp).exists():
            try:
                fonts["title"] = ImageFont.truetype(fp, 36)
                fonts["header"] = ImageFont.truetype(fp, 22)
                fonts["row_label"] = ImageFont.truetype(fp, 18)
                fonts["small"] = ImageFont.truetype(fp, 13)
                fonts["hex"] = ImageFont.truetype(fp, 11)
                return fonts
            except Exception:
                continue
    # fallback
    default = ImageFont.load_default()
    return {"title": default, "header": default, "row_label": default, "small": default, "hex": default}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def is_dark(rgb: tuple[int, int, int]) -> bool:
    """색이 어두운지 판단 (라벨 텍스트 색 결정용)."""
    L = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return L < 130


def draw_circle_with_label(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    hex_color: str,
    label_text: str = "",
    fonts: dict = None,
):
    """색상 원 + 라벨 그리기."""
    rgb = hex_to_rgb(hex_color)
    # 원 (테두리: 연한 회색)
    bbox = (center[0] - CIRCLE_RADIUS, center[1] - CIRCLE_RADIUS,
            center[0] + CIRCLE_RADIUS, center[1] + CIRCLE_RADIUS)
    draw.ellipse(bbox, fill=rgb, outline=(180, 180, 180), width=1)
    if label_text and fonts:
        text_color = (255, 255, 255) if is_dark(rgb) else (40, 40, 40)
        bbox_text = draw.textbbox((0, 0), label_text, font=fonts["small"])
        text_w = bbox_text[2] - bbox_text[0]
        text_h = bbox_text[3] - bbox_text[1]
        tx = center[0] - text_w // 2
        ty = center[1] - text_h // 2
        draw.text((tx, ty), label_text, fill=text_color, font=fonts["small"])


def render_chart(category_key: str, category: dict, matches: dict, fonts: dict) -> Path:
    """한 카테고리 차트 렌더링."""
    main_colors = category["main_colors"]
    n_rows = len(main_colors)
    img_height = HEADER_HEIGHT + COL_LABEL_HEIGHT + n_rows * ROW_HEIGHT + 60
    img = Image.new("RGB", (IMG_WIDTH, img_height), BG)
    draw = ImageDraw.Draw(img)

    # === 타이틀 ===
    title = f"{category['name']} — Main × Complementary × Muted/Tonal"
    draw.text((30, 20), title, fill=TEXT_DARK, font=fonts["title"])
    subtitle = f"{category['description']}"
    draw.text((30, 65), subtitle, fill=TEXT_GRAY, font=fonts["header"])
    n_combo = len(matches.get(main_colors[0]["name"], {}).get("complementary", []))
    n_muted = len(matches.get(main_colors[0]["name"], {}).get("muted_tonal", []))
    draw.text(
        (30, 100),
        f"Pattern: Main (1) + Complementary ({n_combo}) + Muted/Tonal ({n_muted}) = {1 + n_combo + n_muted} per row  |  Rows: {n_rows} main colors",
        fill=TEXT_GRAY,
        font=fonts["small"],
    )

    # === 헤더 (컬럼 라벨) ===
    header_y = HEADER_HEIGHT
    col_xs = []
    # Main 컬럼
    col_xs.append(LEFT_LABEL_WIDTH + CELL_PADDING + CIRCLE_RADIUS)
    draw.text(
        (col_xs[0] - 30, header_y + 5),
        "MAIN",
        fill=TEXT_DARK,
        font=fonts["header"],
    )
    # Complementary 헤더 (그룹)
    for i in range(n_combo):
        cx = LEFT_LABEL_WIDTH + (1 + i) * 180 + 90
        col_xs.append(cx)
        draw.text(
            (cx - 70, header_y + 5),
            f"COMP {i+1}",
            fill=TEXT_GRAY,
            font=fonts["header"],
        )
    # Muted/Tonal 헤더 (그룹)
    for i in range(n_muted):
        cx = LEFT_LABEL_WIDTH + (1 + n_combo + i) * 180 + 90
        col_xs.append(cx)
        draw.text(
            (cx - 50, header_y + 5),
            f"MUTED {i+1}",
            fill=TEXT_GRAY,
            font=fonts["header"],
        )

    # 헤더 라인
    draw.line(
        [(0, header_y + COL_LABEL_HEIGHT - 5), (IMG_WIDTH, header_y + COL_LABEL_HEIGHT - 5)],
        fill=LINE_GRAY,
        width=1,
    )

    # === 메인 행들 ===
    for ri, main in enumerate(main_colors):
        row_y = header_y + COL_LABEL_HEIGHT + ri * ROW_HEIGHT + ROW_HEIGHT // 2
        # 행 라벨 (메인컬러 이름)
        draw.text(
            (15, row_y - 12),
            main["name"],
            fill=TEXT_DARK,
            font=fonts["row_label"],
        )
        draw.text(
            (15, row_y + 8),
            f"#{main['hex'][1:].upper()}  ({main['season']})",
            fill=TEXT_GRAY,
            font=fonts["hex"],
        )
        # 행 라인
        if ri > 0:
            draw.line(
                [(0, row_y - ROW_HEIGHT // 2), (IMG_WIDTH, row_y - ROW_HEIGHT // 2)],
                fill=LINE_GRAY,
                width=1,
            )
        # Main 원
        draw_circle_with_label(draw, (col_xs[0], row_y), main["hex"], "M", fonts)
        # Complementary 원들
        match = matches.get(main["name"], {})
        complementary = match.get("complementary", [])
        for i, comp_name in enumerate(complementary):
            comp_hex = lookup_hex(comp_name, main_colors, category_palette=category)
            if comp_hex:
                draw_circle_with_label(draw, (col_xs[1 + i], row_y), comp_hex, "C", fonts)
        # Muted/Tonal 원들
        muted = match.get("muted_tonal", [])
        for i, muted_name in enumerate(muted):
            muted_hex = lookup_hex(muted_name, main_colors, category_palette=category)
            if muted_hex:
                draw_circle_with_label(draw, (col_xs[1 + n_combo + i], row_y), muted_hex, "M", fonts)

    # 하단 라벨
    draw.text(
        (30, img_height - 30),
        f"v6 Golden Set · {category['season_affinity']} affinity · data-driven (CJ Logistics + 지그재그 + 무신사) · Michael 84 chart pattern",
        fill=TEXT_GRAY,
        font=fonts["small"],
    )

    out_path = OUT_DIR / f"chart_{category_key}.png"
    img.save(out_path, "PNG", optimize=True)
    return out_path


def lookup_hex(color_name: str, current_mains: list, category_palette: dict) -> str | None:
    """색 이름 → hex 찾기 (현재 카테고리 메인 + 4 카테고리 전체에서)."""
    # 1. 현재 카테고리 메인에서 찾기
    for c in current_mains:
        if c["name"] == color_name:
            return c["hex"]
    # 2. category_palettes.json에서 모든 카테고리 검색 (전역 팔레트에서)
    #    → 매칭 시 다른 카테고리도 검색해야 함
    # 이 함수는 호출 시점에 category_palette 외 다른 카테고리도 알아야 함
    # → 전역 패치: load_palette() 결과 사용
    return GLOBAL_HEX.get(color_name)


def main() -> int:
    cat_data = json.loads(CATEGORY_JSON.read_text(encoding="utf-8"))
    match_data = json.loads(MATCHES_JSON.read_text(encoding="utf-8"))

    # 전역 hex 맵 (4 카테고리 모두)
    global GLOBAL_HEX
    GLOBAL_HEX = {}
    for cat in cat_data["categories"].values():
        for c in cat["main_colors"]:
            GLOBAL_HEX[c["name"]] = c["hex"]

    fonts = load_fonts()
    print(f"Rendering 4 charts to {OUT_DIR}\n")
    for cat_key, cat in cat_data["categories"].items():
        matches = match_data["matches"].get(cat_key, {})
        out = render_chart(cat_key, cat, matches, fonts)
        size = out.stat().st_size
        print(f"  OK: {out.name}  ({size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
