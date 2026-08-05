"""fitvto-100k 에서 '전신이 온전히 나온' 정면 이미지 + 실측 치수만 골라 받는다.

계획서(fitvto_download_plan.md)의 원안을 두 지점에서 교체했다.

1. 원안은 `streaming=True` + `next()` 균등 스킵으로 표본을 뽑았다. 그러나
   스트리밍은 shard를 순차로 훑기 때문에 211 GB 중 앞쪽 shard에만 편중된다.
   체형 다양성 확보라는 목적에 정면으로 반한다.
   -> shard 자체를 무작위로 골라 row group 단위로 읽는다.

2. 원안은 "머리끝부터 발목까지 노출이 보장된" 데이터셋이라는 전제로 필터가 없다.
   실측 결과 person 이미지의 **72%가 허벅지에서 잘린다**(50장 중 36장).
   필터 없이 N명을 뽑으면 그중 72%가 계측 불가 이미지가 된다.
   -> 하단 여백 검사를 통과한 것만 채택한다.

라이선스: CC-BY-NC-ND-4.0. 비상업적 + 2차저작물 금지.
          모델 **학습에 사용 금지**. 내부 평가(벤치마크) 전용.
          산출물은 .gitignore로 커밋을 막아둔다.
"""

from __future__ import annotations

import argparse
import io
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import HfFileSystem
from PIL import Image

REPO = "Yuanhao-Harry-Wang/fitvto-100k"
# datasets-server가 변환해둔 parquet 브랜치. 원본 리비전보다 스키마가 안정적이다.
PARQUET_REF = "refs%2Fconvert%2Fparquet/default"
# eval split(20 shard / 5,000행)만 쓴다. train은 406 shard / 201 GB로 파일럿에 과하다.
SPLIT = "eval"
N_SHARDS = 20

OUT_DIR = Path("ml/body_measurement/data/fitvto_eval")

# 하단 여백 검사 파라미터. 육안 대조로 검증한 값이다.
BOTTOM_ROWS = 8       # 이미지 최하단 몇 행을 볼 것인가
BG_TOLERANCE = 40     # 배경색과의 RGB 합산 거리가 이 값을 넘으면 '인물'로 본다
OCCUPANCY_MAX = 0.05  # 최하단 행의 인물 픽셀 비율이 이보다 크면 '잘림'으로 판정


def is_full_body(img: Image.Image) -> bool:
    """발 아래에 배경 여백이 있으면 전신, 인물이 하단 경계에 닿아 있으면 잘림.

    fitvto의 person 이미지는 배경이 균일한 스튜디오 렌더라 이 단순 검사가 통한다.
    배경이 복잡한 소스에는 그대로 쓸 수 없다.
    """
    a = np.asarray(img.convert("RGB")).astype(int)
    # 네 모서리의 중앙값을 배경색으로 삼는다. 한 모서리에 그림자가 걸려도 견딘다.
    bg = np.median(np.stack([a[0, 0], a[0, -1], a[5, 5], a[5, -5]]), axis=0)
    bottom = a[-BOTTOM_ROWS:, :, :]
    occupancy = (np.abs(bottom - bg).sum(axis=2) > BG_TOLERANCE).mean()
    return occupancy <= OCCUPANCY_MAX


def measurement_key(row: dict) -> tuple:
    """치수 튜플. fitvto는 한 사람에게 여러 의상을 입혀 여러 행을 만들기 때문에
    같은 몸이 반복 등장한다. 이 키로 중복을 제거한다."""
    return (
        round(row["body_height"], 1),
        round(row["body_bust"], 1),
        round(row["body_waist"], 1),
        round(row["body_hips"], 1),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=20, help="확보할 인원 수")
    ap.add_argument("--seed", type=int, default=42, help="shard 선택 시드 (재현성)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument(
        "--max-per-shard",
        type=int,
        default=0,
        help="shard 하나에서 최대 몇 명까지 뽑을지. 0이면 max(2, target//5)로 자동 설정. "
             "한 shard를 끝까지 빨아들이면 소표본이 그 shard에 군집해 체형 분포가 좁아진다.",
    )
    args = ap.parse_args()

    # shard당 상한을 두어 표본을 여러 shard에 흩는다.
    # 상한이 없으면 target=20 기준으로 첫 shard에서 전부 채워져 버린다(실측 확인).
    max_per_shard = args.max_per_shard or max(2, args.target // 5)

    img_dir = args.out / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    shard_order = list(range(N_SHARDS))
    rng.shuffle(shard_order)

    fs = HfFileSystem()
    records: list[dict] = []
    seen: set[tuple] = set()
    stat = {"scanned": 0, "cropped": 0, "duplicate": 0}

    print(f"=== fitvto-100k 전신 필터 수집 시작 (목표 {args.target}명, seed={args.seed}) ===")

    # shard 순회를 여러 바퀴 돈다. 한 바퀴에 shard당 max_per_shard 만큼만 가져가므로
    # 목표를 못 채우면 다음 바퀴에서 이어 받는다. 한 바퀴에 아무것도 못 얻으면 종료.
    next_row_group = {i: 0 for i in shard_order}

    while len(records) < args.target:
        gained_this_pass = 0

        for shard_idx in shard_order:
            if len(records) >= args.target:
                break
            if next_row_group[shard_idx] is None:  # 이 shard는 소진됨
                continue

            path = f"datasets/{REPO}@{PARQUET_REF}/{SPLIT}/{shard_idx:04d}.parquet"
            try:
                pf = pq.ParquetFile(fs.open(path))
            except Exception as exc:
                print(f"[shard {shard_idx:04d}] 열기 실패, 건너뜀: {exc}")
                next_row_group[shard_idx] = None
                continue

            taken_here = 0
            rg = next_row_group[shard_idx]

            while rg < pf.num_row_groups and taken_here < max_per_shard:
                if len(records) >= args.target:
                    break

                table = pf.read_row_group(
                    rg,
                    columns=["person", "body_height", "body_bust", "body_waist", "body_hips"],
                )
                rg += 1

                for row in table.to_pylist():
                    if len(records) >= args.target or taken_here >= max_per_shard:
                        break

                    stat["scanned"] += 1

                    key = measurement_key(row)
                    # seen에는 '프레이밍 필터까지 통과한' 행의 키만 쌓인다.
                    # 따라서 이 카운터는 실제 중복률을 과소 집계한다(같은 몸이 잘린 컷으로
                    # 먼저 나온 경우는 중복으로 안 잡힘). 저장 결과는 여전히 중복이 없다.
                    if key in seen:
                        stat["duplicate"] += 1
                        continue

                    try:
                        img = Image.open(io.BytesIO(row["person"]["bytes"])).convert("RGB")
                    except Exception:
                        continue

                    if not is_full_body(img):
                        stat["cropped"] += 1
                        continue

                    seen.add(key)
                    subject_id = f"FV_{len(records):03d}"
                    filename = f"{subject_id}_front.jpg"
                    img.save(img_dir / filename, "JPEG", quality=95)

                    records.append(
                        {
                            "subject_id": subject_id,
                            "height": round(row["body_height"], 2),
                            "bust": round(row["body_bust"], 2),
                            "waist": round(row["body_waist"], 2),
                            "hip": round(row["body_hips"], 2),
                            "image_path": f"{args.out}/images/{filename}",
                            "source_shard": f"{SPLIT}/{shard_idx:04d}.parquet",
                        }
                    )
                    taken_here += 1
                    gained_this_pass += 1
                    print(
                        f"  [{len(records):3d}/{args.target}] {subject_id} "
                        f"(shard {shard_idx:04d}) "
                        f"H:{row['body_height']:.1f} B:{row['body_bust']:.1f} "
                        f"W:{row['body_waist']:.1f} Hip:{row['body_hips']:.1f}"
                    )

            next_row_group[shard_idx] = rg if rg < pf.num_row_groups else None

        if gained_this_pass == 0:
            print("\n한 바퀴를 다 돌았지만 새로 얻은 표본이 없어 종료합니다.")
            break

    df = pd.DataFrame(records)
    csv_path = args.out / "summary_fitvto_eval.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    (args.out / "collection_stats.json").write_text(
        json.dumps(
            {
                "target": args.target,
                "collected": len(records),
                "seed": args.seed,
                "split": SPLIT,
                **stat,
                # 주의: collected/scanned를 통과율이라 부르면 안 된다.
                # collected는 --target에 도달하는 순간 루프가 끊기므로 상한에 걸린 값이고,
                # "필터를 얼마나 통과하는가"가 아니라 "언제 멈췄는가"를 반영한다.
                "collected_per_scanned": (
                    round(len(records) / stat["scanned"], 4) if stat["scanned"] else 0
                ),
                # 실제 프레이밍 통과율: 중복 제거로 빠진 행은 애초에 필터를 타지 않으므로
                # 분모에서 제외한다.
                "full_body_pass_rate": (
                    round(
                        (stat["scanned"] - stat["duplicate"] - stat["cropped"])
                        / (stat["scanned"] - stat["duplicate"]),
                        4,
                    )
                    if stat["scanned"] - stat["duplicate"] > 0
                    else 0
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== 수집 완료 ===")
    print(f" - 확보: {len(records)}명 / 목표 {args.target}명")
    print(f" - 스캔 {stat['scanned']}행 (잘림 제외 {stat['cropped']}, 중복 제외 {stat['duplicate']})")
    print(f" - CSV: {csv_path}")
    if not df.empty:
        print(f" - 키 {df.height.min():.1f}~{df.height.max():.1f} / "
              f"가슴 {df.bust.min():.1f}~{df.bust.max():.1f} / "
              f"허리 {df.waist.min():.1f}~{df.waist.max():.1f}")


if __name__ == "__main__":
    main()
