"""v4: Practical 7 common pants × 17 tops 그리드.

개선점 (v3 대비):
  - 바지: 7가지 기본 색 (White, Black, Navy, Gray, Brown, Ivory, Denim)
  - 상의: 17색 (v2 grade map 동일)
  - 퍼스널컬러: 4계절 팔레트를 "참고"해서 다양성 추구
    - v3처럼 색 family 내 shade를 바꿔가며 매칭하는 게 아니라
    - "실제 wardrobe" 7개 기본을 모든 상의에 매칭
    - 잘 어울리는 조합과 안 어울리는 조합을 시각적으로 비교 가능
  - 그리드: 3×3 = 9 셀, 7 outfits + 2 empty

저장:
  - golden-set/color/images/outfits/practical/outfit_practical_{top}.png (17장)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# 17 top colors (v2 grade map)
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
    "Brown":        "#6B4F3A",
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

# 7 common pants (현실 wardrobe 기본)
COMMON_PANTS = [
    ("White",    "#FFFFFF", "neutral cool/bright"),
    ("Black",    "#1E1E2E", "neutral dark"),
    ("Navy",     "#1F2A44", "cool dark"),
    ("Gray",     "#808080", "neutral medium"),
    ("Brown",    "#6B4F3A", "warm dark"),
    ("Ivory",    "#F2E8D5", "neutral warm light"),
    ("Denim",    "#4A6FA5", "cool medium (classic blue jean)"),
]


def build_prompt(top: str) -> str:
    """7 common pants × top t-shirt 3x3 grid."""
    top_hex = TOP_HEX[top]
    pants_list = ", ".join(
        f"cell {i+1}: {n} ({h}, {desc})" for i, (n, h, desc) in enumerate(COMMON_PANTS)
    )
    return (
        f"Flat-lay fashion product photography grid on pure white background, "
        f"arranged in 3 rows and 3 columns layout (total 9 cells, the last 2 cells in the bottom row are empty/blank). "
        f"Each filled cell contains a folded crew-neck cotton t-shirt on the left side and "
        f"a pair of folded cotton chinos pants on the right side, neatly arranged, top-down view. "
        f"The t-shirt color is the SAME in all 7 filled cells: {top} ({top_hex}). "
        f"The pants color VARIES by cell, showing 7 common wardrobe basics in this exact order from top-left to bottom-right "
        f"(reading left-to-right, top-to-bottom): {pants_list}. "
        f"Each outfit in each cell follows this order so that you see 7 different pants colors "
        f"paired with the same {top} t-shirt. "
        f"These 7 pants represent the realistic basic wardrobe (white, black, navy, gray, brown, ivory, blue jeans) "
        f"that most people actually own. The user wants to see which of these 7 basics harmonize well with the {top} t-shirt. "
        f"Style: Pinterest minimal fashion catalog, soft natural light, professional product photo, "
        f"e-commerce look, no model, no text, no shadow, no watermark, no logo, no mannequin, "
        f"clean centered composition, white borders between cells."
    )


def main() -> int:
    out_dir = Path(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\docs\golden-set\outfits\practical")
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = out_dir / "_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)

    REF_PATH = "C:\\Users\\Playdata\\Desktop\\SKN28-FINAL-1Team\\docs\\golden-set\\assets\\pinterest_ref.jpg"

    requests = []
    for top in TOPS:
        fname = f"outfit_practical_{top.lower().replace(' ', '_')}.png"
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
        out_path = batch_dir / f"practical_batch_{bi:02d}.json"
        out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 메타데이터 저장
    meta = {
        "version": "v4",
        "philosophy": "실제 wardrobe 7가지 기본 바지 × 17 top. 퍼스널컬러는 다양성 참고용, 매칭 강제 아님.",
        "common_pants": [{"name": n, "hex": h, "desc": d} for n, h, d in COMMON_PANTS],
        "tops": [{"name": t, "hex": TOP_HEX[t]} for t in TOPS],
        "total_grids": len(TOPS),
        "outfits_per_grid": 7,
        "total_outfits": len(TOPS) * 7,
    }
    (out_dir / "practical_matching_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"OK: {len(requests)} practical grids, {len(batches)} batches")
    for top in TOPS:
        print(f"  - outfit_practical_{top.lower().replace(' ', '_')}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
