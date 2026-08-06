"""그레이드맵에서 17×16 매트릭스 정밀 추출.

이미지: 1376x768
매트릭스 영역:
  - y: 180~730 (550px, 17행 × 32.4px)
  - x: 150~1290 (1140px, 16열 × 71.25px)
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


def classify_pixel(rgb) -> tuple[str, float]:
    """가장 가까운 등급 색상의 이름과 거리. 거리가 90 초과면 'na'."""
    best, best_d = "na", float("inf")
    for grade, color in GRADE_COLORS.items():
        d = color_distance(rgb, color)
        if d < best_d:
            best, best_d = grade, d
    if best_d > 90:
        return "na", best_d
    return best, best_d


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: extract_matrix_v2.py <image> <output_json>")
        return 1

    image_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape
    print(f"Image: {w}x{h}")

    # 매트릭스 영역 (정밀 측정값)
    y0, y1 = 180, 730
    x0, x1 = 150, 1290
    cell_h = (y1 - y0 + 1) / GRID["rows"]
    cell_w = (x1 - x0 + 1) / GRID["cols"]
    print(f"Cell: {cell_w:.1f} x {cell_h:.1f}")

    matrix = {}
    debug_log: list[list[tuple[str, tuple[int, int, int], float]]] = []
    for ri, rname in enumerate(GRID["row_labels"]):
        row = {}
        dbg_row = []
        cy = int(y0 + (ri + 0.5) * cell_h)
        for ci, cname in enumerate(GRID["col_labels"]):
            cx = int(x0 + (ci + 0.5) * cell_w)
            # 7x7 patch 평균 (셀 중앙 1/3 영역)
            yp0, yp1 = max(0, cy - 3), min(h, cy + 4)
            xp0, xp1 = max(0, cx - 3), min(w, cx + 4)
            if yp0 >= yp1 or xp0 >= xp1:
                row[cname] = "na"
                dbg_row.append(("na", (0, 0, 0), 999))
                continue
            patch = arr[yp0:yp1, xp0:xp1]
            avg = tuple(int(v) for v in patch.reshape(-1, 3).mean(axis=0))
            grade, dist = classify_pixel(avg)
            row[cname] = grade
            dbg_row.append((grade, avg, dist))
        matrix[rname] = row
        debug_log.append(dbg_row)

    # 매트릭스 출력 (시각화)
    print("\n=== Extracted Matrix ===")
    header = "         " + " ".join(f"{c[:4]:>5}" for c in GRID["col_labels"])
    print(header)
    for ri, rname in enumerate(GRID["row_labels"]):
        cells = [f"{matrix[rname][c][:4]:>5}" for c in GRID["col_labels"]]
        print(f"{rname[:8]:>8}  " + " ".join(cells))

    output_path.write_text(
        json.dumps(
            {
                "source_image": str(image_path),
                "image_size": [w, h],
                "matrix_bbox": [y0, y1, x0, x1],
                "cell_size": [cell_w, cell_h],
                "grid": GRID,
                "matrix_grade": matrix,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nOK: wrote {output_path}")
    from collections import Counter
    flat = [v for row in matrix.values() for v in row.values()]
    print("grade distribution:", dict(Counter(flat)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
