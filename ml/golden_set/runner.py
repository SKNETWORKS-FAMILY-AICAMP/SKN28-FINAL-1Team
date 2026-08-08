"""컨테이너 진입점 — S3의 미처리 골든 원본을 찾아 임베딩까지 끝낸다.

기동하면 곧바로 한 번 돌고, `GOLDEN_SCAN_INTERVAL_SECONDS`가 양수면 그 간격으로
계속 다시 스캔한다(0이면 1회 처리 후 종료 — 배치 잡으로 쓰기 좋다).

"미처리"의 판단은 두 층으로 나뉜다.

- 코디 임베딩: `image_embeddings.npz`에 같은 sha가 있으면 건너뛴다(로컬 캐시).
- 아이템 분리·태깅·임베딩: S3에 완료 manifest가 있으면 건너뛴다(원격 기준).

로컬 run 디렉터리가 날아가도 S3 쪽 기준이 남아 있어 가장 비싼 단계(아이템별
Gemini 호출)는 다시 돌지 않는다. 반대로 코디 임베딩은 로컬 캐시가 없으면
다시 계산하므로, 컨테이너에 run 볼륨을 붙이는 편이 낫다.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from .analysis import analyze_run
from .artifacts import read_json, write_json
from .clustering import cluster_embeddings
from .config import GoldenSettings, load_project_env
from .embedding import embed_manifest_images
from .items import extract_items, pending_golden_ids
from .manifest import build_manifest_from_s3
from .qdrant_index import index_run
from .web.service import publish_run_summary

logger = logging.getLogger("golden_set.runner")


def run_once(
    settings: GoldenSettings,
    *,
    embedding_backend: str = "fashion",
    text_backend: str = "bge",
    do_index: bool = True,
    do_analyze: bool = False,
) -> dict[str, Any]:
    run_dir = settings.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    images = build_manifest_from_s3(settings=settings, run_dir=run_dir)
    logger.info("manifest: 코디 %d장", len(images))

    pending = pending_golden_ids(run_dir=run_dir, settings=settings)
    logger.info("아이템 미처리 코디: %d장", len(pending))

    _, _, model_name = embed_manifest_images(
        run_dir=run_dir,
        settings=settings,
        backend_name=embedding_backend,
    )
    embed_meta = read_json(run_dir / "image_embeddings.meta.json")
    logger.info(
        "코디 임베딩: 신규 %s / 재사용 %s (%s)",
        embed_meta.get("embedded"),
        embed_meta.get("reused"),
        model_name,
    )

    cluster_embeddings(run_dir=run_dir)

    item_rows = extract_items(run_dir=run_dir, settings=settings)
    logger.info("아이템: %d건", len(item_rows))

    if do_analyze:
        # 판단 지식 트랙(A1~A8 관찰·claim)은 유료 멀티모달 호출이 커서 기본 꺼둔다.
        results = analyze_run(run_dir=run_dir, settings=settings, analyze_all=True)
        logger.info("코디 분석: %d건", len(results))

    manifest = read_json(run_dir / "run_manifest.json")
    manifest.update({"image_embedding_version": model_name, "status": "EMBEDDED"})
    write_json(run_dir / "run_manifest.json", manifest)

    summary: dict[str, Any] = {
        "num_images": len(images),
        "num_items": len(item_rows),
        "pending_before": len(pending),
        "image_embedding": embed_meta,
        "indexed": False,
    }
    if do_index:
        summary["index"] = index_run(
            run_dir=run_dir,
            settings=settings,
            text_backend_name=text_backend,
            dry_run=False,
        )
        summary["indexed"] = True

    # 확인용 웹은 GPU 호스트의 run 디렉터리를 볼 수 없다. 임베딩 메타를 전달할
    # 유일한 통로가 이 S3 요약이라, 적재 실패와 무관하게 항상 남긴다.
    try:
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        publish_run_summary(settings, summary)
    except Exception:  # noqa: BLE001 — 요약 발행 실패가 사이클을 되돌리면 안 된다
        logger.exception("run 요약 S3 발행 실패")

    logger.info("완료: %s", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="S3 골든 원본 스캔 → 코디·아이템 임베딩 → Qdrant 적재"
    )
    parser.add_argument(
        "--embedding-backend", choices=["fashion", "deterministic"], default="fashion"
    )
    parser.add_argument(
        "--text-backend", choices=["bge", "deterministic"], default="bge"
    )
    parser.add_argument(
        "--no-index", action="store_true", help="Qdrant 적재를 건너뛴다"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="A1~A8 판단 지식 분석도 함께 돌린다 (유료 호출 증가)",
    )
    parser.add_argument("--once", action="store_true", help="반복 스캔 없이 1회만")
    args = parser.parse_args()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    load_project_env()
    settings = GoldenSettings.from_env()
    do_index = not args.no_index and settings.auto_index

    interval = 0 if args.once else settings.scan_interval_seconds
    while True:
        try:
            run_once(
                settings,
                embedding_backend=args.embedding_backend,
                text_backend=args.text_backend,
                do_index=do_index,
                do_analyze=args.analyze,
            )
        except Exception:  # noqa: BLE001 — 한 번의 실패로 워커가 죽으면 안 된다
            logger.exception("스캔 실패")
            if interval <= 0:
                raise
        if interval <= 0:
            return
        logger.info("%d초 후 재스캔", interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
