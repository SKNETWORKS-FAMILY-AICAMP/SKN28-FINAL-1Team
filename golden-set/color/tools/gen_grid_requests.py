"""17장 그리드 이미지 생성 요청 JSON 작성.

각 그리드: 4행×5열, 20셀 (17 사용 + 3 비움).
T-셔츠 색상: 행별로 고정 (top_color).
바지 색상: 17색 모두 (cell 위치별로 결정).
"""

from __future__ import annotations

import json
import sys
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


def build_grid_prompt(top: str) -> str:
    top_hex = COLORS_HEX[top]
    top_hint = COLOR_HINTS[top]
    # 17 pants colors (in COLORS order)
    pants_list = ", ".join(
        f"cell {i+1}: {c} ({COLORS_HEX[c]})" for i, c in enumerate(COLORS)
    )
    return (
        f"Flat-lay fashion product photography grid on pure white background, "
        f"arranged in 4 rows and 5 columns layout (total 20 cells, the last 3 cells in the bottom row are empty/blank). "
        f"Each filled cell contains a folded crew-neck cotton t-shirt on the left side and "
        f"a pair of folded cotton chinos pants on the right side, neatly arranged, top-down view. "
        f"The t-shirt color is the SAME in all 17 filled cells: {top} ({top_hex}, {top_hint}). "
        f"The pants color VARIES by cell, in this exact order from top-left to bottom-right "
        f"(reading left-to-right, top-to-bottom): {pants_list}. "
        f"Each outfit in each cell follows this order so that you see all 17 different pants colors "
        f"paired with the same {top} t-shirt. "
        f"Style: Pinterest minimal fashion catalog, soft natural light, professional product photo, "
        f"e-commerce look, no model, no text, no shadow, no watermark, no logo, no mannequin, "
        f"clean centered composition, white borders between cells."
    )


def main() -> int:
    out_dir = Path(OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = out_dir / "_grid_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)

    requests = [
        {
            "prompt": build_grid_prompt(top),
            "output_file_path": f"{OUT_DIR}\\outfit_grid_{top.lower().replace(' ', '_')}.png",
            "input_file_paths": [REF_PATH],
            "aspect_ratio": "1:1",
            "resolution": "1K",
        }
        for top in COLORS
    ]

    BATCH = 10
    batches = [requests[i:i + BATCH] for i in range(0, len(requests), BATCH)]
    for bi, batch in enumerate(batches):
        out_path = batch_dir / f"grid_batch_{bi:02d}.json"
        out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {len(requests)} grid requests, {len(batches)} batches")
    for top in COLORS:
        print(f"  - outfit_grid_{top.lower().replace(' ', '_')}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
