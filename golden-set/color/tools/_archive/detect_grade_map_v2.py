"""그레이드맵 PNG에서 17×16 매트릭스 등급 추출 (수동 좌표 + 자동 보정).

매트릭스 영역을 먼저 자동 감지한 뒤, 16x17 등분으로 샘플링한다.
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


def detect_matrix_bbox(arr: np.ndarray) -> tuple[int, int, int, int]:
    """매트릭스 영역 (17x16 colored cells) 의 bounding box 자동 감지.

    매트릭스 영역은 색이 다양하게 칠해진 큰 직사각형 영역이다.
    가장 큰 컬러 영역의 bbox를 찾는다.
    """
    h, w, _ = arr.shape
    not_white = np.any(arr < 240, axis=2)

    # 가로 projection: 각 행에 컬러 픽셀이 얼마나 많은가
    row_color_count = not_white.sum(axis=1)
    col_color_count = not_white.sum(axis=0)

    # 매트릭스 영역 (넓고 긴 컬러 영역):
    # 행: 컬러 픽셀이 연속적으로 많은 행들 (한 셀당 가로 70px+, 16셀 = 1120px+ 컬러)
    # 열: 비슷한 방식으로

    # 매트릭스의 y-range: row_color_count가 큰 구간
    threshold = 800  # 한 행에 800개 이상의 컬러 픽셀이면 매트릭스 행
    matrix_rows = np.where(row_color_count >= threshold)[0]
    matrix_cols = np.where(col_color_count >= threshold * 2)[0]  # 매트릭스 컬럼은 더 많은 컬러 픽셀 (16셀 * 높이)

    if len(matrix_rows) < 17 * 20 or len(matrix_cols) < 16 * 30:
        # Fallback: 더 느슨한 threshold
        threshold = 400
        matrix_rows = np.where(row_color_count >= threshold)[0]
        matrix_cols = np.where(col_color_count >= threshold)[0]

    y0, y1 = int(matrix_rows[0]), int(matrix_rows[-1])
    x0, x1 = int(matrix_cols[0]), int(matrix_cols[-1])
    return y0, y1, x0, x1


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: detect_grade_map_v2.py <image> <output_json>")
        return 1

    image_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape
    print(f"Image: {w}x{h}")

    y0, y1, x0, x1 = detect_matrix_bbox(arr)
    print(f"Matrix bbox: y={y0}-{y1} ({y1-y0+1}px), x={x0}-{x1} ({x1-x0+1}px)")

    # 16 cols, 17 rows로 등분
    cell_h = (y1 - y0 + 1) / GRID["rows"]
    cell_w = (x1 - x0 + 1) / GRID["cols"]
    print(f"Cell: {cell_w:.1f} x {cell_h:.1f}")

    matrix = {}
    for ri, rname in enumerate(GRID["row_labels"]):
        row = {}
        cy = int(y0 + (ri + 0.5) * cell_h)
        for ci, cname in enumerate(GRID["col_labels"]):
            cx = int(x0 + (ci + 0.5) * cell_w)
            # 5x5 patch 평균
            yp0, yp1 = max(0, cy - 2), min(h, cy + 3)
            xp0, xp1 = max(0, cx - 2), min(w, cx + 3)
            if yp0 >= yp1 or xp0 >= xp1:
                row[cname] = "na"
                continue
            patch = arr[yp0:yp1, xp0:xp1]
            avg = tuple(int(v) for v in patch.reshape(-1, 3).mean(axis=0))
            row[cname] = classify_pixel(avg)
        matrix[rname] = row

    # 디버그: 매트릭스의 일부분 출력
    print("\nFirst 5 cells of first 5 rows:")
    for ri, rname in enumerate(GRID["row_labels"][:5]):
        grades = [matrix[rname][c] for c in GRID["col_labels"][:5]]
        print(f"  {rname}: {grades}")

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
