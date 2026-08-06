"""퍼스널컬러 4계절 그리드 이미지 생성 (T셔츠 4×5).

각 시즌:
  - 17색 팔레트
  - 1 anchor T셔츠 색 (시즌 대표색)
  - 16 다른 색 바지 (16 + 1 anchor monochrome = 17 조합)

출력:
  - golden-set/color/images/outfits/personal_color/outfit_pc_{season}_{anchor}.png (4장)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


SEASONS = {
    "spring": {
        "name": "Spring Warm (봄웜)",
        "anchor": "Clear Coral",
        "palette": [
            ("Clear Ivory",      "#FFF1D6"),
            ("Cream Yellow",     "#FFE4B5"),
            ("Butter Yellow",    "#F7D86A"),
            ("Peach",            "#F6B38A"),
            ("Light Coral",      "#FF8F7A"),
            ("Clear Coral",      "#FF6F61"),
            ("Warm Pink",        "#F7A6B8"),
            ("Golden Yellow",    "#F5C542"),
            ("Marigold",         "#F4A51C"),
            ("Honey Brown",      "#C68642"),
            ("Golden Camel",     "#C99A5B"),
            ("Grass Green",      "#54A24B"),
            ("Apple Green",      "#7CB342"),
            ("Fresh Mint",       "#9FD8B5"),
            ("Light Aqua",       "#68C7C1"),
            ("Warm Turquoise",   "#28B7A8"),
            ("Clear Sky Blue",   "#A8D8EA"),
        ],
    },
    "summer": {
        "name": "Summer Cool (여름쿨)",
        "anchor": "Dusty Rose",
        "palette": [
            ("Cool White",       "#F4F5F5"),
            ("Moonlight White",  "#EAEFF5"),
            ("Powder Pink",      "#E9B7C7"),
            ("Rosewater",        "#DFA0B6"),
            ("Dusty Rose",       "#C9869A"),
            ("Soft Rose",        "#C894A0"),
            ("Mauve",            "#B57B9A"),
            ("Cool Lavender",    "#B7A7D8"),
            ("Periwinkle",       "#8FA8D8"),
            ("Powder Blue",      "#9EC9E2"),
            ("Mist Blue",        "#9CB3C7"),
            ("Slate Blue",       "#667FA3"),
            ("Lavender Gray",    "#A99AC4"),
            ("Soft Teal",        "#6F9A9A"),
            ("Pine Green",       "#4F7C72"),
            ("Soft Plum",        "#6F4E73"),
            ("Rose Beige",       "#E8C8DC"),
        ],
    },
    "autumn": {
        "name": "Autumn Warm (가을웜)",
        "anchor": "Terracotta",
        "palette": [
            ("Warm Ivory",       "#E8D4B0"),
            ("Light Camel",      "#C19A6B"),
            ("Honey Gold",       "#D4A017"),
            ("Mustard",          "#D4B27B"),
            ("Pumpkin",          "#C2895C"),
            ("Burnt Orange",     "#D96C4F"),
            ("Terracotta",       "#C26B4E"),
            ("Rust",             "#B5523A"),
            ("Caramel Brown",    "#8D5A3F"),
            ("Dark Brown",       "#6B4F3A"),
            ("Tobacco Brown",    "#A78867"),
            ("Olive Green",      "#7A8E5C"),
            ("Moss Green",       "#8B956D"),
            ("Forest Green",     "#2E5E4E"),
            ("Wine Red",         "#7A2E2E"),
            ("Deep Burgundy",    "#7C2C2C"),
            ("Khaki",            "#7C7A4E"),
        ],
    },
    "winter": {
        "name": "Winter Cool (겨울쿨)",
        "anchor": "True Red",
        "palette": [
            ("Pure White",       "#FFFFFF"),
            ("Black",            "#1E1E2E"),
            ("Charcoal",         "#36454F"),
            ("Cool Off-White",   "#F2F3F5"),
            ("Ice Blue",         "#46A0AC"),
            ("Royal Blue",       "#3F4F8B"),
            ("Sapphire",         "#1B3F88"),
            ("Cobalt",           "#2451B8"),
            ("Icy Pink",         "#E0BBE4"),
            ("Fuchsia",          "#C71F7E"),
            ("Magenta",          "#E63D63"),
            ("True Red",         "#C71F37"),
            ("Pure Red",         "#D81E3F"),
            ("Burgundy",         "#7A1F4F"),
            ("Emerald",          "#008F5C"),
            ("Forest Green",     "#1B5E20"),
            ("Violet",           "#5C3A88"),
        ],
    },
}


def build_prompt(season_label: str, top: tuple, palette: list) -> str:
    top_name, top_hex = top
    pants_list = ", ".join(f"cell {i+1}: {n} ({h})" for i, (n, h) in enumerate(palette))
    return (
        f"Flat-lay fashion product photography grid on pure white background, "
        f"arranged in 4 rows and 5 columns layout (total 20 cells, the last 3 cells in the bottom row are empty/blank). "
        f"Each filled cell contains a folded crew-neck cotton t-shirt on the left side and "
        f"a pair of folded cotton chinos pants on the right side, neatly arranged, top-down view. "
        f"This is a {season_label} personal color palette reference grid. "
        f"The t-shirt color is the SAME in all 17 filled cells: {top_name} ({top_hex}). "
        f"The pants color VARIES by cell, in this exact order from top-left to bottom-right "
        f"(reading left-to-right, top-to-bottom): {pants_list}. "
        f"Each outfit in each cell follows this order so that you see all 17 different pants colors "
        f"paired with the same {top_name} t-shirt. "
        f"Style: Pinterest minimal fashion catalog, soft natural light, professional product photo, "
        f"e-commerce look, no model, no text, no shadow, no watermark, no logo, no mannequin, "
        f"clean centered composition, white borders between cells."
    )


def main() -> int:
    out_dir = Path(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\docs\golden-set\outfits\personal_color")
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = out_dir / "_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)

    REF_PATH = "C:\\Users\\Playdata\\Desktop\\SKN28-FINAL-1Team\\docs\\golden-set\\assets\\pinterest_ref.jpg"

    requests = []
    for season_key, season in SEASONS.items():
        top = next(c for c in season["palette"] if c[0] == season["anchor"])
        fname = f"outfit_pc_{season_key}_{top[0].lower().replace(' ', '_')}.png"
        requests.append({
            "prompt": build_prompt(season["name"], top, season["palette"]),
            "output_file_path": str(out_dir / fname),
            "input_file_paths": [REF_PATH],
            "aspect_ratio": "1:1",
            "resolution": "1K",
        })
        print(f"  {season['name']:25s} → {fname} (anchor: {top[0]} {top[1]})")

    BATCH = 4
    batches = [requests[i:i + BATCH] for i in range(0, len(requests), BATCH)]
    for bi, batch in enumerate(batches):
        out_path = batch_dir / f"pc_batch_{bi:02d}.json"
        out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nOK: {len(requests)} PC grids, {len(batches)} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
