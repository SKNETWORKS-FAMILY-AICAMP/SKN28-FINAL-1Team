"""신규 네이버·11번가 상품 → 이미지+텍스트 임베딩 → Qdrant worker.

collector가 product_embedding_job에 등록한 신규 상품만 처리한다. 기존 DB 상품은
별도 백필 명령을 만들기 전까지 이 worker의 대상이 되지 않는다.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from typing import Any

import boto3
import product_config as config
import product_db
import requests
from bge_embedder import BgeM3Embedder
from embedder import FashionSigLIPEmbedder
from product_assets import (
    InvalidProductImage,
    PreparedImage,
    download_and_store_image,
)
from product_qdrant import (
    build_point,
    ensure_collection,
    make_client,
    upsert_points,
)
from product_text import build_product_payload, serialize_product_text

logger = logging.getLogger("product_indexer")


@dataclass
class PreparedProduct:
    job: dict[str, Any]
    product: dict[str, Any]
    image: PreparedImage
    text: str


def _retry_delay(job: dict[str, Any]) -> int:
    exponent = max(0, int(job["attempt_count"]) - 1)
    return config.RETRY_BASE_SECONDS * (2**exponent)


def _is_transient_http_error(error: requests.HTTPError) -> bool:
    response = error.response
    if response is None:
        return True
    status_code = response.status_code
    return status_code in {408, 425, 429} or status_code >= 500


class ProductIndexer:
    def __init__(self) -> None:
        config.validate_runtime_config()
        self.db = product_db.get_connection()
        stale_count = product_db.reset_stale_jobs(
            self.db,
            config.STALE_JOB_MINUTES,
        )
        if stale_count:
            logger.warning("stale 임베딩 작업 %d건을 pending으로 복구", stale_count)

        self.image_embedder = FashionSigLIPEmbedder(
            model_id=config.IMAGE_MODEL_ID,
            device=config.DEVICE,
        )
        self.text_embedder = BgeM3Embedder(
            config.TEXT_MODEL_ID,
            revision=config.TEXT_MODEL_REVISION,
            device=config.DEVICE,
            max_length=config.TEXT_MAX_LENGTH,
        )
        self.qdrant = make_client(config.QDRANT_URL, config.QDRANT_API_KEY)
        ensure_collection(
            self.qdrant,
            config.QDRANT_COLLECTION,
            image_dim=self.image_embedder.dim,
            text_dim=self.text_embedder.dim,
        )
        self.s3 = boto3.client("s3")
        self.http = requests.Session()
        self.http.headers["User-Agent"] = "SKN28-product-indexer/1.0"

    def close(self) -> None:
        self.http.close()
        self.db.close()

    def _fail(
        self,
        job: dict[str, Any],
        error: Exception | str,
        *,
        transient: bool,
    ) -> None:
        message = str(error)
        next_status = product_db.mark_failure(
            self.db,
            job,
            message,
            max_retries=config.MAX_RETRIES,
            retry_delay_seconds=_retry_delay(job),
            transient=transient,
        )
        if next_status == "pending":
            logger.warning(
                "임베딩 재시도 예약: %s:%s attempt=%s error=%s",
                job["source"],
                job["external_product_id"],
                job["attempt_count"],
                message,
            )
        elif next_status == "failed":
            logger.error(
                "임베딩 최종 실패: %s:%s attempts=%s error=%s",
                job["source"],
                job["external_product_id"],
                job["attempt_count"],
                message,
            )

    def _prepare(self, job: dict[str, Any]) -> PreparedProduct | None:
        if job["target_version"] != config.EMBEDDING_VERSION:
            self._fail(
                job,
                (
                    "worker와 작업의 embedding_version이 다릅니다: "
                    f"worker={config.EMBEDDING_VERSION}, "
                    f"job={job['target_version']}"
                ),
                transient=False,
            )
            return None

        product = product_db.fetch_product(
            self.db,
            job["source"],
            job["external_product_id"],
        )
        if product is None:
            self._fail(job, "DB에서 상품을 찾을 수 없습니다.", transient=False)
            return None

        try:
            image = download_and_store_image(
                session=self.http,
                s3_client=self.s3,
                source=job["source"],
                external_product_id=job["external_product_id"],
                image_url=product.get("image_url") or "",
                bucket=config.IMAGE_S3_BUCKET,
                prefix=config.IMAGE_S3_PREFIX,
                timeout=config.IMAGE_DOWNLOAD_TIMEOUT,
                max_bytes=config.MAX_IMAGE_BYTES,
            )
        except InvalidProductImage as exc:
            self._fail(job, exc, transient=False)
            return None
        except requests.HTTPError as exc:
            self._fail(job, exc, transient=_is_transient_http_error(exc))
            return None
        except (requests.RequestException, OSError) as exc:
            self._fail(job, exc, transient=True)
            return None
        except Exception as exc:  # noqa: BLE001 - boto3 오류 계층은 서비스별로 다름
            self._fail(job, exc, transient=True)
            return None

        return PreparedProduct(
            job=job,
            product=product,
            image=image,
            text=serialize_product_text(product),
        )

    def process_once(self, batch_size: int) -> int:
        jobs = product_db.claim_jobs(
            self.db,
            batch_size,
            config.EMBEDDING_VERSION,
        )
        if not jobs:
            return 0

        prepared = [item for job in jobs if (item := self._prepare(job)) is not None]
        if not prepared:
            return len(jobs)

        try:
            image_vectors = self.image_embedder.encode_images(
                [item.image.image for item in prepared]
            )
            text_vectors = self.text_embedder.encode_texts(
                [item.text for item in prepared]
            )
            points = []
            for index, item in enumerate(prepared):
                payload = build_product_payload(
                    item.product,
                    embedding_version=config.EMBEDDING_VERSION,
                    image_s3_bucket=config.IMAGE_S3_BUCKET,
                    image_s3_key=item.image.s3_key,
                )
                payload["text"] = item.text
                payload["image_checksum"] = item.image.checksum
                points.append(
                    build_point(
                        source=item.job["source"],
                        external_product_id=item.job["external_product_id"],
                        image_vector=image_vectors[index].tolist(),
                        text_vector=text_vectors[index].tolist(),
                        payload=payload,
                    )
                )
            upsert_points(
                self.qdrant,
                config.QDRANT_COLLECTION,
                points,
            )
        except Exception as exc:
            logger.exception("임베딩 또는 Qdrant 배치 적재 실패")
            for item in prepared:
                self._fail(item.job, exc, transient=True)
            return len(jobs)
        finally:
            for item in prepared:
                item.image.image.close()

        for item in prepared:
            accepted = product_db.mark_success(
                self.db,
                item.job,
                embedding_version=config.EMBEDDING_VERSION,
                image_s3_key=item.image.s3_key,
                image_checksum=item.image.checksum,
            )
            if accepted:
                logger.info(
                    "상품 임베딩 완료: %s:%s",
                    item.job["source"],
                    item.job["external_product_id"],
                )
            else:
                logger.info(
                    "태깅 갱신으로 이전 generation 완료를 건너뜀: %s:%s",
                    item.job["source"],
                    item.job["external_product_id"],
                )
        return len(jobs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="신규 쇼핑 상품 이미지+텍스트 임베딩 worker"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="현재 pending 배치를 한 번만 처리하고 종료",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=config.BATCH_SIZE,
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=config.POLL_SECONDS,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size는 1 이상이어야 합니다.")
    if args.poll_seconds < 1:
        raise ValueError("--poll-seconds는 1 이상이어야 합니다.")

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    indexer = ProductIndexer()
    try:
        while True:
            claimed = indexer.process_once(args.batch_size)
            if args.once:
                return 0
            if claimed == 0:
                time.sleep(args.poll_seconds)
    finally:
        indexer.close()


if __name__ == "__main__":
    raise SystemExit(main())
