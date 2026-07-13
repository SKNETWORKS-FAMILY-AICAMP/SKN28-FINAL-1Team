"""후보 3: Grounding DINO + SAM2

open-vocabulary 검출(텍스트 프롬프트) + 프롬프터블 세그멘테이션.
품질 상한이 가장 높고 카테고리 확장이 프롬프트 수정만으로 가능. GPU 권장.

- Grounding DINO: HF transformers (IDEA-Research/grounding-dino-base)
- SAM2: ultralytics 배포 체크포인트(sam2.1_l.pt, 첫 실행 시 자동 다운로드)
  * 공식 facebookresearch/sam2 패키지도 가능하나 설치가 단순한 쪽을 기본으로 한다.

실행: python test_grounded_sam2.py <이미지경로> [--out output]
"""
from __future__ import annotations

import argparse
import os
import time

import numpy as np
import torch
from PIL import Image

from common import SegmentedItem, run

DINO_ID = "IDEA-Research/grounding-dino-base"
SAM2_WEIGHTS = os.getenv("SAM2_WEIGHTS", "sam2.1_l.pt")
BOX_THRESHOLD = 0.30
TEXT_THRESHOLD = 0.25
NMS_IOU = 0.6

# 검출 프롬프트 구문 → 대분류 힌트.
# DINO 텍스트 타워는 영어 중심이므로 프롬프트는 영어로 구성한다.
PROMPT_CLASSES: dict[str, str | None] = {
    "t-shirt": "상의",
    "shirt": "상의",
    "sweater": "상의",
    "hoodie": "상의",
    "sleeveless top": "상의",
    "jacket": "아우터",
    "coat": "아우터",
    "padded jacket": "아우터",
    "cardigan": "아우터",
    "vest": None,          # 니트 베스트(상의) vs 패딩 베스트(아우터) → SigLIP 판별
    "dress": "원피스/세트",
    "jumpsuit": "원피스/세트",
    "pants": "하의",
    "jeans": "하의",
    "shorts": "하의",
    "skirt": "하의",
    "leggings": "하의",
    "shoes": "신발",
    "sneakers": "신발",
    "boots": "신발",
    "sandals": "신발",
    "bag": "가방",
    "backpack": "가방",
    "hat": "액세서리",
    "cap": "액세서리",
    "scarf": "액세서리",
    "belt": "액세서리",
    "sunglasses": "액세서리",
}
TEXT_PROMPT = " . ".join(PROMPT_CLASSES) + " ."


def _match_hint(label: str) -> str | None:
    """DINO가 반환한 라벨(프롬프트 구문 조각)을 힌트 테이블에 매칭."""
    label = label.strip().lower()
    if label in PROMPT_CLASSES:
        return PROMPT_CLASSES[label]
    for phrase, hint in PROMPT_CLASSES.items():  # 부분 일치 fallback
        if phrase in label:
            return hint
    return None


def segment(image_path: str, device: str) -> tuple[list[SegmentedItem], dict]:
    from torchvision.ops import nms
    from transformers import AutoProcessor, GroundingDinoForObjectDetection
    from ultralytics import SAM

    timings: dict[str, float] = {}
    image = Image.open(image_path).convert("RGB")

    # ── ① Grounding DINO: 텍스트 프롬프트 → bbox ──────────
    t0 = time.perf_counter()
    processor = AutoProcessor.from_pretrained(DINO_ID)
    dino = GroundingDinoForObjectDetection.from_pretrained(DINO_ID).to(device).eval()
    timings["dino_model_load"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    inputs = processor(images=image, text=TEXT_PROMPT, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = dino(**inputs)
    det = processor.post_process_grounded_object_detection(
        outputs, inputs.input_ids,
        box_threshold=BOX_THRESHOLD, text_threshold=TEXT_THRESHOLD,
        target_sizes=[image.size[::-1]],
    )[0]
    timings["dino_inference"] = round(time.perf_counter() - t0, 3)

    boxes, scores, labels = det["boxes"], det["scores"], det["labels"]
    if len(boxes) == 0:
        return [], timings

    # 같은 옷이 "shirt"/"t-shirt" 등으로 중복 검출되므로 라벨 무관 NMS로 정리
    keep = nms(boxes, scores, NMS_IOU)
    boxes, scores = boxes[keep].cpu(), scores[keep].cpu()
    labels = [labels[i] for i in keep.tolist()]

    # ── ② SAM2: bbox 프롬프트 → 마스크 ────────────────────
    t0 = time.perf_counter()
    sam = SAM(SAM2_WEIGHTS)
    timings["sam2_model_load"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    sam_res = sam(image_path, bboxes=boxes.numpy(), verbose=False)[0]
    timings["sam2_inference"] = round(time.perf_counter() - t0, 3)

    items: list[SegmentedItem] = []
    for mask_t, score, label in zip(sam_res.masks.data, scores, labels):
        mask = mask_t.cpu().numpy().astype(bool)
        if mask.shape != (image.height, image.width):
            import cv2
            mask = cv2.resize(mask.astype(np.uint8), image.size,
                              interpolation=cv2.INTER_NEAREST).astype(bool)
        items.append(SegmentedItem(mask=mask, label=str(label),
                                   score=float(score),
                                   category_large_hint=_match_hint(str(label))))
    return items, timings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    device = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    items, timings = segment(args.image, device)
    run(args.image, args.out, "grounded_sam2", items, timings)


if __name__ == "__main__":
    main()
