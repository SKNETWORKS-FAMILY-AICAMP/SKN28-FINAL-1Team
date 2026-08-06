"""289장 outfit 이미지 생성을 위한 batch JSON 파일 생성.

각 파일은 image_synthesize의 requests 파라미터로 바로 사용 가능.
"""

from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path


COLORS = [
    "Black", "White", "Charcoal", "Navy", "Beige", "Olive", "Brown",
    "Burgundy", "Mustard", "Teal", "Gray", "Cream", "Rust",
    "Forest Green", "Lavender", "Light Blue", "Blush Pink",
]

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

REF_PATH = "C:\\Users\\Playdata\\Desktop\\SKN28-FINAL-1Team\\docs\\golden-set\\assets\\pinterest_ref.jpg"
OUT_DIR = "C:\\Users\\Playdata\\Desktop\\SKN28-FINAL-1Team\\docs\\golden-set\\outfits"


def build_prompt(top: str, bot: str) -> str:
    th, bh = COLORS_HEX[top], COLORS_HEX[bot]
    th_hint, bh_hint = COLOR_HINTS[top], COLOR_HINTS[bot]
    return (
        f"Flat-lay fashion product photography on pure white background, top-down view, "
        f"no model, no text, no shadow, no watermark, no logo, no mannequin. "
        f"Left side: a {top} ({th}, {th_hint}) long-sleeve button-up cotton shirt, "
        f"neatly folded, slightly wrinkled fabric texture. "
        f"Right side: a pair of {bot} ({bh}, {bh_hint}) cotton chinos pants, "
        f"neatly folded, cuff at the bottom. "
        f"Pinterest minimal catalog style, soft natural light, professional product photo, "
        f"e-commerce product shot, clean composition, centered."
    )


def fname(row: str, col: str) -> str:
    return f"outfit_{row.lower().replace(' ', '_')}_{col.lower().replace(' ', '_')}.png"


def main() -> int:
    all_pairs = list(product(COLORS, COLORS))  # 289
    BATCH = 10
    batches = [all_pairs[i:i + BATCH] for i in range(0, len(all_pairs), BATCH)]

    out_dir = Path(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\docs\golden-set\outfits\_batches")
    out_dir.mkdir(parents=True, exist_ok=True)

    for bi, batch in enumerate(batches):
        requests = [
            {
                "prompt": build_prompt(row, col),
                "output_file_path": f"{OUT_DIR}\\{fname(row, col)}",
                "input_file_paths": [REF_PATH],
                "aspect_ratio": "1:1",
                "resolution": "1K",
            }
            for row, col in batch
        ]
        out_path = out_dir / f"batch_{bi:02d}.json"
        out_path.write_text(json.dumps(requests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK: {len(batches)} batches written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
