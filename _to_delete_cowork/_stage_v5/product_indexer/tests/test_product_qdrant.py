from __future__ import annotations

import sys
import unittest
from pathlib import Path

from qdrant_client import QdrantClient

# indexer/ 를 import 루트로 잡아 product_indexer·util 패키지를 찾게 한다.
INDEXER_ROOT = Path(__file__).resolve().parents[2]
if str(INDEXER_ROOT) not in sys.path:
    sys.path.insert(0, str(INDEXER_ROOT))

from product_indexer.product_qdrant import (
    build_point,
    ensure_collection,
    product_point_id,
)


class ProductQdrantTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = QdrantClient(":memory:")

    def test_collection_and_named_vectors(self) -> None:
        ensure_collection(
            self.client,
            collection_name="products_test",
            image_dim=3,
            text_dim=4,
        )

        collection = self.client.get_collection("products_test")
        vectors = collection.config.params.vectors

        self.assertEqual(vectors["image"].size, 3)
        self.assertEqual(vectors["text"].size, 4)

    def test_point_id_is_stable_and_point_can_be_upserted(self) -> None:
        point_id = product_point_id("eleven", "123")
        self.assertEqual(point_id, product_point_id("eleven", "123"))
        self.assertNotEqual(point_id, product_point_id("naver", "123"))

        ensure_collection(
            self.client,
            collection_name="products_test",
            image_dim=3,
            text_dim=4,
        )
        point = build_point(
            source="eleven",
            external_product_id="123",
            image_vector=[0.1, 0.2, 0.3],
            text_vector=[0.1, 0.2, 0.3, 0.4],
            payload={"title": "테스트 상품"},
        )
        self.client.upsert(collection_name="products_test", points=[point])

        self.assertEqual(
            self.client.count(
                collection_name="products_test",
                exact=True,
            ).count,
            1,
        )


if __name__ == "__main__":
    unittest.main()
