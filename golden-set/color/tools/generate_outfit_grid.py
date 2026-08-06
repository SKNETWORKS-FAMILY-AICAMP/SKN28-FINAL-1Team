"""17×17 = 289 조합 outfit flat-lay 이미지 생성.

각 호출에 10장 (image_synthesize 한계) → 29 호출.
입력:
  - color_rules.json: 17색 hex 매핑
  - Pinterest reference image: 레퍼런스 스타일

출력:
  - C:\\Users\\Playdata\\Downloads\\golden_set_assets\\outfits_v2\\outfit_{row}_{col}.png
"""

from __future__ import annotations

import asyncio
import json
import sys
from itertools import product
from pathlib import Path

# 17색 (rules/color_rules.json의 attributes 키 순서와 일치)
COLORS = [
    "Black", "White", "Charcoal", "Navy", "Beige", "Olive", "Brown",
    "Burgundy", "Mustard", "Teal", "Gray", "Cream", "Rust",
    "Forest Green", "Lavender", "Light Blue", "Blush Pink",
]

# Pinterest reference
PINTEREST_REF = Path(r"C:\Users\Playdata\Downloads\golden_set_assets\v1_backup\pinterest_a0416f4d64d83b2305cebf98ba4a7d9b.jpg")

# 출력 폴더
OUTPUT_DIR = Path(r"C:\Users\Playdata\Downloads\golden_set_assets\outfits_v2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# v2 17색 hex (color_rules.json과 동기화)
COLORS_HEX = {
    "Black":        "#000000",
    "White":        "#FFFFFF",
    "Charcoal":     "#36454F",
    "Navy":         "#1B2444",
    "Beige":        "#E8DCC4",
    "Olive":        "#6B6B45",
    "Brown":        "#6B4A2F",
    "Burgundy":     "#800020",
    "Mustard":      "#D4A017",
    "Teal":         "#008080",
    "Gray":         "#808080",
    "Cream":        "#F5E6CC",
    "Rust":         "#B7410E",
    "Forest Green": "#228B22",
    "Lavender":     "#B57EDC",
    "Light Blue":   "#ADD8E6",
    "Blush Pink":   "#FFB6C1",
}

# 안전을 위한 색상 설명 (모델이 헷갈릴 때 대비)
COLOR_HINTS = {
    "Black":        "true black, jet black",
    "White":        "pure white, snow white",
    "Charcoal":     "charcoal gray (very dark, slightly bluish gray)",
    "Navy":         "navy blue (very dark blue, almost black)",
    "Beige":        "beige (light warm tan)",
    "Olive":        "olive green (dark yellowish green)",
    "Brown":        "brown (medium warm brown)",
    "Burgundy":     "burgundy (dark wine red, deep maroon)",
    "Mustard":      "mustard yellow (warm dark yellow)",
    "Teal":         "teal (dark cyan, blue-green)",
    "Gray":         "neutral medium gray",
    "Cream":        "cream (light warm off-white)",
    "Rust":         "rust orange (warm dark orange-red)",
    "Forest Green": "forest green (deep cool green)",
    "Lavender":     "lavender (light cool purple)",
    "Light Blue":   "light blue (pale sky blue)",
    "Blush Pink":   "blush pink (pale warm pink)",
}


def build_prompt(top_color: str, bot_color: str) -> str:
    top_hex = COLORS_HEX[top_color]
    bot_hex = COLORS_HEX[bot_color]
    top_hint = COLOR_HINTS[top_color]
    bot_hint = COLOR_HINTS[bot_color]
    return (
        f"Flat-lay fashion product photography on pure white background, top-down view, "
        f"no model, no text, no shadow, no watermark, no logo, no mannequin. "
        f"Left side: a {top_color} ({top_hex}, {top_hint}) long-sleeve button-up cotton "
        f"shirt, neatly folded, slightly wrinkled fabric texture. "
        f"Right side: a pair of {bot_color} ({bot_hex}, {bot_hint}) cotton chinos pants, "
        f"neatly folded, cuff at the bottom. "
        f"Pinterest minimal catalog style, soft natural light, professional product photo, "
        f"e-commerce product shot, clean composition, centered."
    )


def build_outfit_requests(batch: list[tuple[str, str]]) -> list[dict]:
    """(row_color, col_color) 리스트 → image_synthesize requests."""
    return [
        {
            "prompt": build_prompt(row, col),
            "output_file_path": str(OUTPUT_DIR / f"outfit_{row.lower().replace(' ', '_')}_{col.lower().replace(' ', '_')}.png"),
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "input_file_paths": [str(PINTEREST_REF)],
        }
        for row, col in batch
    ]


def main() -> int:
    if not PINTEREST_REF.exists():
        print(f"ERROR: Pinterest reference not found at {PINTEREST_REF}")
        return 1

    all_pairs = list(product(COLORS, COLORS))  # 17×17 = 289
    print(f"Total: {len(all_pairs)} outfit pairs")

    # 이미 생성된 건 건너뛰기
    pairs_to_generate = []
    skipped = 0
    for row, col in all_pairs:
        out_path = OUTPUT_DIR / f"outfit_{row.lower().replace(' ', '_')}_{col.lower().replace(' ', '_')}.png"
        if out_path.exists():
            skipped += 1
        else:
            pairs_to_generate.append((row, col))
    print(f"  skipped (already exists): {skipped}")
    print(f"  to generate: {len(pairs_to_generate)}")

    # 10장씩 배치
    BATCH = 10
    batches = [pairs_to_generate[i:i + BATCH] for i in range(0, len(pairs_to_generate), BATCH)]
    print(f"  batches: {len(batches)} (max {BATCH} per call)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
