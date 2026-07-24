"""Qdrant 벡터 upsert (파생 저장소).

- 컬렉션: wardrobe_items, named vector 2종
  image(768d, FashionSigLIP) / text(1024d, 캡션 임베딩)
- payload의 user_id는 테넌트 필터 — 검색 쿼리에서 반드시 강제한다.
- DB 저장이 성공한 뒤 호출되며, 실패해도 콜백 처리를 막지 않는다(best-effort).
  실패 아이템은 embedding_version이 비어 있으므로 배치 재색인으로 복구한다.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_WARDROBE_COLLECTION", "wardrobe_items")
IMAGE_DIM = int(os.getenv("WARDROBE_IMAGE_VECTOR_DIM", "768"))
TEXT_DIM = int(os.getenv("WARDROBE_TEXT_VECTOR_DIM", "1024"))
EMBEDDING_VERSION = os.getenv("WARDROBE_EMBEDDING_VERSION", "fashionsiglip-v1")


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=os.getenv("QDRANT_API_KEY") or None)


def ensure_collection() -> None:
    client = _client()
    if client.collection_exists(COLLECTION):
        return
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "image": VectorParams(size=IMAGE_DIM, distance=Distance.COSINE),
            "text": VectorParams(size=TEXT_DIM, distance=Distance.COSINE),
        },
    )
    # 테넌트 필터 성능을 위한 payload 인덱스
    client.create_payload_index(COLLECTION, "user_id", field_schema="integer")
    client.create_payload_index(COLLECTION, "category_large", field_schema="keyword")


def upsert_item(item, image_vector: list[float] | None,
                text_vector: list[float] | None) -> bool:
    """아이템 벡터 upsert. 성공 시 True. 벡터가 하나도 없으면 건너뛴다."""
    vectors: dict[str, list[float]] = {}
    if image_vector:
        vectors["image"] = image_vector
    if text_vector:
        vectors["text"] = text_vector
    if not vectors:
        return False

    try:
        ensure_collection()
        _client().upsert(
            collection_name=COLLECTION,
            points=[
                PointStruct(
                    id=str(item.id),
                    vector=vectors,
                    payload={
                        "user_id": item.user_id,
                        "item_id": str(item.id),
                        "category_large": item.category_large,
                        "category_small": item.category_small,
                        "season": item.season,
                        "style": item.style,
                        "color": item.color,
                        "layer_role": item.layer_role,
                        "confirmed": item.confirmed,
                        "s3_key": item.s3_key,
                        "embedding_version": EMBEDDING_VERSION,
                    },
                )
            ],
        )
        return True
    except Exception:  # noqa: BLE001 — 파생 저장소 실패는 콜백을 막지 않는다
        logger.exception("Qdrant upsert 실패: item=%s", item.id)
        return False


def update_payload(item) -> None:
    """태깅 수정·확정 시 payload 동기화 (best-effort)."""
    try:
        _client().set_payload(
            collection_name=COLLECTION,
            payload={
                "category_large": item.category_large,
                "category_small": item.category_small,
                "season": item.season,
                "style": item.style,
                "color": item.color,
                "layer_role": item.layer_role,
                "confirmed": item.confirmed,
            },
            points=[str(item.id)],
        )
    except Exception:  # noqa: BLE001
        logger.exception("Qdrant payload 갱신 실패: item=%s", item.id)


def delete_item(item_id) -> None:
    """아이템 삭제 시 벡터도 제거 (best-effort)."""
    try:
        _client().delete(collection_name=COLLECTION, points_selector=[str(item_id)])
    except Exception:  # noqa: BLE001
        logger.exception("Qdrant 삭제 실패: item=%s", item_id)
