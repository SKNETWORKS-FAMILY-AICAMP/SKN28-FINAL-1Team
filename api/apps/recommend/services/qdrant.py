"""Qdrant 클라이언트와 컬렉션 스키마 정의.

컬렉션 스키마의 단일 소유자다 (PG 스키마를 Django migration이 소유하는 것과
같은 원칙). 컬렉션 생성/변경은 반드시 `manage.py init_qdrant`를 통해 한다.

설계 근거: docs/fashion-rag-embedding-retriever_2.md
- 한 포인트에 named vector 2개(image=FashionSigLIP, text=BGE-M3)를 저장한다.
- 하드 필터에 쓰이는 payload 필드는 반드시 인덱스를 만든다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from functools import lru_cache

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client import models as qm

IMAGE_VECTOR = "image"
TEXT_VECTOR = "text"

# point ID 생성용 고정 네임스페이스. 같은 원본 키는 항상 같은 UUID가 되어
# 재실행 시 upsert가 멱등하게 동작한다. 절대 변경하지 않는다.
_POINT_NAMESPACE = uuid.UUID("6b2c1f3a-9d4e-4c8b-8a71-2f0e5d9c3b17")


def point_id(source_key: str) -> str:
    """원본 식별자(naver_product_id 등) → 결정적 Qdrant point ID."""
    return str(uuid.uuid5(_POINT_NAMESPACE, source_key))


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    vectors: dict[str, int]                      # named vector → 차원
    payload_indexes: dict[str, str] = field(default_factory=dict)  # 필드 → 스키마


def _image_dim() -> int:
    return settings.QDRANT_IMAGE_VECTOR_DIM


def _text_dim() -> int:
    return settings.QDRANT_TEXT_VECTOR_DIM


# 상품·옷장이 같은 태그 체계를 쓰므로 필터 인덱스도 동일하게 맞춘다
# (크로스 컬렉션 질의가 같은 필터 언어로 동작해야 한다).
_ITEM_TAG_INDEXES: dict[str, str] = {
    "category_large": "keyword",
    "category_small": "keyword",
    "layer_role": "keyword",
    "season": "keyword",
    "style": "keyword",
    "color": "keyword",
    "fit": "keyword",
    "pattern": "keyword",
    "material": "keyword",
}


def collection_specs() -> list[CollectionSpec]:
    """차원이 settings에서 오므로 모듈 상수 대신 함수로 정의한다."""
    return [
        CollectionSpec(
            name="products",
            vectors={IMAGE_VECTOR: _image_dim(), TEXT_VECTOR: _text_dim()},
            payload_indexes={**_ITEM_TAG_INDEXES, "lprice": "integer"},
        ),
        CollectionSpec(
            name="wardrobe",
            vectors={IMAGE_VECTOR: _image_dim(), TEXT_VECTOR: _text_dim()},
            payload_indexes={**_ITEM_TAG_INDEXES, "user_id": "keyword"},
        ),
        CollectionSpec(
            name="knowledge",
            vectors={TEXT_VECTOR: _text_dim()},
            payload_indexes={
                "knowledge_type": "keyword",
                "body_type": "keyword",
                "skin_tone": "keyword",
                "season": "keyword",
                "occasion": "keyword",
            },
        ),
    ]


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    """프로세스당 1개 재사용. gunicorn 워커별로 각자 생성된다."""
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=settings.QDRANT_TIMEOUT,
    )


def ensure_collections(client: QdrantClient, *, recreate: bool = False) -> list[str]:
    """스키마 정의대로 컬렉션을 생성한다. 이미 있으면 건드리지 않는다(멱등).

    Returns: 이번 호출에서 새로 생성한 컬렉션 이름 목록.
    """
    created: list[str] = []
    for spec in collection_specs():
        if recreate and client.collection_exists(spec.name):
            client.delete_collection(spec.name)
        if client.collection_exists(spec.name):
            continue
        client.create_collection(
            collection_name=spec.name,
            vectors_config={
                vec_name: qm.VectorParams(size=dim, distance=qm.Distance.COSINE)
                for vec_name, dim in spec.vectors.items()
            },
        )
        for fld, schema in spec.payload_indexes.items():
            client.create_payload_index(
                collection_name=spec.name, field_name=fld, field_schema=schema
            )
        created.append(spec.name)
    return created
