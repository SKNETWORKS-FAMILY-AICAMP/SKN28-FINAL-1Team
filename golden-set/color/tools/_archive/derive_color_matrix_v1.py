"""17색 taxonomy의 색 속성과 17x17 조합 등급을 규칙에서 생성한다.

색 조합표를 손으로 289칸 적으면 (1) 서로 모순된 칸이 반드시 생기고
(2) "왜 이 조합이 기피인가"에 답할 수 없다. 그래서 이 파일은
**색 속성(HSL) + 조합 규칙 6개**만 정의하고 등급은 전부 계산한다.
규칙을 바꾸면 표 전체가 일관되게 다시 만들어지는 것이 핵심이다.

색 이름은 image-processor/pipeline/taxonomy.py의 COLORS와 1:1로 맞춘다
(옷장·상품 아이템에 실제로 붙는 태그가 그것이기 때문).

출력:
docs/golden-set/rules/color_rules.json      — 속성 + 등급 + 규칙 메타
docs/golden-set/rules/color_matrix.md       — 사람이 읽는 17x17 표 (생성물)

실행:
    python docs/golden-set/tools/derive_color_matrix.py
"""
from __future__ import annotations

import colorsys
import json
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "docs/golden-set/rules/color_rules.json"
OUT_MD = ROOT / "docs/golden-set/rules/color_matrix.md"

# taxonomy COLORS 17개의 대표 색상값.
# "그 이름으로 태깅될 옷들의 중앙값"에 해당하는 값을 골랐다 — 예를 들어 레드는
# 형광 빨강(#FF0000)이 아니라 의류에서 흔한 톤다운 레드다. 이 선택이 채도 판정을
# 좌우하므로 값 변경 시 매트릭스 전체가 바뀐다는 점에 유의.
HEX = {
    "화이트": "#FFFFFF",
    "아이보리": "#F2E8D5",
    "베이지": "#D9C3A5",
    "그레이": "#9A9A9A",
    "블랙": "#1A1A1A",
    "네이비": "#1F2A44",
    "블루": "#2A5CAA",
    "스카이블루": "#8FC5E8",
    "그린": "#3F7A45",
    "카키": "#6B6B45",
    "브라운": "#6B4A2F",
    "레드": "#C62828",
    "핑크": "#F0A0B4",
    "오렌지": "#E8712F",
    "옐로우": "#F2C744",
    "퍼플": "#7A4A93",
}
MULTI = "멀티"  # 패턴 다색 아이템 — 단일 HSL로 표현 불가라 규칙에서 특수 처리

# 무채색/저채도라 어떤 색과도 충돌하지 않는 '앵커' 색.
# 룩의 색 부담을 흡수하는 역할을 해서, 대면적(상·하의)에 우선 배치한다.
NEUTRALS = {"화이트", "아이보리", "베이지", "그레이", "블랙", "네이비"}
# 채도는 낮지만 색상(hue)이 뚜렷해 완전 중립은 아닌 색. 뉴트럴 대용은 되지만
# 3색 규칙에서는 유채색으로 센다.
SEMI_NEUTRALS = {"카키", "브라운"}

CHROMA_HIGH = 45.0     # 이 이상이면 '고채도' — 대면적 2개 이상이면 시선 분산
LIGHT_CONTRAST = 18.0  # 상·하의 명도차 최소치. 미만이면 실루엣 경계가 뭉개진다
HUE_SIMILAR = 35.0     # 유사색 범위(도)
HUE_COMPLEMENT = 150.0 # 이 이상 벌어지면 보색 대비로 간주


def to_hsl(hex_code: str) -> tuple[float, float, float, float]:
    """hue, HSL 채도, 명도, **chroma**를 반환한다.

    HSL 채도를 그대로 쓰면 안 되는 이유: 아이보리(#F2E8D5)의 HSL 채도는 52.7로
    나오지만 눈에는 거의 무채색이다. HSL은 명도가 극단으로 갈수록 채도를 부풀린다.
    chroma = max(RGB) - min(RGB)는 실제로 색이 얼마나 도는지를 나타내므로,
    '고채도 2색 충돌' 판정은 반드시 chroma로 한다.
    """
    r, g, b = (int(hex_code[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, ligh, sat = colorsys.rgb_to_hls(r, g, b)
    chroma = max(r, g, b) - min(r, g, b)
    return round(h * 360, 1), round(sat * 100, 1), round(ligh * 100, 1), round(chroma * 100, 1)


def temperature(hue: float, chroma: float) -> str:
    if chroma < 12:
        return "neutral"
    if hue < 75 or hue >= 330:
        return "warm"
    if 180 <= hue < 300:
        return "cool"
    return "neutral"  # 그린~옐로우그린 구간은 착장에서 중립처럼 쓰인다


def hue_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def build_attributes() -> dict:
    attrs = {}
    for name, hex_code in HEX.items():
        hue, sat, ligh, chroma = to_hsl(hex_code)
        attrs[name] = {
            "hex": hex_code,
            "hue": hue,
            "chroma": chroma,
            "hsl_saturation": sat,
            "lightness": ligh,
            "role": "neutral" if name in NEUTRALS
            else "semi_neutral" if name in SEMI_NEUTRALS
            else "accent",
            "temperature": temperature(hue, chroma),
            # 시각적 확장/축소 — 체형 규칙이 이 값을 참조한다.
            "visual_effect": "확장" if ligh >= 70 else "축소" if ligh <= 35 else "중립",
        }
    attrs[MULTI] = {
        "hex": None, "hue": None, "chroma": None, "hsl_saturation": None, "lightness": None,
        "role": "accent", "temperature": "unknown", "visual_effect": "확장",
    }
    return attrs


def grade_pair(a: str, b: str, attrs: dict) -> dict:
    """두 색의 조합 등급과 그 사유를 반환한다.

    등급: recommended(◎) / allowed(○) / caution(△) / avoid(✕)
    """
    A, B = attrs[a], attrs[b]

    # R0. 멀티는 자기 안에 이미 여러 색을 가지고 있어, 상대가 유채색이면 색 수가 넘친다.
    if MULTI in (a, b):
        other = b if a == MULTI else a
        if other == MULTI:
            return {"grade": "avoid", "reason": "멀티끼리 — 패턴 충돌", "rule": "R0"}
        if attrs[other]["role"] == "neutral":
            return {"grade": "recommended", "reason": "멀티는 뉴트럴이 받아준다", "rule": "R0"}
        if attrs[other]["role"] == "semi_neutral":
            return {"grade": "allowed", "reason": "세미뉴트럴로 완충", "rule": "R0"}
        return {"grade": "caution", "reason": "멀티 + 유채색 — 색 수 초과 위험", "rule": "R0"}

    l_gap = abs(A["lightness"] - B["lightness"])
    both_neutral = A["role"] == "neutral" and B["role"] == "neutral"

    # R1. 뉴트럴끼리는 색 충돌이 없다. 남는 변수는 명도차뿐.
    if both_neutral:
        if l_gap >= LIGHT_CONTRAST:
            return {"grade": "recommended", "reason": f"뉴트럴 조합, 명도차 {l_gap:.0f}", "rule": "R1"}
        return {"grade": "allowed", "reason": f"톤온톤, 명도차 {l_gap:.0f} — 소재로 차이를 준다", "rule": "R1"}

    # R2. 뉴트럴 1 + 유채색 1 = 가장 안전한 기본형. 앵커가 색 부담을 흡수한다.
    if A["role"] == "neutral" or B["role"] == "neutral":
        accent = B if A["role"] == "neutral" else A
        neutral = A if A["role"] == "neutral" else B
        if accent["chroma"] >= CHROMA_HIGH and abs(neutral["lightness"] - accent["lightness"]) < 12:
            return {"grade": "allowed", "reason": "뉴트럴 앵커는 성립하나 명도가 붙어 경계가 약함", "rule": "R2"}
        return {"grade": "recommended", "reason": "뉴트럴 앵커 + 포인트 1색", "rule": "R2"}

    # 여기부터는 유채색(세미뉴트럴 포함) 2개.
    gap = hue_gap(A["hue"], B["hue"])
    hot = A["chroma"] >= CHROMA_HIGH and B["chroma"] >= CHROMA_HIGH

    # R4-우선. 같은 색상 계열이면 채도가 높아도 충돌이 아니라 톤온톤이다
    # (블루+스카이블루). 명도차만 확보되면 R3의 고채도 판정보다 앞선다.
    if gap <= HUE_SIMILAR and l_gap >= LIGHT_CONTRAST:
        return {"grade": "recommended", "reason": f"유사색 톤 그라데이션(명도차 {l_gap:.0f})", "rule": "R4"}

    # R3. 고채도 2개는 시선이 분산되고, 보색이면 진동까지 생긴다.
    if hot and gap >= HUE_COMPLEMENT:
        return {"grade": "avoid", "reason": f"고채도 보색(색상차 {gap:.0f}°) — 대면적 동시 사용 금지", "rule": "R3"}
    if hot:
        return {"grade": "caution", "reason": "고채도 2색 — 한쪽을 소면적(액세서리)으로", "rule": "R3"}

    # R4. 유사색인데 명도차까지 없으면 두 아이템의 경계가 사라진다.
    if gap <= HUE_SIMILAR:
        return {"grade": "caution", "reason": "유사색인데 명도까지 붙어 뭉개짐", "rule": "R4"}

    # R5. 보색이라도 한쪽 채도가 낮으면 대비가 완충된다.
    if gap >= HUE_COMPLEMENT:
        return {"grade": "allowed", "reason": f"보색이지만 채도가 낮아 완충됨(색상차 {gap:.0f}°)", "rule": "R5"}

    # R6. 중간 색상차 + 저채도 = 무난한 배색.
    if A["temperature"] != B["temperature"] and "neutral" not in (A["temperature"], B["temperature"]):
        return {"grade": "caution", "reason": "웜·쿨 혼합 — 사이에 뉴트럴을 넣어 분리", "rule": "R6"}
    return {"grade": "allowed", "reason": f"중간 색상차 {gap:.0f}°, 저채도라 안정", "rule": "R6"}


SYMBOL = {"recommended": "◎", "allowed": "○", "caution": "△", "avoid": "✕"}


def main() -> None:
    attrs = build_attributes()
    names = list(HEX) + [MULTI]

    pairs = {}
    for a, b in combinations(names, 2):
        pairs[f"{a}|{b}"] = grade_pair(a, b, attrs)

    counts: dict[str, int] = {}
    for v in pairs.values():
        counts[v["grade"]] = counts.get(v["grade"], 0) + 1

    payload = {
        "taxonomy_source": "image-processor/pipeline/taxonomy.py::COLORS",
        "generated_by": "docs/golden-set/tools/derive_color_matrix.py",
        "thresholds": {
            "chroma_high": CHROMA_HIGH,
            "lightness_contrast_min": LIGHT_CONTRAST,
            "hue_similar_max": HUE_SIMILAR,
            "hue_complement_min": HUE_COMPLEMENT,
        },
        "rules": {
            "R0": "멀티(다색 패턴)의 상대는 뉴트럴로 고정한다",
            "R1": "뉴트럴 2색은 명도차 18 이상이면 권장, 미만이면 소재 대비로 보완",
            "R2": "뉴트럴 앵커 1 + 포인트 1색이 기본형",
            "R3": "고채도 2색 동시 대면적 금지, 보색이면 기피",
            "R4": "유사색은 명도차 18 이상일 때만 권장",
            "R5": "보색이라도 한쪽 채도가 낮으면 허용",
            "R6": "웜·쿨 혼합은 뉴트럴을 사이에 넣어 분리",
        },
        "attributes": attrs,
        "pair_grades": pairs,
        "grade_distribution": counts,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 사람이 읽는 표 (생성물 — 직접 수정 금지)
    lines = [
        "# 색상 조합 매트릭스 (자동 생성)",
        "",
        "> `docs/golden-set/tools/derive_color_matrix.py`가 생성한다. **직접 수정하지 말 것** —",
        "> 규칙을 바꾸려면 스크립트의 임계값·규칙을 고치고 다시 실행한다.",
        "",
        "◎ 권장 · ○ 허용 · △ 주의(소면적/뉴트럴 완충 필요) · ✕ 기피",
        "",
        "| | " + " | ".join(names) + " |",
        "|" + "---|" * (len(names) + 1),
    ]
    for a in names:
        row = [f"**{a}**"]
        for b in names:
            if a == b:
                row.append("—")
                continue
            key = f"{a}|{b}" if f"{a}|{b}" in pairs else f"{b}|{a}"
            row.append(SYMBOL[pairs[key]["grade"]])
        lines.append("| " + " | ".join(row) + " |")

    lines += ["", "## 기피(✕) 조합과 사유", ""]
    lines += [f"- **{k.replace('|', ' + ')}** — {v['reason']} `[{v['rule']}]`"
              for k, v in pairs.items() if v["grade"] == "avoid"]
    lines += ["", "## 주의(△) 조합과 사유", ""]
    lines += [f"- **{k.replace('|', ' + ')}** — {v['reason']} `[{v['rule']}]`"
              for k, v in pairs.items() if v["grade"] == "caution"]
    lines += ["", f"_등급 분포: {counts}_", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(counts, ensure_ascii=False))
    print(f"wrote {OUT_JSON.name}, {OUT_MD.name}")


if __name__ == "__main__":
    main()
