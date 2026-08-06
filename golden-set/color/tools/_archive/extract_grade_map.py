"""Pinterest 그레이드맵 PNG에서 17×16 매트릭스 등급을 픽셀로 추출.

셀 판정:
  - dark green  (≈#1F7A3A)  → recommended
  - light green (≈#A8DDB0)  → allowed
  - yellow      (≈#F2E565)  → caution
  - red         (≈#D43C3C)  → avoid
  - other       → row×col 의 실제 색상 → 'na' (모노톤)

Usage:
    python extract_grade_map.py <image_path> <output_json>
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

# 그레이드 색상 (image_synthesize가 그려준 셀 채움 색)
GRADE_COLORS = {
    "recommended": (31, 122, 58),    # dark green
    "allowed":     (168, 221, 176),  # light green
    "caution":     (242, 229, 101),  # yellow
    "avoid":       (212, 60, 60),    # red
}


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    return float(sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5)


def classify_pixel(rgb: tuple[int, int, int]) -> str:
    """셀 중앙 픽셀이 어떤 등급에 해당하는지 판정."""
    best, best_d = "na", float("inf")
    for grade, color in GRADE_COLORS.items():
        d = color_distance(rgb, color)
        if d < best_d:
            best, best_d = grade, d
    # 거리가 멀면 (실제 색상 셀) na 처리
    if best_d > 90:
        return "na"
    return best


def find_grid_bounds(arr: np.ndarray) -> dict:
    """그레이드맵 이미지에서 매트릭스 셀 영역 경계를 찾는다.

    그리드는 흰색 배경 위, 셀 사이는 흰색으로 분리되어 있다.
    - 위에서부터: title (큰 글자), legend (작은 글자 + 4 색 칩), header row (column label)
    - 왼쪽에서: row label column
    """
    h, w, _ = arr.shape
    # 흰색이 아닌 첫 행을 찾는다 (제목의 위)
    not_white_row = np.where(np.any(arr < 240, axis=(1, 2)))[0]
    if len(not_white_row) == 0:
        raise ValueError("no grid found")
    return {"width": w, "height": h, "first_dark_row": int(not_white_row[0])}


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: extract_grade_map.py <image> <output_json>")
        return 1

    image_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape
    print(f"Image: {w}x{h}")

    # 경험적 grid 위치 (이 그레이드맵에 맞춤):
    # - 상단 여백: ~30px
    # - 헤더 행 (column label): ~30px
    # - 좌측 여백 (row label): ~80px
    # - 셀 가로: ~85px
    # - 셀 세로: ~30px
    # 이 값은 1480x590 이미지에 맞춤. 다른 사이즈면 수정 필요.
    top_offset = 78
    left_offset = 92
    cell_w = 86
    cell_h = 30

    rows = GRID["rows"]
    cols = GRID["cols"]

    matrix: dict[str, dict[str, str]] = {}
    reasons: dict[str, dict[str, str]] = {}
    pixel_log: list[list[tuple[int, int, int]]] = []

    for ri, rname in enumerate(GRID["row_labels"]):
        row: dict[str, str] = {}
        rr: dict[str, str] = {}
        row_pixels: list[tuple[int, int, int]] = []
        for ci, cname in enumerate(GRID["col_labels"]):
            cy = top_offset + ri * cell_h + cell_h // 2
            cx = left_offset + ci * cell_w + cell_w // 2
            # 셀이 너무 좁아서 1px 샘플이 불안정하면 5x5 평균
            y0, y1 = max(0, cy - 2), min(h, cy + 3)
            x0, x1 = max(0, cx - 2), min(w, cx + 3)
            patch = arr[y0:y1, x0:x1]
            avg = tuple(int(x) for x in patch.reshape(-1, 3).mean(axis=0))
            row_pixels.append(avg)
            grade = classify_pixel(avg)
            row[cname] = grade
            rr[cname] = f"그레이드맵 픽셀 #{avg[0]:02x}{avg[1]:02x}{avg[2]:02x}"
        matrix[rname] = row
        reasons[rname] = rr
        pixel_log.append(row_pixels)

    output_path.write_text(
        json.dumps(
            {
                "source_image": str(image_path),
                "image_size": [w, h],
                "grid": GRID,
                "matrix_grade": matrix,
                "matrix_reason": reasons,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"OK: wrote {output_path}")
    # 요약
    from collections import Counter
    flat = [v for row in matrix.values() for v in row.values()]
    print("grade distribution:", dict(Counter(flat)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
