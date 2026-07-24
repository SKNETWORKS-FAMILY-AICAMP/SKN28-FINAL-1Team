"""후보 1: SegFormer clothes (mattmdjaga/segformer_b2_clothes)

semantic segmentation — 가볍고 설치 간단, CPU도 가능.
같은 클래스 옷 2벌은 분리 못 하므로 connected component로 근사 분리한다.

실행: python test_segformer.py <이미지경로> [--out output]
"""
from __future__ import annotations

import argparse
import os
import time

import cv2
import numpy as np
import torch
from PIL import Image

from common import SegmentedItem, run

MODEL_ID = "mattmdjaga/segformer_b2_clothes"

# ATR 18클래스 중 패션 아이템 클래스 → (라벨, 대분류 힌트)
# 신체·배경 클래스(피부·머리·다리 등)는 제외한다.
ATR_CLASSES: dict[int, tuple[str, str | None]] = {
    1: ("Hat", "액세서리"),
    3: ("Sunglasses", "액세서리"),
    4: ("Upper-clothes", "상의"),     # 아우터도 여기에 섞임 → 대분류는 SigLIP 재판별
    5: ("Skirt", "하의"),
    6: ("Pants", "하의"),
    7: ("Dress", "원피스/세트"),
    8: ("Belt", "액세서리"),
    9: ("Left-shoe", "신발"),
    10: ("Right-shoe", "신발"),
    16: ("Bag", "가방"),
    17: ("Scarf", "액세서리"),
}
MERGE_LR_SHOES = True  # 왼발/오른발 → 신발 1아이템으로 병합
# Upper-clothes는 상의/아우터 구분이 안 되므로 힌트를 주지 않고 SigLIP에 맡긴다.
NO_HINT_LABELS = {"Upper-clothes"}


def segment(image_path: str, device: str) -> tuple[list[SegmentedItem], dict]:
    from transformers import AutoModelForSemanticSegmentation, SegformerImageProcessor

    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    processor = SegformerImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForSemanticSegmentation.from_pretrained(MODEL_ID).to(device).eval()
    timings["seg_model_load"] = round(time.perf_counter() - t0, 3)

    image = Image.open(image_path).convert("RGB")
    t0 = time.perf_counter()
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    # 원본 해상도로 업샘플 후 클래스 맵 생성
    up = torch.nn.functional.interpolate(
        logits, size=image.size[::-1], mode="bilinear", align_corners=False
    )
    seg_map = up.argmax(dim=1)[0].cpu().numpy()
    timings["seg_inference"] = round(time.perf_counter() - t0, 3)

    items: list[SegmentedItem] = []
    shoe_mask = np.zeros(seg_map.shape, dtype=bool)

    for cls_id, (label, hint) in ATR_CLASSES.items():
        mask = seg_map == cls_id
        if not mask.any():
            continue
        if MERGE_LR_SHOES and label in ("Left-shoe", "Right-shoe"):
            shoe_mask |= mask
            continue
        # semantic 마스크를 connected component로 분리 (동일 클래스 복수 아이템 근사)
        n, comp = cv2.connectedComponents(mask.astype(np.uint8))
        for c in range(1, n):
            items.append(SegmentedItem(
                mask=comp == c,
                label=label,
                category_large_hint=None if label in NO_HINT_LABELS else hint,
            ))

    if shoe_mask.any():
        items.append(SegmentedItem(mask=shoe_mask, label="Shoes",
                                   category_large_hint="신발"))
    return items, timings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    device = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    items, timings = segment(args.image, device)
    run(args.image, args.out, "segformer_b2_clothes", items, timings)


if __name__ == "__main__":
    main()
