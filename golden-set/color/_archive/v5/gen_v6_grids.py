"""v6: 12 pants × 17 tops outfit 그리드 생성 (3×4 레이아웃).

각 그리드:
  - 17 top colors (v2 grade map) + 12 pants (8 필수 + 4 추가)
  - 3 rows × 4 cols = 12 cells = 12 pants
  - Pinterest 스타일 flat-lay T-셔츠 + 바지

생성: 17 그리드 = 17 image_synthesize 호출 필요
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# 17 top colors (v2 grade map, 영문)
TOPS = [
    "Black", "White", "Charcoal", "Navy", "Beige", "Olive", "Brown",
    "Burgundy", "Mustard", "Teal", "Gray", "Cream", "Rust",
    "Forest Green", "Lavender", "Light Blue", "Blush Pink",
]

TOP_HEX = {
    "Black":        "#1E1E2E",
    "White":        "#FFFFFF",
    "Charcoal":     "#36454F",
    "Navy":         "#1B2444",
    "Beige":        "#D9C3A5",
    "Olive":        "#6B6B45",
    "Brown":         "#6B4F3A",
    "Burgundy":     "#7A1F4F",
    "Mustard":      "#D4A017",
    "Teal":         "#008080",
    "Gray":         "#808080",
    "Cream":        "#F5E6CC",
    "Rust":         "#B5523A",
    "Forest Green": "#2E5E4E",
    "Lavender":     "#B57EDC",
    "Light Blue":   "#ADD8E6",
    "Blush Pink":   "#FFB6C1",
}

# 12 Pants (v6: 8 필수 + 4 추가)
PANTS = [
    # 8 필수
    ("Denim",       "#4A6FA5", "medium blue jean"),
    ("White",       "#FFFFFF", "pure white"),
    ("Black",       "#1E1E2E", "true black"),
    ("Beige",       "#D9C3A5", "light warm tan"),
    ("Ivory",       "#F2E8D5", "warm off-white"),
    ("Brown",       "#6B4F3A", "medium warm brown"),
    ("Khaki",       "#8B7355", "khaki/tan"),
    ("Navy",        "#1B2444", "dark navy"),
    # 4 추가
    ("Medium Gray", "#808080", "neutral medium gray"),
    ("Light Denim", "#A0BCD8", "light blue jean"),
    ("Dark Denim",  "#2C3E50", "dark indigo jean"),
    ("Olive",       "#6B6B45", "warm olive green"),
]


def build_prompt(top: str) -> str:
    """3x4 grid: 12 pants × 1 top color."""
    top_hex = TOP_HEX[top]
    pants_list = ", ".join(
        f"cell {i+1}: {n} ({h}, {desc})" for i, (n, h, desc) in enumerate(PANTS)
    )
    return (
        f"Flat-lay fashion product photography grid on pure white background, "
        f"arranged in 3 rows and 4 columns layout (total 12 cells, all cells filled with different pants colors). "
        f"Each filled cell contains a folded crew-neck cotton t-shirt on the left side and "
        f"a pair of folded cotton chinos pants on the right side, neatly arranged, top-down view. "
        f"The t-shirt color is the SAME in all 12 cells: {top} ({top_hex}). "
        f"The pants color VARIES by cell, showing 12 different real-world common pants colors "
        f"in this exact order from top-left to bottom-right (reading left-to-right, top-to-bottom): "
        f"{pants_list}. "
        f"These 12 pants represent the realistic basic wardrobe that people actually own: "
        f"8 essential pants (denim, white, black, beige, ivory, brown, khaki, navy) + "
        f"4 additional common pants (medium gray, light denim, dark denim, olive). "
        f"The user wants to see how the {top} t-shirt pairs with all 12 of these wardrobe basics. "
        f"Style: Pinterest minimal fashion catalog, soft natural light, professional product photo, "
        f"e-commerce look, no model, no text, no shadow, no watermark, no logo, no mannequin, "
        f"clean centered composition, white borders between cells."
    )


def main() -> int:
    out_dir = Path(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\docs\golden-set\outfits\v6_grids")
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = out_dir / "_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)

    REF_PATH = "C:\\Users\\Playdata\\Desktop\\SKN28-FINAL-1Team\\docs\\golden-set\\assets\\pinterest_ref.jpg"

    requests = []
    for top in TOPS:
        fname = f"outfit_v6_{top.lower().replace(' ', '_')}.png"
        requests.append({
            "prompt": build_prompt(top),
            "output_file_path": str(out_dir / fname),
            "input_file_paths": [REF_PATH],
            "aspect_ratio": "1:1",
            "resolution": "1K",
        })

    BATCH = 10
    batches = [requests[i:i + BATCH] for i in range(0, len(requests), BATCH)]
    for bi, batch in enumerate(batches):
        out_path = batch_dir / f"v6_batch_{bi:02d}.json"
        out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    meta = {
        "version": "v6",
        "philosophy": "12 pants (8 필수 + 4 추가) × 17 tops outfit 그리드. Pinterest flat-lay + wardrobe basics.",
        "tops": [{"name": t, "hex": TOP_HEX[t]} for t in TOPS],
        "pants": [{"name": n, "hex": h, "desc": d} for n, h, d in PANTS],
        "total_grids": len(TOPS),
        "outfits_per_grid": 12,
        "total_outfits": len(TOPS) * 12,
    }
    (out_dir / "v6_grids_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"OK: {len(requests)} v6 grids, {len(batches)} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
