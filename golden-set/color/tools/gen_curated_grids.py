"""v3: Shade-Aware Curated Matching 시스템.

기존 v2의 문제:
  - 17색 고정이 모든 상의에 동일하게 매칭됨
  - 예: "노란색" 1개 = Beige에도 Brown에도 동일하게 사용
  - 하지만 실제로는 Beige용 옅은 노랑 vs Brown용 진한 머스타드가 다름

v3 접근:
  - 17 top colors (기존과 동일)
  - 4시즌 팔레트 68색을 expanded bottoms 풀(pool)로 사용
  - 각 top에 6개의 CURATED best matches (shade-aware)
  - 각 매칭은 색온도(warm/cool) + 명도(light/dark) + 채도(bright/muted) 고려

출력:
  - 17 grids (one per top), 각 3×3 (6 outfits + 3 empty)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# 17 top colors (from v2 grade map, 영문)
TOPS = [
    "Black", "White", "Charcoal", "Navy", "Beige", "Olive", "Brown",
    "Burgundy", "Mustard", "Teal", "Gray", "Cream", "Rust",
    "Forest Green", "Lavender", "Light Blue", "Blush Pink",
]


# Expanded palette: 4시즌 × 17색 = 68색 (shade variety를 위해)
# 각 색은 (이름, hex, season, role) 튜플
EXPANDED_PALETTE = {
    # ===== NEUTRALS (여러 시즌 공통) =====
    "Black":            ("#1E1E2E", "winter", "neutral"),
    "Pure White":       ("#FFFFFF", "winter", "neutral"),
    "Charcoal":         ("#36454F", "winter", "neutral"),
    "Soft Charcoal":    ("#565B63", "summer", "neutral"),
    "Slate Gray":       ("#667FA3", "summer", "neutral"),
    "Light Gray":       ("#A9AEB4", "summer", "neutral"),
    "Silver":           ("#C0C7D1", "summer", "neutral"),
    "Soft White":       ("#F2F3F5", "winter", "neutral"),
    "Moonlight White":  ("#EAEFF5", "summer", "neutral"),
    "Warm White":       ("#FAF7F0", "spring", "neutral"),
    "Cream":            ("#F5E6CC", "spring", "neutral"),
    "Cream Yellow":     ("#FFF1D6", "spring", "neutral"),
    "Cool White":       ("#F4F5F5", "summer", "neutral"),
    "Soft Beige":       ("#D9C3A5", "spring", "neutral"),
    "Light Camel":      ("#C19A6B", "autumn", "neutral"),
    "Taupe":            ("#8F8377", "summer", "neutral"),
    "Stone":            ("#B8A99A", "summer", "neutral"),
    "Dark Gray":        ("#3C3F46", "summer", "neutral"),
    "Mushroom":         ("#B8A99A", "summer", "neutral"),
    "Tobacco Brown":    ("#A78867", "autumn", "neutral"),
    "Beige":            ("#D9C3A5", "spring", "neutral"),
    "Ivory":            ("#F2E8D5", "spring", "neutral"),

    # ===== BROWNS (다양한 shade) =====
    "Caramel":          ("#C68642", "spring", "brown"),
    "Honey Brown":      ("#C68642", "spring", "brown"),
    "Golden Camel":     ("#C99A5B", "spring", "brown"),
    "Light Brown":      ("#8D5A3F", "autumn", "brown"),
    "Caramel Brown":    ("#8D5A3F", "autumn", "brown"),
    "Brown":            ("#6B4F3A", "autumn", "brown"),
    "Dark Brown":       ("#4A2F22", "autumn", "brown"),
    "Chocolate":        ("#3A2418", "autumn", "brown"),

    # ===== YELLOWS (다양한 shade) =====
    "Butter Yellow":    ("#F7D86A", "spring", "yellow"),
    "Cream Yellow2":    ("#FFE4B5", "spring", "yellow"),  # moccasin
    "Pale Yellow":      ("#FFE066", "spring", "yellow"),
    "Light Gold":       ("#F5C542", "spring", "yellow"),
    "Golden Yellow":    ("#F5C542", "spring", "yellow"),
    "Marigold":         ("#F4A51C", "spring", "yellow"),
    "Mustard":          ("#D4A017", "autumn", "yellow"),
    "Ochre":            ("#C2895C", "autumn", "yellow"),
    "Honey Gold":       ("#D4A017", "autumn", "yellow"),
    "Dark Mustard":     ("#B8860B", "autumn", "yellow"),

    # ===== GREENS (다양한 shade) =====
    "Fresh Mint":       ("#9FD8B5", "spring", "green"),
    "Apple Green":      ("#7CB342", "spring", "green"),
    "Grass Green":      ("#54A24B", "spring", "green"),
    "Light Olive":      ("#8B956D", "autumn", "green"),
    "Olive":            ("#6B6B45", "autumn", "green"),
    "Olive Green":      ("#7A8E5C", "autumn", "green"),
    "Moss Green":       ("#8B956D", "autumn", "green"),
    "Sage":             ("#9CB3A0", "summer", "green"),
    "Eucalyptus":       ("#789486", "summer", "green"),
    "Soft Teal":        ("#6F9A9A", "summer", "green"),
    "Forest Green":     ("#2E5E4E", "autumn", "green"),
    "Pine Green":       ("#4F7C72", "summer", "green"),
    "Emerald":          ("#008F5C", "winter", "green"),
    "Dark Forest":      ("#1B5E20", "winter", "green"),

    # ===== BLUES (다양한 shade) =====
    "Powder Blue":      ("#9EC9E2", "summer", "blue"),
    "Periwinkle":       ("#8FA8D8", "summer", "blue"),
    "Sky Blue":         ("#A8D8EA", "spring", "blue"),
    "Light Blue":       ("#ADD8E6", "summer", "blue"),
    "Soft Aqua":        ("#68C7C1", "spring", "blue"),
    "Warm Turquoise":   ("#28B7A8", "spring", "blue"),
    "Mist Blue":        ("#9CB3C7", "summer", "blue"),
    "Dusty Blue":       ("#7BA4D9", "summer", "blue"),
    "Slate Blue":       ("#667FA3", "summer", "blue"),
    "Navy":             ("#1F2A44", "winter", "blue"),
    "Royal Blue":       ("#3F4F8B", "winter", "blue"),
    "Sapphire":         ("#1B3F88", "winter", "blue"),
    "Cobalt":           ("#2451B8", "winter", "blue"),
    "Teal":             ("#008080", "winter", "blue"),
    "Ice Blue":         ("#46A0AC", "winter", "blue"),
    "Dark Teal":        ("#177E7A", "spring", "blue"),

    # ===== REDS (다양한 shade) =====
    "Coral":            ("#FF6F61", "spring", "red"),
    "Light Coral":      ("#FF8F7A", "spring", "red"),
    "Salmon":           ("#FA8072", "spring", "red"),
    "Tomato Red":       ("#E94B35", "spring", "red"),
    "Pumpkin":          ("#C2895C", "autumn", "red"),
    "Burnt Orange":     ("#D96C4F", "autumn", "red"),
    "Terracotta":       ("#C26B4E", "autumn", "red"),
    "Rust":             ("#B5523A", "autumn", "red"),
    "Pure Red":         ("#D81E3F", "winter", "red"),
    "True Red":         ("#C71F37", "winter", "red"),
    "Crimson":          ("#DC143C", "winter", "red"),
    "Wine Red":         ("#7A2E2E", "autumn", "red"),
    "Burgundy":         ("#7A1F4F", "winter", "red"),
    "Deep Burgundy":    ("#7C2C2C", "autumn", "red"),

    # ===== PINKS (다양한 shade) =====
    "Soft Pink":        ("#F4D2DA", "summer", "pink"),
    "Powder Pink":      ("#E9B7C7", "summer", "pink"),
    "Rosewater":        ("#DFA0B6", "summer", "pink"),
    "Dusty Rose":       ("#C9869A", "summer", "pink"),
    "Soft Rose":        ("#C894A0", "summer", "pink"),
    "Mauve":            ("#B57B9A", "summer", "pink"),
    "Hot Pink":         ("#FF6F91", "spring", "pink"),
    "Fuchsia":          ("#C71F7E", "winter", "pink"),
    "Magenta":          ("#E63D63", "winter", "pink"),
    "Blush Pink":       ("#FFB6C1", "summer", "pink"),
    "Rose Beige":       ("#E8C8DC", "summer", "pink"),

    # ===== PURPLES (다양한 shade) =====
    "Cool Lavender":    ("#B7A7D8", "summer", "purple"),
    "Soft Lilac":       ("#D8BFD8", "summer", "purple"),
    "Lavender":         ("#B57EDC", "summer", "purple"),
    "Periwinkle Purple":("#8FA8D8", "summer", "purple"),
    "Lavender Gray":    ("#A99AC4", "summer", "purple"),
    "Soft Plum":        ("#6F4E73", "summer", "purple"),
    "Violet":           ("#5C3A88", "winter", "purple"),
    "Aubergine":        ("#4A2C4A", "winter", "purple"),
}


# ============================================================
# Curated matching rules: 각 top에 6 best bottoms (shade-aware)
# 색 family별로 다른 shade를 사용
# ============================================================
CURATED_MATCHES = {
    # === Black: most versatile, dark accent 가능 ===
    "Black": [
        "Charcoal",      # tonal
        "Pure White",    # high contrast
        "Soft White",    # soft contrast
        "True Red",      # classic bold
        "Royal Blue",    # high contrast
        "Mustard",       # warm pop
    ],

    # === White: 매우 versatile, 거의 모든 색 OK. soft pairings 우선 ===
    "White": [
        "Cream Yellow",   # tonal warm
        "Soft Beige",     # tonal neutral
        "Honey Brown",    # warm neutral
        "Powder Blue",    # cool soft
        "Light Coral",    # warm soft
        "Sage",           # soft green
    ],

    # === Charcoal: dark cool, lighter tones 매칭 ===
    "Charcoal": [
        "Pure White",
        "Light Gray",
        "Soft Charcoal",
        "Mustard",        # warm pop
        "Deep Burgundy",  # dark warm
        "Powder Blue",    # cool soft
    ],

    # === Navy: dark cool, warm + light 매칭 ===
    "Navy": [
        "Pure White",     # classic
        "Soft White",     # soft
        "Cream Yellow",   # warm light
        "Light Camel",    # warm
        "Light Coral",    # warm pop
        "Mustard",        # warm contrast
    ],

    # === Beige: light warm, CREAM YELLOW (NOT mustard) - shade-aware! ===
    "Beige": [
        "Ivory",          # tonal
        "Soft Beige",     # tonal
        "Cream Yellow",   # Beige's OWN yellow (light warm)
        "Light Coral",    # warm pop
        "Honey Brown",    # warm brown family (NOT dark)
        "Fresh Mint",     # soft green
    ],

    # === Olive: medium warm green, BROWN 계열 매칭 ===
    "Olive": [
        "Cream",          # light
        "Ivory",          # light
        "Light Camel",    # warm
        "Light Brown",    # BROWN family shade
        "Caramel",        # warm brown
        "Burgundy",       # dark warm
    ],

    # === Brown: medium warm, MUSTARD/TERRACOTTA (NOT butter yellow) - shade-aware! ===
    "Brown": [
        "Caramel",        # tonal
        "Light Brown",    # tonal
        "Mustard",        # Brown's OWN yellow (deep warm)
        "Ochre",          # deep warm
        "Terracotta",     # warm pop
        "Cream",          # light contrast
    ],

    # === Burgundy: dark warm red, CREAM/MUSTARD 매칭 ===
    "Burgundy": [
        "Cream Yellow",   # soft warm
        "Ivory",          # light
        "Soft Beige",     # light warm
        "Mustard",        # warm pop
        "Olive",          # warm dark
        "Teal",           # cool pop
    ],

    # === Mustard: medium warm yellow, OLIVE/BROWN 매칭 ===
    "Mustard": [
        "Olive",          # warm green
        "Light Olive",    # soft warm
        "Caramel",        # warm brown
        "Burgundy",       # dark warm
        "Cream",          # light
        "Navy",           # cool pop
    ],

    # === Teal: cool green-blue, WARM 매칭 ===
    "Teal": [
        "Cream",          # light warm
        "Ivory",          # light
        "Terracotta",     # warm pop
        "Burnt Orange",   # warm pop
        "Mustard",        # warm yellow
        "Burgundy",       # dark warm
    ],

    # === Gray: cool neutral, versatile ===
    "Gray": [
        "Pure White",
        "Charcoal",
        "Light Gray",
        "Mustard",        # warm pop
        "Burgundy",       # dark pop
        "Royal Blue",     # cool pop
    ],

    # === Cream: light warm, VERY versatile ===
    "Cream": [
        "Soft Beige",     # tonal
        "Light Camel",    # warm
        "Sage",           # soft cool
        "Powder Blue",    # soft cool
        "Dusty Rose",     # soft warm
        "Caramel",        # warm
    ],

    # === Rust: dark warm orange, CREAM/BROWN 매칭 ===
    "Rust": [
        "Cream",          # light
        "Ivory",          # light
        "Caramel",        # warm
        "Mustard",        # warm yellow
        "Brown",          # tonal
        "Navy",           # cool pop
    ],

    # === Forest Green: dark warm green, BROWN/BURGUNDY 매칭 ===
    "Forest Green": [
        "Cream",          # light
        "Ivory",          # light
        "Caramel",        # warm
        "Mustard",        # warm yellow
        "Burgundy",       # dark warm
        "Tobacco Brown",  # warm brown
    ],

    # === Lavender: light cool purple, SOFT tones 매칭 ===
    "Lavender": [
        "Pure White",     # classic
        "Soft White",     # soft
        "Powder Pink",    # soft cool
        "Powder Blue",    # soft cool
        "Light Gray",     # soft cool
        "Sage",           # soft cool
    ],

    # === Light Blue: light cool, COOL softs 매칭 ===
    "Light Blue": [
        "Pure White",
        "Cream Yellow",   # soft warm
        "Soft Beige",     # light
        "Powder Pink",    # soft cool
        "Light Gray",     # soft
        "Light Coral",    # warm pop
    ],

    # === Blush Pink: light warm pink, COOL softs 매칭 ===
    "Blush Pink": [
        "Pure White",     # classic
        "Soft White",     # soft
        "Light Gray",     # soft
        "Powder Blue",    # soft cool
        "Sage",           # soft cool
        "Soft Beige",     # light warm
    ],
}


# v2 top color → expanded palette key 매핑 (top 색이 expanded에도 있는지 확인)
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
    "Cream":        "#F2E8D5",
    "Rust":         "#B5523A",
    "Forest Green": "#2E5E4E",
    "Lavender":     "#B57EDC",
    "Light Blue":   "#ADD8E6",
    "Blush Pink":   "#FFB6C1",
}


def build_curated_prompt(top: str, bottoms: list[str]) -> str:
    top_hex = TOP_HEX[top]
    top_hint = "consistent across all 6 cells"
    bottoms_list = ", ".join(f"cell {i+1}: {b} ({EXPANDED_PALETTE[b][0]})" for i, b in enumerate(bottoms))
    return (
        f"Flat-lay fashion product photography grid on pure white background, "
        f"arranged in 3 rows and 3 columns layout (total 9 cells, the last 3 cells in the bottom row are empty/blank). "
        f"Each filled cell contains a folded crew-neck cotton t-shirt on the left side and "
        f"a pair of folded cotton chinos pants on the right side, neatly arranged, top-down view. "
        f"The t-shirt color is the SAME in all 6 filled cells: {top} ({top_hex}). "
        f"The pants color VARIES by cell, in this exact order from top-left to bottom-right "
        f"(reading left-to-right, top-to-bottom): {bottoms_list}. "
        f"Each outfit in each cell follows this order so that you see 6 different pants colors "
        f"carefully curated to match the {top} t-shirt. "
        f"These 6 colors are specifically chosen for fashion color harmony with {top}, "
        f"not random color combinations. "
        f"Style: Pinterest minimal fashion catalog, soft natural light, professional product photo, "
        f"e-commerce look, no model, no text, no shadow, no watermark, no logo, no mannequin, "
        f"clean centered composition, white borders between cells."
    )


def main() -> int:
    out_dir = Path(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\docs\golden-set\outfits\curated")
    out_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = out_dir / "_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)

    REF_PATH = "C:\\Users\\Playdata\\Desktop\\SKN28-FINAL-1Team\\docs\\golden-set\\assets\\pinterest_ref.jpg"

    # 매칭 규칙 JSON 저장
    rules = {
        "version": "v3",
        "philosophy": "shade-aware curated matching: 각 top에 6 best bottoms, 색 family 내에서도 shade 차이 적용",
        "tops": TOPS,
        "expanded_palette_size": len(EXPANDED_PALETTE),
        "matches": {
            top: {
                "tops": [{"name": top, "hex": TOP_HEX[top]}],
                "bottoms": [
                    {"name": b, "hex": EXPANDED_PALETTE[b][0], "season": EXPANDED_PALETTE[b][1]}
                    for b in bottoms
                ],
            }
            for top, bottoms in CURATED_MATCHES.items()
        },
    }
    rules_path = out_dir / "curated_matching_rules.json"
    rules_path.write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: rules saved to {rules_path}")

    # image_synthesize 요청 생성
    requests = []
    for top in TOPS:
        bottoms = CURATED_MATCHES[top]
        fname = f"outfit_curated_{top.lower().replace(' ', '_')}.png"
        requests.append({
            "prompt": build_curated_prompt(top, bottoms),
            "output_file_path": str(out_dir / fname),
            "input_file_paths": [REF_PATH],
            "aspect_ratio": "1:1",
            "resolution": "1K",
        })
        print(f"  {top:14s} → {fname}  (6 bottoms: {bottoms})")

    # 배치로 분할 (한 호출에 10개씩)
    BATCH = 10
    batches = [requests[i:i + BATCH] for i in range(0, len(requests), BATCH)]
    for bi, batch in enumerate(batches):
        out_path = batch_dir / f"curated_batch_{bi:02d}.json"
        out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nOK: {len(requests)} curated grids, {len(batches)} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
