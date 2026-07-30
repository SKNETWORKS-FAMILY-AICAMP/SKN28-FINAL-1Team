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
import requests
from bge_embedder import BgeM3Embedder
from botocore.exceptions import ClientError
from embedder import FashionSigLIPEmbedder
from product_assets import (
    InvalidProductImage,
    PreparedImage,
    StoredProductImageUnavailable,
    download_and_store_image,
    load_stored_image,
)
from product_catalog_api import ProductCatalogApiClient
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
    return min(
        24 * 60 * 60,
        config.RETRY_BASE_SECONDS * (2**exponent),
    )


def _is_transient_http_error(error: requests.HTTPError) -> bool:
    response = error.response
    if response is None:
        return True
    status_code = response.status_code
    return status_code in {408, 425, 429} or status_code >= 500


def _is_missing_s3_object(error: ClientError) -> bool:
    code = str(error.response.get("Error", {}).get("Code", ""))
    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"404", "NoSuchKey", "NotFound"} or status == 404


class ProductIndexer:
    def __init__(
        self,
        *,
        catalog_client: ProductCatalogApiClient | None = None,
        reset_stale: bool = True,
    ) -> None:
        config.validate_runtime_config()
        self.catalog = catalog_client or ProductCatalogApiClient()
        if reset_stale:
            state = self.catalog.status(
                config.EMBEDDING_VERSION,
                reset_stale=True,
                stale_job_minutes=config.STALE_JOB_MINUTES,
            )
            stale_count = int(state.get("reset_stale_count", 0))
            if stale_count:
                logger.warning(
                    "stale 임베딩 작업 %d건을 pending으로 복구",
                    stale_count,
                )

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
        self.catalog.close()

    def _fail(
        self,
        job: dict[str, Any],
        error: Exception | str,
        *,
        transient: bool,
    ) -> None:
        message = str(error)
        next_status = self.catalog.mark_failure(
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

    def _load_or_store_image(
        self,
        job: dict[str, Any],
        product: dict[str, Any],
    ) -> PreparedImage | None:
        image_s3_key = product.get("image_s3_key")
        image_checksum = product.get("image_checksum")
        if image_s3_key and image_checksum:
            try:
                image = load_stored_image(
                    s3_client=self.s3,
                    bucket=config.IMAGE_S3_BUCKET,
                    s3_key=image_s3_key,
                    expected_checksum=image_checksum,
                    max_bytes=config.MAX_IMAGE_BYTES,
                )
                logger.info(
                    "S3 상품 이미지 재사용: %s:%s",
                    job["source"],
                    job["external_product_id"],
                )
                return image
            except StoredProductImageUnavailable as exc:
                logger.warning(
                    "저장 이미지 검증 실패로 원본 URL 복구: %s:%s error=%s",
                    job["source"],
                    job["external_product_id"],
                    exc,
                )
            except ClientError as exc:
                if not _is_missing_s3_object(exc):
                    raise
                logger.warning(
                    "S3 이미지가 없어 원본 URL 복구: %s:%s key=%s",
                    job["source"],
                    job["external_product_id"],
                    image_s3_key,
                )

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
        accepted = self.catalog.mark_image_stored(
            job,
            image_s3_key=image.s3_key,
            image_checksum=image.checksum,
        )
        if not accepted:
            image.image.close()
            logger.info(
                "새 generation 작업으로 변경되어 이미지 체크포인트를 건너뜀: %s:%s",
                job["source"],
                job["external_product_id"],
            )
            return None
        product["image_s3_key"] = image.s3_key
        product["image_checksum"] = image.checksum
        return image

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

        product = job.get("product")
        if not isinstance(product, dict):
            self._fail(
                job,
                "catalog API 응답에 상품 데이터가 없습니다.",
                transient=False,
            )
            return None

        try:
            image = self._load_or_store_image(job, product)
            if image is None:
                return None
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
        jobs = self.catalog.claim_jobs(
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
            accepted = self.catalog.mark_success(
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
                    "새 generation으로 이전 작업 완료를 건너뜀: %s:%s",
                    item.job["source"],
                    item.job["external_product_id"],
                )
        return len(jobs)

    def drain(
        self,
        batch_size: int,
        *,
        max_wait_seconds: int,
        max_runtime_minutes: int,
    ) -> int:
        """현재 준비된 작업과 짧은 재시도까지 모두 처리한 뒤 종료한다."""
        started_at = time.monotonic()
        deadline = started_at + (max_runtime_minutes * 60)
        total_claimed = 0

        while time.monotonic() < deadline:
            claimed = self.process_once(batch_size)
            total_claimed += claimed
            if claimed:
                continue

            state = self.catalog.status(
                config.EMBEDDING_VERSION,
            )
            next_delay = state.get("next_available_in_seconds")
            if (
                next_delay is None
                or max_wait_seconds == 0
                or next_delay > max_wait_seconds
            ):
                break

            sleep_seconds = max(1.0, next_delay)
            remaining_runtime = deadline - time.monotonic()
            if sleep_seconds > remaining_runtime:
                break
            logger.info(
                "임베딩 재시도 작업을 %.1f초 대기",
                sleep_seconds,
            )
            time.sleep(sleep_seconds)

        logger.info(
            "임베딩 drain 종료: claimed=%d, elapsed=%.1f초",
            total_claimed,
            time.monotonic() - started_at,
        )
        return total_claimed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="신규 쇼핑 상품 이미지+텍스트 임베딩 worker"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="현재 pending 배치를 한 번만 처리하고 종료",
    )
    mode.add_argument(
        "--drain",
        action="store_true",
        help="준비된 pending 작업과 짧은 재시도를 모두 처리하고 종료",
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
    parser.add_argument(
        "--drain-max-wait-seconds",
        type=int,
        default=config.DRAIN_MAX_WAIT_SECONDS,
    )
    parser.add_argument(
        "--max-runtime-minutes",
        type=int,
        default=config.DRAIN_MAX_RUNTIME_MINUTES,
    )
    return parser.parse_args()


def _create_indexer(args: argparse.Namespace) -> ProductIndexer | None:
    if not args.drain:
        return ProductIndexer()

    config.validate_runtime_config()
    catalog = ProductCatalogApiClient()
    try:
        state = catalog.status(
            config.EMBEDDING_VERSION,
            reset_stale=True,
            stale_job_minutes=config.STALE_JOB_MINUTES,
        )
        stale_count = int(state.get("reset_stale_count", 0))
        if stale_count:
            logger.warning("stale 임베딩 작업 %d건을 pending으로 복구", stale_count)

        if not state.get("has_pending_jobs"):
            logger.info("처리 가능한 임베딩 작업이 없어 모델 로드 전 종료합니다.")
            catalog.close()
            return None
        next_delay = state.get("next_available_in_seconds")
        if (
            next_delay is None
            or next_delay > args.drain_max_wait_seconds
        ):
            logger.info(
                "설정된 drain 대기 시간 안에 실행할 작업이 없어 "
                "모델 로드 전 종료합니다."
            )
            catalog.close()
            return None
        return ProductIndexer(
            catalog_client=catalog,
            reset_stale=False,
        )
    except Exception:
        catalog.close()
        raise


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size는 1 이상이어야 합니다.")
    if args.batch_size > 256:
        raise ValueError("--batch-size는 256 이하여야 합니다.")
    if args.poll_seconds < 1:
        raise ValueError("--poll-seconds는 1 이상이어야 합니다.")
    if args.drain_max_wait_seconds < 0:
        raise ValueError("--drain-max-wait-seconds는 0 이상이어야 합니다.")
    if args.max_runtime_minutes < 1:
        raise ValueError("--max-runtime-minutes는 1 이상이어야 합니다.")

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    indexer = _create_indexer(args)
    if indexer is None:
        return 0
    try:
        if args.drain:
            indexer.drain(
                args.batch_size,
                max_wait_seconds=args.drain_max_wait_seconds,
                max_runtime_minutes=args.max_runtime_minutes,
            )
            return 0
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
