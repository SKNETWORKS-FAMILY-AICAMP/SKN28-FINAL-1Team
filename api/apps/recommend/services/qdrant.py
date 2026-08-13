"""Qdrant 클라이언트와 컬렉션 스키마 정의.

컬렉션 스키마의 단일 소유자다 (PG 스키마를 Django migration이 소유하는 것과
같은 원칙). 컬렉션 생성/변경은 반드시 `manage.py init_qdrant`를 통해 한다.

설계 근거: docs/fashion-rag-embedding-retriever_2.md
- 한 포인트에 named vector 2개(image=FashionSigLIP, text=BGE-M3)를 저장한다.
- 하드 필터에 쓰이는 payload 필드는 반드시 인덱스를 만든다.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from functools import lru_cache

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client import models as qm

IMAGE_VECTOR = "image"
TEXT_VECTOR = "text"
GOLDEN_OUTFIT_COLLECTION = "outfit_goldenset"
GOLDEN_ITEM_COLLECTION = "goldenset_items"
WARDROBE_ITEM_COLLECTION = os.getenv("QDRANT_WARDROBE_COLLECTION", "wardrobe_items")

# point ID 생성용 고정 네임스페이스. 같은 원본 키는 항상 같은 UUID가 되어
# 재실행 시 upsert가 멱등하게 동작한다. 절대 변경하지 않는다.
# 오프라인 파이프라인(ml/golden_set/point_ids.py)이 같은 값을 복제해서 쓴다 —
# Django 없이 도는 패키지라 이 모듈을 import할 수 없다. 한쪽만 바꾸면 안 된다.
_POINT_NAMESPACE = uuid.UUID("6b2c1f3a-9d4e-4c8b-8a71-2f0e5d9c3b17")


def point_id(source_key: str) -> str:
    """원본 식별자(naver_product_id 등) → 결정적 Qdrant point ID."""
    return str(uuid.uuid5(_POINT_NAMESPACE, source_key))


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    vectors: dict[str, int]  # named vector → 차원
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
        # apps.wardrobe.services.vectors가 사용자별 등록 아이템을 적재하는 컬렉션.
        # 추천용 wardrobe 컬렉션과는 소유자 필터의 타입·적재 경로가 달라 분리한다.
        CollectionSpec(
            name="wardrobe_items",
            vectors={IMAGE_VECTOR: _image_dim(), TEXT_VECTOR: _text_dim()},
            payload_indexes={**_ITEM_TAG_INDEXES, "user_id": "integer"},
        ),
        CollectionSpec(
            name="knowledge",
            vectors={TEXT_VECTOR: _text_dim()},
            payload_indexes={
                "knowledge_type": "keyword",
                "dimension": "keyword",
                "axis": "keyword",
                "status": "keyword",
                "knowledge_role": "keyword",
                "principle_type": "keyword",
                "eligible_for_scoring": "bool",
                "source": "keyword",
                "dataset_version": "keyword",
                "style": "keyword",
                "body_type": "keyword",
                "skin_tone": "keyword",
                "season": "keyword",
                "occasion": "keyword",
            },
        ),
        # 골든 코디 1장 = 포인트 1개. payload의 items[]가 아이템 포인트로 가는
        # 다리다 (아이템 교체 질의는 여기서 goldenset_items로 넘어간다).
        CollectionSpec(
            name=GOLDEN_OUTFIT_COLLECTION,
            vectors={IMAGE_VECTOR: _image_dim(), TEXT_VECTOR: _text_dim()},
            payload_indexes={
                "source": "keyword",
                "dataset_version": "keyword",
                "status": "keyword",
                "split": "keyword",
                "presentation_group": "keyword",
                "style": "keyword",
                "season": "keyword",
                "occasion": "keyword",
                "score_band": "keyword",
                "human_score": "float",
                "anchor_scope": "keyword",
                "exposable": "bool",
                "golden_id": "keyword",
                # 코디 단계에서 "상의가 있는 코디만" 같은 사전 필터를 걸 수 있게
                # 소속 아이템의 역할·대분류를 코디 payload에도 인덱싱한다.
                "item_layer_roles": "keyword",
                "item_categories": "keyword",
            },
        ),
        # 골든 코디에서 분리한 의상 아이템. 태그 인덱스를 products/wardrobe와
        # 똑같이 맞춰야 "이 코디의 상의를 옷장/상품 아이템으로 교체"가 같은
        # 필터 언어로 성립한다.
        CollectionSpec(
            name=GOLDEN_ITEM_COLLECTION,
            vectors={IMAGE_VECTOR: _image_dim(), TEXT_VECTOR: _text_dim()},
            payload_indexes={
                **_ITEM_TAG_INDEXES,
                "source": "keyword",
                "dataset_version": "keyword",
                "split": "keyword",
                "exposable": "bool",
                "item_key": "keyword",
                "outfit_golden_id": "keyword",
                "outfit_point_id": "keyword",
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
    """스키마 정의대로 컬렉션과 누락된 payload 인덱스를 수렴시킨다.

    Returns: 이번 호출에서 새로 생성한 컬렉션 이름 목록.
    """
    created: list[str] = []
    for spec in collection_specs():
        if recreate and client.collection_exists(spec.name):
            client.delete_collection(spec.name)
        exists = client.collection_exists(spec.name)
        if not exists:
            client.create_collection(
                collection_name=spec.name,
                vectors_config={
                    vec_name: qm.VectorParams(size=dim, distance=qm.Distance.COSINE)
                    for vec_name, dim in spec.vectors.items()
                },
            )
            created.append(spec.name)

        # 컬렉션은 먼저 만들어졌지만 payload 인덱스가 뒤늦게 추가된 경우에도
        # init_qdrant 재실행만으로 스키마를 수렴시킨다. 기존 구현의 즉시 continue는
        # 이런 증분 변경을 영구히 놓쳤다.
        info = client.get_collection(spec.name)
        existing_indexes = set((info.payload_schema or {}).keys())
        for fld, schema in spec.payload_indexes.items():
            if fld in existing_indexes:
                continue
            client.create_payload_index(
                collection_name=spec.name, field_name=fld, field_schema=schema
            )
    return created
