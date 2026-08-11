from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase
from qdrant_client import QdrantClient
from qdrant_client import models as qm

from apps.recommend.services import vocabulary
from apps.recommend.services.body_profile import (
    INVERTED_TRIANGLE,
    NORMAL,
    ROUND,
    TRIANGLE,
    BodyProfile,
    build_profile,
)
from apps.recommend.services.retriever import (
    GoldenOutfitRetriever,
    RetrievalRequest,
    build_filter,
)
from apps.recommend.services.text_embedding import (
    TextEmbeddingClient,
    TextEmbeddingError,
    TextEmbeddingResult,
)


class FakeEmbeddingClient:
    def __init__(self, vector: tuple[float, ...] = (0.1, 0.2, 0.3)) -> None:
        self.vector = vector
        self.queries: list[str] = []

    def embed(self, text: str) -> TextEmbeddingResult:
        self.queries.append(text)
        return TextEmbeddingResult(
            vector=self.vector,
            model="BAAI/bge-m3",
            version="bge-m3-test-v1",
        )


class FakeQdrantClient:
    def __init__(self, *, hits=None, points=None, retrieved=None) -> None:
        self.hits = list(hits or [])
        self.points = list(points or [])
        self.retrieved = list(retrieved or [])
        self.query_calls: list[dict] = []
        self.scroll_calls: list[dict] = []
        self.retrieve_calls: list[dict] = []

    def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        return SimpleNamespace(points=self.hits)

    def scroll(self, **kwargs):
        self.scroll_calls.append(kwargs)
        return self.points, None

    def retrieve(self, **kwargs):
        self.retrieve_calls.append(kwargs)
        requested = {str(value) for value in kwargs["ids"]}
        return [point for point in self.retrieved if str(point.id) in requested]


def hit(point_id: str, score: float, payload: dict):
    return SimpleNamespace(id=point_id, score=score, payload=payload)


class BodyProfileTests(SimpleTestCase):
    def test_available_measurements_build_independent_profile_axes(self) -> None:
        profile = build_profile(
            {
                "height": 175,
                "weight": 70,
                "shoulder": 48,
                "hip": 42,
                "waist": 34,
                "thigh": 55,
                "calf": 38,
            }
        )

        self.assertEqual(profile.silhouette, INVERTED_TRIANGLE)
        self.assertEqual(profile.bmi_band, NORMAL)
        self.assertEqual(profile.ratios["leg_volume"], "balanced")

    def test_missing_measurements_are_not_guessed(self) -> None:
        profile = build_profile({"shoulder": 38, "hip": 45})

        self.assertEqual(profile.silhouette, TRIANGLE)
        self.assertIn("waist", profile.missing)
        self.assertIsNone(profile.bmi)


class VocabularyTests(SimpleTestCase):
    def test_same_code_is_translated_by_category(self) -> None:
        translated = vocabulary.translate(
            {"top_lengths": ["short"], "sleeves": ["short"]}
        )

        self.assertEqual(translated.tags["length"], {"기본"})
        self.assertEqual(translated.tags["sleeve"], {"반팔"})

    def test_unsupported_taxonomy_value_is_reported(self) -> None:
        translated = vocabulary.translate(
            {"styles": ["classic", "minimal"], "necklines": ["vneck"]}
        )

        self.assertEqual(translated.tags["style"], {"미니멀"})
        self.assertEqual(
            set(translated.unmapped),
            {"styles:classic", "necklines"},
        )


class GoldenOutfitRetrieverTests(SimpleTestCase):
    def test_named_text_vector_search_works_with_real_qdrant_client(self) -> None:
        client = QdrantClient(":memory:")
        client.create_collection(
            collection_name="outfit_goldenset",
            vectors_config={
                "image": qm.VectorParams(size=3, distance=qm.Distance.COSINE),
                "text": qm.VectorParams(size=3, distance=qm.Distance.COSINE),
            },
        )
        client.upsert(
            collection_name="outfit_goldenset",
            points=[
                qm.PointStruct(
                    id=1,
                    vector={"image": [0.0, 1.0, 0.0], "text": [1.0, 0.0, 0.0]},
                    payload={"golden_id": "closest"},
                ),
                qm.PointStruct(
                    id=2,
                    vector={"image": [1.0, 0.0, 0.0], "text": [0.0, 1.0, 0.0]},
                    payload={"golden_id": "farther"},
                ),
            ],
        )
        retriever = GoldenOutfitRetriever(
            client=client,
            embedding_client=FakeEmbeddingClient((1.0, 0.0, 0.0)),
        )

        result = retriever.retrieve(RetrievalRequest(query_text="미니멀", limit=2))

        self.assertEqual(result.candidates[0].golden_id, "closest")

    def test_real_qdrant_accepts_legacy_status_and_current_dataset_status(self) -> None:
        client = QdrantClient(":memory:")
        client.create_collection(
            collection_name="outfit_goldenset",
            vectors_config={
                "image": qm.VectorParams(size=3, distance=qm.Distance.COSINE),
                "text": qm.VectorParams(size=3, distance=qm.Distance.COSINE),
            },
        )
        client.upsert(
            collection_name="outfit_goldenset",
            points=[
                qm.PointStruct(
                    id=1,
                    vector={"image": [1.0, 0.0, 0.0], "text": [1.0, 0.0, 0.0]},
                    payload={"golden_id": "legacy", "status": "APPROVED"},
                ),
                qm.PointStruct(
                    id=2,
                    vector={"image": [1.0, 0.0, 0.0], "text": [1.0, 0.0, 0.0]},
                    payload={
                        "golden_id": "current",
                        "dataset_status": "approved",
                    },
                ),
                qm.PointStruct(
                    id=3,
                    vector={"image": [1.0, 0.0, 0.0], "text": [1.0, 0.0, 0.0]},
                    payload={"golden_id": "draft", "status": "DRAFT"},
                ),
            ],
        )

        result = GoldenOutfitRetriever(client=client).retrieve(
            RetrievalRequest(dataset_statuses=("approved",), limit=10)
        )

        self.assertEqual(
            {candidate.golden_id for candidate in result.candidates},
            {"legacy", "current"},
        )

    def test_query_text_is_embedded_and_sent_to_text_vector_search(self) -> None:
        client = FakeQdrantClient(
            hits=[hit("point-1", 0.82, {"golden_id": "golden-1"})]
        )
        embedding = FakeEmbeddingClient()
        retriever = GoldenOutfitRetriever(
            client=client,
            embedding_client=embedding,
        )

        result = retriever.retrieve(
            RetrievalRequest(query_text="비 오는 날 출근룩", limit=3)
        )

        self.assertEqual(embedding.queries, ["비 오는 날 출근룩"])
        self.assertEqual(client.query_calls[0]["using"], "text")
        self.assertEqual(client.query_calls[0]["query"], [0.1, 0.2, 0.3])
        self.assertEqual(result.search_mode, "text")
        self.assertEqual(result.embedding_model, "BAAI/bge-m3")
        self.assertEqual(result.embedding_version, "bge-m3-test-v1")
        self.assertEqual(result.candidates[0].golden_id, "golden-1")

    def test_preference_score_can_rerank_similar_candidates(self) -> None:
        client = FakeQdrantClient(
            hits=[
                hit(
                    "minimal",
                    0.75,
                    {"golden_id": "g-minimal", "style": ["미니멀"]},
                ),
                hit(
                    "street",
                    0.80,
                    {"golden_id": "g-street", "style": ["스트릿"]},
                ),
            ]
        )
        retriever = GoldenOutfitRetriever(
            client=client,
            embedding_client=FakeEmbeddingClient(),
        )
        pursuit = {
            "preferred": {"styles": ["minimal"]},
            "avoided": {},
        }

        result = retriever.retrieve(
            RetrievalRequest(query_text="깔끔한 코디", pursuit=pursuit, limit=2)
        )

        self.assertEqual(result.candidates[0].golden_id, "g-minimal")
        self.assertEqual(result.candidates[0].score, 105.0)
        self.assertTrue(result.candidates[0].reasons)

    def test_avoided_item_tag_is_hard_excluded_after_search(self) -> None:
        client = FakeQdrantClient(
            hits=[
                hit(
                    "black",
                    0.90,
                    {
                        "golden_id": "g-black",
                        "items": [{"color": "블랙"}],
                    },
                ),
                hit(
                    "white",
                    0.80,
                    {
                        "golden_id": "g-white",
                        "items": [{"color": "화이트"}],
                    },
                ),
            ]
        )
        pursuit = {
            "preferred": {},
            "avoided": {"colors": ["black"]},
        }

        result = GoldenOutfitRetriever(
            client=client,
            embedding_client=FakeEmbeddingClient(),
        ).retrieve(RetrievalRequest(query_text="코디", pursuit=pursuit))

        self.assertEqual(
            [candidate.golden_id for candidate in result.candidates],
            ["g-white"],
        )

    def test_presentation_group_is_only_filtered_when_explicit(self) -> None:
        self.assertIsNone(build_filter(RetrievalRequest()))

        query_filter = build_filter(
            RetrievalRequest(presentation_groups=("masculine",))
        )

        self.assertIsNotNone(query_filter)
        self.assertEqual(query_filter.must[0].key, "presentation_group")
        self.assertEqual(query_filter.must[0].match.any, ["man", "unisex"])

    def test_legacy_and_current_dataset_status_fields_are_both_supported(self) -> None:
        query_filter = build_filter(RetrievalRequest(dataset_statuses=("approved",)))

        status_filter = query_filter.must[0]
        self.assertEqual(
            {condition.key for condition in status_filter.should},
            {"status", "dataset_status"},
        )
        self.assertIn("APPROVED", status_filter.should[0].match.any)

    def test_weather_and_occasion_are_soft_score_reasons(self) -> None:
        client = FakeQdrantClient(
            points=[
                SimpleNamespace(
                    id="summer-office",
                    payload={
                        "golden_id": "g-1",
                        "human_score": 70,
                        "season": ["여름"],
                        "occasion": ["출근"],
                    },
                )
            ]
        )

        result = GoldenOutfitRetriever(client=client).retrieve(
            RetrievalRequest(
                weather={"temperature": 27},
                occasion="출근",
            )
        )

        self.assertEqual(result.search_mode, "filter")
        self.assertEqual(result.candidates[0].score, 90.0)
        self.assertEqual(len(result.candidates[0].reasons), 2)

    def test_explicit_season_takes_priority_over_weather_season(self) -> None:
        client = FakeQdrantClient(
            points=[
                SimpleNamespace(
                    id="spring",
                    payload={
                        "golden_id": "g-spring",
                        "season": ["봄"],
                    },
                )
            ]
        )

        result = GoldenOutfitRetriever(client=client).retrieve(
            RetrievalRequest(season="봄", weather={"temperature": 28})
        )

        self.assertEqual(result.candidates[0].score, 10.0)
        self.assertIn("봄 조건과 일치", result.candidates[0].reasons[0].text)

    def test_item_point_ids_are_hydrated_before_body_and_weather_scoring(self) -> None:
        item = SimpleNamespace(
            id="item-top",
            payload={
                "category_large": "상의",
                "fit": "슬림핏",
                "material": "니트",
            },
        )
        client = FakeQdrantClient(
            points=[
                SimpleNamespace(
                    id="outfit",
                    payload={
                        "golden_id": "g-1",
                        "item_point_ids": ["item-top"],
                    },
                )
            ],
            retrieved=[item],
        )

        result = GoldenOutfitRetriever(client=client).retrieve(
            RetrievalRequest(
                body=BodyProfile(silhouette=ROUND),
                weather={"temperature": 28},
                hard_filter=False,
            )
        )

        candidate = result.candidates[0]
        self.assertEqual(candidate.items[0]["fit"], "슬림핏")
        self.assertTrue(any(reason.source == "rule" for reason in candidate.reasons))
        self.assertTrue(any(reason.source == "weather" for reason in candidate.reasons))

    def test_image_and_text_query_cannot_be_mixed_implicitly(self) -> None:
        with self.assertRaisesMessage(ValueError, "동시에 사용할 수 없습니다"):
            GoldenOutfitRetriever(client=FakeQdrantClient()).retrieve(
                RetrievalRequest(query_text="코디", image_vector=[0.1, 0.2])
            )


class TextEmbeddingClientTests(SimpleTestCase):
    def test_response_contract_is_validated(self) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "model": "BAAI/bge-m3",
            "version": "bge-m3-v1",
            "vectors": [[0.1, 0.2, 0.3]],
        }
        session = Mock()
        session.post.return_value = response
        client = TextEmbeddingClient(
            url="http://embedding.internal/v1/embeddings/text",
            token="secret",
            timeout=10,
            expected_dimension=3,
            session=session,
        )

        result = client.embed("출근 코디")

        self.assertEqual(result.vector, (0.1, 0.2, 0.3))
        self.assertEqual(
            session.post.call_args.kwargs["headers"],
            {"Authorization": "Bearer secret"},
        )

    def test_wrong_vector_dimension_is_rejected(self) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "model": "BAAI/bge-m3",
            "version": "bge-m3-v1",
            "vectors": [[0.1, 0.2]],
        }
        session = Mock()
        session.post.return_value = response
        client = TextEmbeddingClient(
            url="http://embedding.internal/v1/embeddings/text",
            token="secret",
            timeout=10,
            expected_dimension=3,
            session=session,
        )

        with self.assertRaisesMessage(TextEmbeddingError, "차원 불일치"):
            client.embed("출근 코디")
