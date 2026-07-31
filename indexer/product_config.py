"""네이버·11번가 쇼핑 상품 임베딩 worker 설정."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Django catalog 내부 API. product-indexer는 PostgreSQL에 직접 연결하지 않는다.
CATALOG_API_URL = os.getenv("PRODUCT_CATALOG_API_URL", "").strip().rstrip("/")
CATALOG_API_TOKEN = os.getenv("PRODUCT_INDEXER_INTERNAL_TOKEN", "").strip()
CATALOG_API_TIMEOUT_SECONDS = max(
    1,
    int(os.getenv("PRODUCT_CATALOG_API_TIMEOUT_SECONDS", "30")),
)

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
QDRANT_COLLECTION = os.getenv("PRODUCT_QDRANT_COLLECTION", "products_v1")

# 모델
IMAGE_MODEL_ID = os.getenv(
    "PRODUCT_IMAGE_EMBED_MODEL",
    "hf-hub:Marqo/marqo-fashionSigLIP",
)
TEXT_MODEL_ID = os.getenv("PRODUCT_TEXT_EMBED_MODEL", "BAAI/bge-m3")
TEXT_MODEL_REVISION = os.getenv("PRODUCT_TEXT_MODEL_REVISION", "").strip() or None
EMBEDDING_VERSION = os.getenv(
    "PRODUCT_EMBEDDING_VERSION",
    "marqo-fashionSigLIP+bge-m3-v1",
).strip()
DEVICE = os.getenv("PRODUCT_INDEXER_DEVICE", os.getenv("INDEXER_DEVICE", "auto"))
TEXT_MAX_LENGTH = int(os.getenv("PRODUCT_TEXT_MAX_LENGTH", "512"))

# S3 상품 이미지 원본
IMAGE_S3_BUCKET = os.getenv("PRODUCT_IMAGE_S3_BUCKET", "").strip()
IMAGE_S3_PREFIX = os.getenv("PRODUCT_IMAGE_S3_PREFIX", "products").strip("/")

# worker
BATCH_SIZE = min(
    256,
    max(1, int(os.getenv("PRODUCT_INDEXER_BATCH_SIZE", "32"))),
)
POLL_SECONDS = max(1, int(os.getenv("PRODUCT_INDEXER_POLL_SECONDS", "10")))
MAX_RETRIES = min(
    20,
    max(0, int(os.getenv("PRODUCT_INDEXER_MAX_RETRIES", "2"))),
)
RETRY_BASE_SECONDS = max(1, int(os.getenv("PRODUCT_INDEXER_RETRY_BASE_SECONDS", "30")))
STALE_JOB_MINUTES = max(1, int(os.getenv("PRODUCT_INDEXER_STALE_JOB_MINUTES", "30")))
DRAIN_MAX_WAIT_SECONDS = max(
    0,
    int(os.getenv("PRODUCT_INDEXER_DRAIN_MAX_WAIT_SECONDS", "120")),
)
DRAIN_MAX_RUNTIME_MINUTES = max(
    1,
    int(os.getenv("PRODUCT_INDEXER_DRAIN_MAX_RUNTIME_MINUTES", "120")),
)
IMAGE_DOWNLOAD_TIMEOUT = max(1, int(os.getenv("PRODUCT_IMAGE_DOWNLOAD_TIMEOUT", "30")))
MAX_IMAGE_BYTES = max(
    1, int(os.getenv("PRODUCT_IMAGE_MAX_BYTES", str(20 * 1024 * 1024)))
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def validate_runtime_config() -> None:
    if not CATALOG_API_URL:
        raise RuntimeError(
            "PRODUCT_CATALOG_API_URL이 필요합니다. Django catalog 내부 API의 "
            "product-embeddings URL을 설정하세요."
        )
    if not CATALOG_API_TOKEN:
        raise RuntimeError(
            "PRODUCT_INDEXER_INTERNAL_TOKEN이 필요합니다. catalog API와 "
            "product-indexer에 같은 토큰을 주입하세요."
        )
    if not IMAGE_S3_BUCKET:
        raise RuntimeError(
            "PRODUCT_IMAGE_S3_BUCKET이 필요합니다. 상품 이미지를 S3에 보존한 뒤 "
            "임베딩하도록 .env 또는 실행 환경에 설정하세요."
        )
    if not EMBEDDING_VERSION:
        raise RuntimeError("PRODUCT_EMBEDDING_VERSION은 비어 있을 수 없습니다.")
