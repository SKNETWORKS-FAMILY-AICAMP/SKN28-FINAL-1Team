"""그레이드맵 PNG에서 17×16 매트릭스 등급 자동 추출.

자동 그리드 감지:
  1. 흰 배경에서 색이 있는 영역(셀)들의 bbox를 찾는다.
  2. 셀 가로/세로 평균을 계산한다.
  3. 헤더 영역(컬럼 라벨)을 분리한다.
  4. 각 셀 중앙 픽셀을 샘플링해 등급을 판정한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


GRID = {
    "rows": 17,
    "cols": 16,
    "row_labels": [
        "Black", "White", "Charcoal", "Navy", "Beige", "Olive", "Brown",
        "Burgundy", "Mustard", "Teal", "Gray", "Cream", "Rust",
        "Forest Green", "Lavender", "Light Blue", "Blush Pink",
    ],
    "col_labels": [
        "Black", "White", "Charcoal", "Navy", "Beige", "Olive", "Brown",
        "Burgundy", "Mustard", "Teal", "Gray", "Cream", "Rust",
        "Forest Green", "Lavender", "Light Blue",
    ],
}

GRADE_COLORS = {
    "recommended": (31, 122, 58),
    "allowed":     (168, 221, 176),
    "caution":     (242, 229, 101),
    "avoid":       (212, 60, 60),
}


def color_distance(c1, c2) -> float:
    return float(sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5)


def classify_pixel(rgb) -> str:
    best, best_d = "na", float("inf")
    for grade, color in GRADE_COLORS.items():
        d = color_distance(rgb, color)
        if d < best_d:
            best, best_d = grade, d
    if best_d > 90:
        return "na"
    return best


def find_cells(arr: np.ndarray) -> tuple[list[tuple[int, int, int, int]], int, int]:
    """흰 배경이 아닌 connected components(셀)들의 bbox를 y, x로 정렬해서 반환.

    각 셀은 (y_top, x_left, y_bot, x_right).
    """
    h, w, _ = arr.shape
    # 흰 배경이 아닌 픽셀: R<240 OR G<240 OR B<240
    not_white = np.any(arr < 240, axis=2)

    # 각 행에서 "컬러 블록"이 시작/끝나는 위치를 찾는다
    # 단순 접근: 가로 projection (행별 컬러 픽셀 수)
    row_has = not_white.any(axis=1)
    col_has = not_white.any(axis=0)

    # 흰색 사이의 큰 컬러 블록들 (셀) 찾기
    # 각 행에서 컬러 픽셀의 left/right 범위 계산
    rows_with_blocks: list[tuple[int, int, int]] = []  # (y, x_left, x_right)
    for y in range(h):
        xs = np.where(not_white[y])[0]
        if len(xs) < 50:  # 너무 좁은 건 무시 (텍스트 글자 노이즈)
            continue
        rows_with_blocks.append((y, int(xs[0]), int(xs[-1])))

    if not rows_with_blocks:
        raise ValueError("no cells found")

    # 행들을 그룹핑 (연속된 행들)
    groups: list[list[tuple[int, int, int]]] = []
    cur: list[tuple[int, int, int]] = []
    last_y = -10
    for entry in rows_with_blocks:
        y, lx, rx = entry
        if y - last_y > 5:  # 5px 이상 떨어지면 새 그룹
            if cur:
                groups.append(cur)
            cur = []
        cur.append(entry)
        last_y = y
    if cur:
        groups.append(cur)

    print(f"  detected {len(groups)} row groups")
    for i, g in enumerate(groups):
        y0 = g[0][0]
        y1 = g[-1][0]
        lx = min(r[1] for r in g)
        rx = max(r[2] for r in g)
        h_g = y1 - y0 + 1
        w_g = rx - lx + 1
        print(f"    group {i}: y={y0}-{y1} (h={h_g}), x={lx}-{rx} (w={w_g})")

    return groups, w, h


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: detect_grade_map.py <image> <output_json>")
        return 1

    image_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape
    print(f"Image: {w}x{h}")

    groups, _, _ = find_cells(arr)

    # 17개 행 + 1개 헤더 행 = 18개 그룹이어야 함 (혹은 17)
    # 헤더 행은 column label 영역 (텍스트만)
    # 매트릭스 행은 셀 영역 (가로 폭이 큼)
    # 가로 폭으로 구분: 텍스트 라벨은 좁고 셀은 넓음
    actual_groups = []
    for g in groups:
        y0, y1 = g[0][0], g[-1][0]
        lx, rx = min(r[1] for r in g), max(r[2] for r in g)
        w_g = rx - lx
        actual_groups.append((y0, y1, lx, rx, w_g))

    # 가장 넓은 가로 폭을 가진 그룹들을 매트릭스 행으로 추정
    widths = sorted([g[4] for g in actual_groups], reverse=True)
    print(f"  top widths: {widths[:5]}")

    # 매트릭스 행 (너비가 큰 그룹들)
    matrix_rows = sorted([g for g in actual_groups if g[4] >= widths[3] * 0.8], key=lambda x: x[0])

    print(f"  matrix rows: {len(matrix_rows)}")
    if len(matrix_rows) != 17:
        print(f"  WARNING: expected 17 rows, got {len(matrix_rows)}")

    # 17개 행의 평균 y0, y1
    if len(matrix_rows) >= 17:
        y_starts = [r[0] for r in matrix_rows[:17]]
        y_ends = [r[1] for r in matrix_rows[:17]]
        x_left = max(r[2] for r in matrix_rows[:17])
        x_right = min(r[3] for r in matrix_rows[:17])
    else:
        y_starts = [r[0] for r in matrix_rows]
        y_ends = [r[1] for r in matrix_rows]
        x_left = max(r[2] for r in matrix_rows)
        x_right = min(r[3] for r in matrix_rows)

    print(f"  matrix y: {y_starts[0]}-{y_ends[-1]}, x: {x_left}-{x_right}")

    # 셀 가로 사이즈: (x_right - x_left) / 16
    cell_w = (x_right - x_left) / GRID["cols"]
    print(f"  cell_w: {cell_w:.1f}")

    matrix = {}
    for ri, rname in enumerate(GRID["row_labels"]):
        row = {}
        if ri >= len(y_starts):
            break
        cy = (y_starts[ri] + y_ends[ri]) // 2
        for ci, cname in enumerate(GRID["col_labels"]):
            cx = int(x_left + (ci + 0.5) * cell_w)
            # 5x5 patch 평균
            y0, y1 = max(0, cy - 2), min(h, cy + 3)
            x0, x1 = max(0, cx - 2), min(w, cx + 3)
            if y0 >= y1 or x0 >= x1:
                row[cname] = "na"
                continue
            patch = arr[y0:y1, x0:x1]
            avg = tuple(int(x) for x in patch.reshape(-1, 3).mean(axis=0))
            row[cname] = classify_pixel(avg)
        matrix[rname] = row

    output_path.write_text(
        json.dumps(
            {
                "source_image": str(image_path),
                "image_size": [w, h],
                "grid": GRID,
                "matrix_grade": matrix,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"OK: wrote {output_path}")
    from collections import Counter
    flat = [v for row in matrix.values() for v in row.values()]
    print("grade distribution:", dict(Counter(flat)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
