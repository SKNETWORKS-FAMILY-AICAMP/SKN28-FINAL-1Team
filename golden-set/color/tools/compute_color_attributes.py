"""v2 색상 속성 계산기: hex → HCL/HLS 변환 + 룰 등급 산출.

기존 v1(한국어 17색)을 대체하는 v2(영문 17색) 시스템.
Pinterest 스타일 패션 그레이드맵 기준 17색 (Black, White, Charcoal, Navy,
Beige, Olive, Brown, Burgundy, Mustard, Teal, Gray, Cream, Rust, Forest Green,
Lavender, Light Blue, Blush Pink).

사용법:
    python compute_color_attributes.py          # 콘솔에 17색 속성 출력
    python compute_color_attributes.py --json   # color_rules.json 형태로 출력

CIELCh 변환: sRGB → linear RGB → XYZ(D65) → CIELAB → CIELCh.
"""

from __future__ import annotations

import json
import math
import sys


COLORS_V2: dict[str, dict] = {
    "Black":        {"hex": "#000000", "role": "neutral",     "temperature": "neutral", "visual_effect": "축소"},
    "White":        {"hex": "#FFFFFF", "role": "neutral",     "temperature": "neutral", "visual_effect": "확장"},
    "Charcoal":     {"hex": "#36454F", "role": "neutral",     "temperature": "cool",    "visual_effect": "축소"},
    "Navy":         {"hex": "#1B2444", "role": "neutral",     "temperature": "cool",    "visual_effect": "축소"},
    "Beige":        {"hex": "#E8DCC4", "role": "neutral",     "temperature": "warm",    "visual_effect": "확장"},
    "Olive":        {"hex": "#6B6B45", "role": "semi_neutral", "temperature": "warm",   "visual_effect": "축소"},
    "Brown":        {"hex": "#6B4A2F", "role": "semi_neutral", "temperature": "warm",   "visual_effect": "축소"},
    "Burgundy":     {"hex": "#800020", "role": "accent",       "temperature": "warm",   "visual_effect": "중립"},
    "Mustard":      {"hex": "#D4A017", "role": "accent",       "temperature": "warm",   "visual_effect": "중립"},
    "Teal":         {"hex": "#008080", "role": "accent",       "temperature": "cool",   "visual_effect": "중립"},
    "Gray":         {"hex": "#808080", "role": "neutral",      "temperature": "neutral", "visual_effect": "중립"},
    "Cream":        {"hex": "#F5E6CC", "role": "neutral",      "temperature": "warm",   "visual_effect": "확장"},
    "Rust":         {"hex": "#B7410E", "role": "accent",       "temperature": "warm",   "visual_effect": "중립"},
    "Forest Green": {"hex": "#228B22", "role": "accent",       "temperature": "cool",   "visual_effect": "중립"},
    "Lavender":     {"hex": "#B57EDC", "role": "accent",       "temperature": "cool",   "visual_effect": "확장"},
    "Light Blue":   {"hex": "#ADD8E6", "role": "accent",       "temperature": "cool",   "visual_effect": "확장"},
    "Blush Pink":   {"hex": "#FFB6C1", "role": "accent",       "temperature": "warm",   "visual_effect": "확장"},
}


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_xyz(r: int, g: int, b: int) -> tuple[float, float, float]:
    rl, gl, bl = srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)
    # sRGB D65 matrix
    x = 0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl
    y = 0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl
    z = 0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl
    return x, y, z


def xyz_to_lab(x: float, y: float, z: float) -> tuple[float, float, float]:
    # D65 reference white
    xn, yn, zn = 0.95047, 1.0, 1.08883
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27) * t / 116 + 16 / 116
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return L, a, b


def lab_to_lch(L: float, a: float, b: float) -> tuple[float, float, float]:
    C = math.sqrt(a * a + b * b)
    H = math.degrees(math.atan2(b, a)) % 360
    return L, C, H


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    L = (mx + mn) / 2
    if mx == mn:
        H = S = 0.0
    else:
        d = mx - mn
        S = d / (2 - mx - mn) if L > 0.5 else d / (mx + mn)
        if mx == rf:
            H = (gf - bf) / d + (6 if gf < bf else 0)
        elif mx == gf:
            H = (bf - rf) / d + 2
        else:
            H = (rf - gf) / d + 4
        H *= 60
    return H, S * 100, L * 100


def enrich(color_def: dict) -> dict:
    r, g, b = hex_to_rgb(color_def["hex"])
    x, y, z = rgb_to_xyz(r, g, b)
    L, a, bv = xyz_to_lab(x, y, z)
    Lch_L, C, H = lab_to_lch(L, a, bv)
    H_hsl, S_hsl, L_hsl = rgb_to_hsl(r, g, b)
    out = dict(color_def)
    out["hue"] = round(H, 1)
    out["chroma"] = round(C, 1)
    out["lightness"] = round(Lch_L, 1)
    out["hsl_hue"] = round(H_hsl, 1)
    out["hsl_saturation"] = round(S_hsl, 1)
    out["hsl_lightness"] = round(L_hsl, 1)
    out["rgb"] = [r, g, b]
    return out


def main() -> int:
    enriched = {name: enrich(def_) for name, def_ in COLORS_V2.items()}
    if "--json" in sys.argv:
        out = {
            "taxonomy_source": "Pinterest fashion color combination reference (user-provided grade map, 2026-08-06)",
            "generated_by": "golden-set/color/tools/compute_color_attributes.py",
            "version": "v2",
            "replaces_v1": "v1_backup/color_rules_v1.json (한국어 17색)",
            "thresholds": {
                "chroma_high": 45.0,
                "lightness_contrast_min": 18.0,
                "hue_similar_max": 35.0,
                "hue_complement_min": 150.0,
            },
            "rules": {
                "R1": "뉴트럴 2색은 명도차 18 이상이면 권장, 미만이면 소재 대비로 보완",
                "R2": "뉴트럴 앵커 1 + 포인트 1색이 기본형",
                "R3": "고채도 2색 동시 대면적 금지, 보색이면 기피",
                "R4": "유사색은 명도차 18 이상일 때만 권장",
                "R5": "보색이라도 한쪽 채도가 낮으면 허용",
                "R6": "웜·쿨 혼합은 뉴트럴을 사이에 넣어 분리",
            },
            "attributes": enriched,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"{'name':<14} {'hex':<8} {'L':>6} {'C':>6} {'H':>7} {'role':<14} {'temp':<8}")
        print("-" * 70)
        for name, e in enriched.items():
            print(
                f"{name:<14} {e['hex']:<8} {e['lightness']:>6.1f} {e['chroma']:>6.1f} "
                f"{e['hue']:>7.1f} {e['role']:<14} {e['temperature']:<8}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
