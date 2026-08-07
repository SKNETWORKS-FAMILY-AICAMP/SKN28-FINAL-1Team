"""v2 color_rules.json 빌드 + 매트릭스 등급 산출.

v1(한국어 17색) → v2(영문 17색) 완전 교체.

**등급의 출처는 레퍼런스 이미지가 아니라 아래 규칙이다.** 레퍼런스는 팔레트(어떤 17색을
쓸지)만 제공했다. 이미지에서 등급표를 추출한 grade_map_extracted.json과 대조해 봤으나
셀 검출이 실패해(7개 행이 단일 값으로 뭉개짐, na 27칸) 검증 기준으로 쓸 수 없었다.
→ tools/crosscheck_grade_map.py 참조.

등급 산출 규칙:
  - R1: 뉴트럴 2색 + 명도차 ≥ 18 → recommended, < 18 → allowed (소재로 보완)
  - R2: (neutral) × (accent|warm|cool) → recommended
  - R3: (warm accent) × (cool accent) + 양쪽 chroma ≥ 45 → avoid
  - R4: hue 차이 ≤ 35 + 명도차 < 18 → caution (유사색 뭉개짐)
  - R5: 보색(hue 차이 ≥ 150) + 한쪽 chroma < 25 → allowed
  - R6: warm × cool + 양쪽 accent → caution (뉴트럴 분리 필요)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


COLORS_V2: dict[str, dict] = {
    "Black":        {"hex": "#000000", "role": "neutral",      "temperature": "neutral", "visual_effect": "축소"},
    "White":        {"hex": "#FFFFFF", "role": "neutral",      "temperature": "neutral", "visual_effect": "확장"},
    "Charcoal":     {"hex": "#36454F", "role": "neutral",      "temperature": "cool",    "visual_effect": "축소"},
    "Navy":         {"hex": "#1B2444", "role": "neutral",      "temperature": "cool",    "visual_effect": "축소"},
    "Beige":        {"hex": "#E8DCC4", "role": "neutral",      "temperature": "warm",    "visual_effect": "확장"},
    "Olive":        {"hex": "#6B6B45", "role": "semi_neutral", "temperature": "warm",    "visual_effect": "축소"},
    "Brown":        {"hex": "#6B4A2F", "role": "semi_neutral", "temperature": "warm",    "visual_effect": "축소"},
    "Burgundy":     {"hex": "#800020", "role": "accent",       "temperature": "warm",    "visual_effect": "중립"},
    "Mustard":      {"hex": "#D4A017", "role": "accent",       "temperature": "warm",    "visual_effect": "중립"},
    "Teal":         {"hex": "#008080", "role": "accent",       "temperature": "cool",    "visual_effect": "중립"},
    "Gray":         {"hex": "#808080", "role": "neutral",      "temperature": "neutral", "visual_effect": "중립"},
    "Cream":        {"hex": "#F5E6CC", "role": "neutral",      "temperature": "warm",    "visual_effect": "확장"},
    "Rust":         {"hex": "#B7410E", "role": "accent",       "temperature": "warm",    "visual_effect": "중립"},
    "Forest Green": {"hex": "#228B22", "role": "accent",       "temperature": "cool",    "visual_effect": "중립"},
    "Lavender":     {"hex": "#B57EDC", "role": "accent",       "temperature": "cool",    "visual_effect": "확장"},
    "Light Blue":   {"hex": "#ADD8E6", "role": "accent",       "temperature": "cool",    "visual_effect": "확장"},
    "Blush Pink":   {"hex": "#FFB6C1", "role": "accent",       "temperature": "warm",    "visual_effect": "확장"},
    # 파랑 계열이 Navy(L*15)와 Light Blue(L*84)뿐이라 그 사이가 비어 있었다.
    # 아이템 태그 '블루'(데님 포함)가 Navy로 폴백되면서 accent가 neutral 앵커로,
    # 밝은 워싱 데님이 '축소'색으로 잘못 분류됐다. 중간 명도 파랑을 채워 해소한다.
    "Blue":         {"hex": "#2A5CAA", "role": "accent",       "temperature": "cool",    "visual_effect": "중립"},
}


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_xyz(r: int, g: int, b: int) -> tuple[float, float, float]:
    rl, gl, bl = srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)
    return (
        0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl,
        0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl,
        0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl,
    )


def xyz_to_lab(x: float, y: float, z: float) -> tuple[float, float, float]:
    xn, yn, zn = 0.95047, 1.0, 1.08883
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27) * t / 116 + 16 / 116
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def lab_to_lch(L: float, a: float, b: float) -> tuple[float, float, float]:
    return L, math.sqrt(a * a + b * b), math.degrees(math.atan2(b, a)) % 360


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    L = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, L * 100
    d = mx - mn
    S = d / (2 - mx - mn) if L > 0.5 else d / (mx + mn)
    if mx == rf:
        H = (gf - bf) / d + (6 if gf < bf else 0)
    elif mx == gf:
        H = (bf - rf) / d + 2
    else:
        H = (rf - gf) / d + 4
    return H * 60, S * 100, L * 100


def enrich(color_def: dict) -> dict:
    r, g, b = hex_to_rgb(color_def["hex"])
    x, y, z = rgb_to_xyz(r, g, b)
    L, a, bv = xyz_to_lab(x, y, z)
    _, C, H = lab_to_lch(L, a, bv)
    Hh, Sh, Lh = rgb_to_hsl(r, g, b)
    out = dict(color_def)
    out.update(
        hue=round(H, 1),
        chroma=round(C, 1),
        lightness=round(L, 1),
        hsl_hue=round(Hh, 1),
        hsl_saturation=round(Sh, 1),
        hsl_lightness=round(Lh, 1),
        rgb=[r, g, b],
    )
    return out


def hue_diff(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def grade_pair(a: dict, b: dict, th: dict) -> tuple[str, str, str]:
    """Return (grade, reason, rule)."""
    if a["name"] == b["name"]:
        return "na", "동일 색상 (모노톤)", "—"
    L_diff = abs(a["lightness"] - b["lightness"])
    H_diff = hue_diff(a["hue"], b["hue"])
    both_neutral = a["role"] == "neutral" and b["role"] == "neutral"
    any_neutral = a["role"] == "neutral" or b["role"] == "neutral"
    both_warm = a["temperature"] == "warm" and b["temperature"] == "warm"
    both_cool = a["temperature"] == "cool" and b["temperature"] == "cool"
    warm_cool = a["temperature"] != b["temperature"] and "neutral" not in (a["temperature"], b["temperature"])
    both_accent = a["role"] == "accent" and b["role"] == "accent"
    both_high_chroma = a["chroma"] >= th["chroma_high"] and b["chroma"] >= th["chroma_high"]

    if both_neutral:
        if L_diff >= th["lightness_contrast_min"]:
            return "recommended", f"뉴트럴 조합, 명도차 {L_diff:.0f}", "R1"
        return "allowed", f"톤온톤, 명도차 {L_diff:.0f} — 소재로 차이를 준다", "R1"

    if any_neutral:
        return "recommended", "뉴트럴 앵커 + 포인트 1색", "R2"

    if both_accent and both_high_chroma and H_diff >= th["hue_complement_min"]:
        return "avoid", f"고채도 보색(색상차 {H_diff:.0f}°) — 대면적 동시 사용 금지", "R3"

    if both_accent and both_high_chroma and H_diff <= th["hue_similar_max"]:
        if L_diff < th["lightness_contrast_min"]:
            return "caution", f"고채도 유사색(색상차 {H_diff:.0f}°, 명도차 {L_diff:.0f}) — 명도 분리 필요", "R4"
        return "recommended", f"고채도 유사색(색상차 {H_diff:.0f}°, 명도차 {L_diff:.0f})", "R4"

    if both_accent and H_diff >= th["hue_complement_min"]:
        if a["chroma"] < 25 or b["chroma"] < 25:
            return "allowed", f"보색이지만 한쪽 채도가 낮아 완충됨(색상차 {H_diff:.0f}°)", "R5"
        return "caution", f"보색(색상차 {H_diff:.0f}°) — 한쪽을 소면적으로", "R3"

    if both_accent and warm_cool and not both_warm and not both_cool:
        return "caution", "웜·쿨 혼합 — 사이에 뉴트럴을 넣어 분리", "R6"

    if H_diff <= th["hue_similar_max"] and L_diff < th["lightness_contrast_min"]:
        return "caution", f"유사색인데 명도까지 붙어 뭉개짐(색상차 {H_diff:.0f}°)", "R4"

    return "recommended", f"색상차 {H_diff:.0f}°, 명도차 {L_diff:.0f}", "R2"


def main() -> int:
    enriched = {name: {**enrich(d), "name": name} for name, d in COLORS_V2.items()}
    enriched_v2 = {name: {k: v for k, v in d.items() if k != "name"} for name, d in enriched.items()}

    th = {"chroma_high": 45.0, "lightness_contrast_min": 18.0, "hue_similar_max": 35.0, "hue_complement_min": 150.0}

    names = list(enriched.keys())
    pair_grades: dict[str, dict] = {}
    for i, na in enumerate(names):
        for nb in names[i + 1:]:
            a, b = enriched[na], enriched[nb]
            grade, reason, rule = grade_pair(a, b, th)
            pair_grades[f"{na}|{nb}"] = {"grade": grade, "reason": reason, "rule": rule}
            pair_grades[f"{nb}|{na}"] = {"grade": grade, "reason": reason, "rule": rule}

    matrix = {}
    for na in names:
        row = {}
        for nb in names:
            if na == nb:
                row[nb] = {"grade": "na", "reason": "동일 색상 (모노톤)", "rule": "—"}
            else:
                row[nb] = pair_grades[f"{na}|{nb}"]
        matrix[na] = row

    out = {
        "palette_source": "코디 색조합 레퍼런스 이미지 (assets/pinterest_ref.jpg) — 17색 팔레트만 차용",
        "grade_source": "이 스크립트의 규칙 R1~R6 계산값. 레퍼런스 등급표는 추출 실패로 미사용 (tools/crosscheck_grade_map.py)",
        "item_tag_mapping": "rules/color_taxonomy_map.json — 아이템의 한국어 color 태그를 이 팔레트로 변환",
        "generated_by": "golden-set/color/tools/build_color_rules.py",
        "version": "v2",
        "replaces_v1": "v1_backup/color_rules_v1.json (한국어 17색, taxonomy.py::COLORS 기반)",
        "thresholds": th,
        "rules": {
            "R1": "뉴트럴 2색은 명도차 18 이상이면 권장, 미만이면 소재 대비로 보완",
            "R2": "뉴트럴 앵커 1 + 포인트 1색이 기본형",
            "R3": "고채도 2색 동시 대면적 금지, 보색이면 기피",
            "R4": "유사색은 명도차 18 이상일 때만 권장",
            "R5": "보색이라도 한쪽 채도가 낮으면 허용",
            "R6": "웜·쿨 혼합은 뉴트럴을 사이에 넣어 분리",
        },
        "attributes": enriched_v2,
        "pair_grades": pair_grades,
        "matrix": matrix,
    }

    repo_root = Path(__file__).resolve().parents[1]
    json_path = repo_root / "rules" / "color_rules.json"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: wrote {json_path} ({json_path.stat().st_size} bytes)")
    print(f"  - {len(enriched_v2)} colors")
    print(f"  - {len(pair_grades) // 2} unique pair grades")
    grades = [p["grade"] for p in pair_grades.values() if p["rule"] != "—"]
    from collections import Counter
    cnt = Counter(grades)
    print(f"  - grade distribution: {dict(cnt)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
