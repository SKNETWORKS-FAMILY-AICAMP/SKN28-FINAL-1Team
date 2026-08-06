"""color_taxonomy_map.json이 실제 두 원천과 어긋나지 않는지 검증한다.

매핑표는 손으로 쓰는 판단 산출물이라 자동 생성할 수 없다. 대신 **깨졌는지는
자동으로 알 수 있다** — taxonomy에 색이 추가되거나 v2 팔레트가 바뀌면 이 스크립트가
먼저 실패해야 한다. 그게 이 파일의 존재 이유다.

실행:
    python golden-set/color/tools/validate_color_map.py
종료코드 0 = 정합, 1 = 불일치
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TAXONOMY = ROOT / "image-processor/pipeline/taxonomy.py"
V2 = ROOT / "golden-set/color/rules/color_rules.json"
MAP = ROOT / "golden-set/color/rules/color_taxonomy_map.json"


def taxonomy_colors() -> list[str]:
    """taxonomy.py를 import하지 않고 COLORS 리터럴만 파싱한다.

    import하면 image-processor의 의존성(무거운 패키지)이 끌려온다.
    """
    tree = ast.parse(TAXONOMY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "COLORS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit("taxonomy.py에서 COLORS를 찾지 못했다")


def main() -> int:
    ko = taxonomy_colors()
    v2 = json.loads(V2.read_text(encoding="utf-8"))["attributes"]
    mapping = json.loads(MAP.read_text(encoding="utf-8"))["map"]

    errors: list[str] = []

    missing = [c for c in ko if c not in mapping]
    if missing:
        errors.append(f"매핑 누락 (taxonomy에 있으나 map에 없음): {missing}")

    extra = [c for c in mapping if c not in ko]
    if extra:
        errors.append(f"유령 항목 (map에 있으나 taxonomy에 없음): {extra}")

    for ko_name, entry in mapping.items():
        target = entry.get("v2")
        if target is None:
            if not entry.get("rule"):
                errors.append(f"{ko_name}: v2가 null인데 대체 rule이 없다")
            continue
        if target not in v2:
            errors.append(f"{ko_name} → '{target}': v2 팔레트에 없는 색")

    used = {e["v2"] for e in mapping.values() if e.get("v2")}
    unused = sorted(set(v2) - used)
    declared = set(json.loads(MAP.read_text(encoding="utf-8")).get("unused_v2_colors", {}))
    if set(unused) != declared:
        errors.append(f"unused_v2_colors 불일치 — 실제: {unused} / 문서: {sorted(declared)}")

    print(f"taxonomy {len(ko)}색 / v2 {len(v2)}색 / 매핑 {len(mapping)}건")
    print(f"미사용 v2 색: {unused}")
    lossy = [k for k, e in mapping.items() if e.get("fidelity") in ("lossy", "unrepresented")]
    print(f"주의 매핑({len(lossy)}): {lossy}")

    if errors:
        print("\n[FAIL]")
        for e in errors:
            print("  -", e)
        return 1
    print("\n[OK] 매핑 정합")
    return 0


if __name__ == "__main__":
    sys.exit(main())
