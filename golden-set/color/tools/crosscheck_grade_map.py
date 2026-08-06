"""레퍼런스 이미지에서 추출한 등급표(grade_map_extracted.json)와
규칙으로 계산한 등급(color_rules.json)을 대조한다.

build_color_rules.py의 주석에 "사용자 그레이드맵과 교차검증 예정"으로 남아 있던
항목을 실제로 수행하기 위한 스크립트다. **결론: 추출본은 검증 기준으로 쓸 수 없다.**
아래 degenerate 행 검사가 그 근거를 출력한다.

실행:
    python golden-set/color/tools/crosscheck_grade_map.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXTRACTED = ROOT / "golden-set/color/rules/_archive/grade_map_extracted.json"
COMPUTED = ROOT / "golden-set/color/rules/color_rules.json"

# 한 행의 셀이 이 비율 이상 같은 값이면 셀 단위 검출이 실패한 것으로 본다.
# 정상적인 등급표라면 한 색이 나머지 16색과 모두 같은 등급일 수 없다.
DEGENERATE_RATIO = 0.8


def main() -> int:
    extracted = json.loads(EXTRACTED.read_text(encoding="utf-8"))["matrix_grade"]
    computed = json.loads(COMPUTED.read_text(encoding="utf-8"))["pair_grades"]

    agree = 0
    diffs: list[tuple[str, str, str, str]] = []
    for row, cols in extracted.items():
        for col, ext in cols.items():
            if row == col:
                continue
            got = computed.get(f"{row}|{col}", {}).get("grade")
            if ext == got:
                agree += 1
            else:
                diffs.append((row, col, ext, got))

    total = agree + len(diffs)
    print(f"대조 {total}셀 — 일치 {agree} ({agree / total:.0%}) / 불일치 {len(diffs)}")

    degenerate = []
    for row, cols in extracted.items():
        vals = [v for k, v in cols.items() if k != row]
        top, n = Counter(vals).most_common(1)[0]
        if n / len(vals) >= DEGENERATE_RATIO:
            degenerate.append((row, top, n, len(vals)))

    na = sum(1 for row, cols in extracted.items() for k, v in cols.items()
             if k != row and v == "na")

    print(f"\n셀 검출 실패 징후")
    print(f"  - 값이 뭉개진 행 {len(degenerate)}/{len(extracted)}:")
    for row, top, n, m in degenerate:
        print(f"      {row:14s} {n}/{m} 셀이 전부 '{top}'")
    print(f"  - 미검출(na) 셀: {na}")

    print("\n불일치 유형 (추출값 → 계산값):")
    for (e, c), n in Counter((e, c) for _, _, e, c in diffs).most_common():
        print(f"  {str(e):12s} → {str(c):12s} {n}건")

    verdict = len(degenerate) >= 3 or na >= 10
    print("\n[판정] " + (
        "추출본은 검증 기준으로 쓸 수 없다 — 셀 단위 검출이 실패했다. "
        "계산 등급을 유지하고, 재검증은 레퍼런스를 사람이 직접 전사한 뒤에 한다."
        if verdict else
        "추출본이 사용 가능해 보인다 — 불일치 목록을 사람이 검토할 것."
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
