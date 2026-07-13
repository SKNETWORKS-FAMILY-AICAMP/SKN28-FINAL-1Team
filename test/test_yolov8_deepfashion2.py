"""후보 2: YOLOv8-seg + DeepFashion2 파인튜닝 가중치

instance segmentation — 같은 클래스 복수 아이템 분리 가능, 빠름.
공식 배포 가중치가 없어 DeepFashion2로 학습된 .pt 파일을 준비해야 한다.
(HF/커뮤니티 체크포인트 사용 또는 S3의 세그 라벨 데이터로 자체 학습)

실행: python test_yolov8_deepfashion2.py <이미지경로> --weights <df2.pt> [--out output]
      가중치는 --weights 또는 환경변수 YOLO_DF2_WEIGHTS로 지정.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image

from common import SegmentedItem, run

# DeepFashion2 13클래스 → (라벨, 대분류 힌트)
DF2_CLASSES: dict[int, tuple[str, str | None]] = {
    0: ("short_sleeved_shirt", "상의"),
    1: ("long_sleeved_shirt", "상의"),
    2: ("short_sleeved_outwear", "아우터"),
    3: ("long_sleeved_outwear", "아우터"),
    4: ("vest", "상의"),
    5: ("sling", "상의"),
    6: ("shorts", "하의"),
    7: ("trousers", "하의"),
    8: ("skirt", "하의"),
    9: ("short_sleeved_dress", "원피스/세트"),
    10: ("long_sleeved_dress", "원피스/세트"),
    11: ("vest_dress", "원피스/세트"),
    12: ("sling_dress", "원피스/세트"),
}
CONF_THRESHOLD = 0.35


def segment(image_path: str, weights: str) -> tuple[list[SegmentedItem], dict]:
    from ultralytics import YOLO

    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    model = YOLO(weights)
    timings["seg_model_load"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    result = model(image_path, conf=CONF_THRESHOLD, verbose=False)[0]
    timings["seg_inference"] = round(time.perf_counter() - t0, 3)

    items: list[SegmentedItem] = []
    if result.masks is None:
        return items, timings

    h, w = np.array(Image.open(image_path).convert("RGB")).shape[:2]
    for mask_t, box in zip(result.masks.data, result.boxes):
        cls_id = int(box.cls)
        label, hint = DF2_CLASSES.get(cls_id, (result.names.get(cls_id, str(cls_id)), None))
        # 마스크는 모델 입력 해상도 기준 → 원본 크기로 복원
        mask = cv2.resize(mask_t.cpu().numpy(), (w, h),
                          interpolation=cv2.INTER_NEAREST).astype(bool)
        items.append(SegmentedItem(mask=mask, label=label,
                                   score=float(box.conf),
                                   category_large_hint=hint))
    return items, timings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--weights", default=os.getenv("YOLO_DF2_WEIGHTS"))
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    if not args.weights:
        sys.exit(
            "DeepFashion2 학습 가중치가 필요합니다.\n"
            "--weights <path.pt> 또는 환경변수 YOLO_DF2_WEIGHTS를 지정하세요.\n"
            "참고: DeepFashion2는 신발·가방·모자 클래스가 없어 의류만 검출됩니다."
        )
    items, timings = segment(args.image, args.weights)
    run(args.image, args.out, "yolov8_deepfashion2", items, timings)


if __name__ == "__main__":
    main()
