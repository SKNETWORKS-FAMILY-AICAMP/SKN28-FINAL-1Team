"""승인된 골든셋 원칙을 추천 설명 재료로 꺼내오는 경로.

원칙은 사람이 검수해 승인한 문장이고, 추천 이유를 쓸 때 근거로 쓴다. 여기서 지켜야
할 것이 세 가지다.

- **DRAFT를 끌어오면 안 된다.** 검수자가 "반례가 더 필요하다"고 판단한 문장이다.
- **스타일이 맞는 원칙이 먼저다.** 벡터 유사도가 더 높아도 순서를 뒤집지 않는다.
- **없어도 추천은 진행한다.** 골든셋 1차 사이클이라 스타일에 따라 원칙이 0건일 수
  있고, 임베딩 서비스나 Qdrant가 죽어도 추천 자체를 막으면 안 된다.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.recommend.services.retriever import (
    PRINCIPLE_WIDEN_THRESHOLD,
    _principle_filter,
    retrieve_principles,
)
from apps.recommend.services.text_embedding import (
    TextEmbeddingError,
    TextEmbeddingResult,
)


class FakeEmbedding:
    def embed(self, text: str) -> TextEmbeddingResult:
        return TextEmbeddingResult(vector=(0.1, 0.2), model="m", version="v")


class BrokenEmbedding:
    def embed(self, text: str) -> TextEmbeddingResult:
        raise TextEmbeddingError("임베딩 서비스 없음")


def _hit(key: str, style: str, score: float):
    return SimpleNamespace(
        id=key,
        score=score,
        payload={
            "principle_key": key,
            "statement": key + " 문장",
            "axis": "A1_COLOR_HARMONY",
            "style": [style],
            "exceptions": ["예외"],
            "support_image_count": 3,
        },
    )


class FakeQdrant:
    """스타일 필터가 걸렸는지에 따라 다른 결과를 준다."""

    def __init__(self, narrow, wide):
        self.narrow = narrow
        self.wide = wide
        self.calls: list[bool] = []

    def query_points(self, *, query_filter, limit, **kwargs):
        filtered = any(
            getattr(condition, "key", "") == "style"
            for condition in query_filter.must
        )
        self.calls.append(filtered)
        rows = self.narrow if filtered else self.wide
        return SimpleNamespace(points=rows[:limit])


class PrincipleFilterTests(SimpleTestCase):
    def test_only_approved_principles_are_eligible(self) -> None:
        conditions = {
            condition.key: condition.match.value
            for condition in _principle_filter(()).must
            if hasattr(condition.match, "value")
        }
        self.assertEqual(conditions["status"], "APPROVED")
        self.assertEqual(conditions["knowledge_type"], "golden_principle")

    def test_style_condition_is_added_only_when_given(self) -> None:
        keys = [condition.key for condition in _principle_filter(()).must]
        self.assertNotIn("style", keys)
        keys = [condition.key for condition in _principle_filter(["댄디"]).must]
        self.assertIn("style", keys)

    def test_blank_styles_are_ignored(self) -> None:
        keys = [condition.key for condition in _principle_filter(["", "  "]).must]
        self.assertNotIn("style", keys)


class RetrievePrinciplesTests(SimpleTestCase):
    def _run(self, narrow, wide, **kwargs):
        client = FakeQdrant(narrow, wide)
        result = retrieve_principles(
            query="가을 데이트룩",
            client=client,
            embedding_client=FakeEmbedding(),
            **kwargs,
        )
        return result, client

    def test_style_match_is_enough_when_there_are_plenty(self) -> None:
        narrow = [_hit("p1", "댄디", 0.5), _hit("p2", "댄디", 0.4)]
        result, client = self._run(narrow, [_hit("w1", "포멀", 0.9)], styles=["댄디"])
        self.assertEqual([row.principle_key for row in result], ["p1", "p2"])
        self.assertEqual(client.calls, [True])

    def test_widens_when_the_style_has_too_few(self) -> None:
        """시크는 승인 원칙이 1건뿐이다. 그대로 두면 설명 재료가 없다."""
        narrow = [_hit("p1", "시크", 0.4)]
        wide = [_hit("w1", "포멀", 0.9), _hit("w2", "빈티지", 0.8)]
        result, client = self._run(narrow, wide, styles=["시크"], limit=3)
        self.assertEqual([row.principle_key for row in result], ["p1", "w1", "w2"])
        self.assertEqual(client.calls, [True, False])

    def test_style_match_stays_first_even_with_a_lower_score(self) -> None:
        narrow = [_hit("p1", "시크", 0.1)]
        wide = [_hit("w1", "포멀", 0.99)]
        result, _ = self._run(narrow, wide, styles=["시크"], limit=2)
        self.assertEqual(result[0].principle_key, "p1")
        self.assertFalse(result[0].widened)
        self.assertTrue(result[1].widened)

    def test_widened_result_does_not_duplicate_the_narrow_one(self) -> None:
        narrow = [_hit("p1", "시크", 0.4)]
        wide = [_hit("p1", "시크", 0.4), _hit("w1", "포멀", 0.3)]
        result, _ = self._run(narrow, wide, styles=["시크"], limit=3)
        self.assertEqual([row.principle_key for row in result], ["p1", "w1"])

    def test_no_style_searches_without_the_filter(self) -> None:
        result, client = self._run([], [_hit("w1", "포멀", 0.5)], styles=[])
        self.assertEqual([row.principle_key for row in result], ["w1"])
        self.assertEqual(client.calls, [False])

    def test_style_without_any_principle_falls_back(self) -> None:
        """베이직처럼 승인 원칙이 0건인 스타일."""
        result, client = self._run([], [_hit("w1", "포멀", 0.5)], styles=["베이직"])
        self.assertEqual([row.principle_key for row in result], ["w1"])
        self.assertTrue(result[0].widened)
        self.assertEqual(client.calls, [True, False])

    def test_embedding_failure_returns_empty_instead_of_raising(self) -> None:
        """임베딩 서비스가 없어도 추천은 계속돼야 한다."""
        result = retrieve_principles(
            query="가을 데이트룩",
            styles=["댄디"],
            client=FakeQdrant([], []),
            embedding_client=BrokenEmbedding(),
        )
        self.assertEqual(result, ())

    def test_qdrant_failure_returns_empty_instead_of_raising(self) -> None:
        class Broken:
            def query_points(self, **kwargs):
                raise RuntimeError("Qdrant 접속 실패")

        result = retrieve_principles(
            query="가을 데이트룩",
            styles=["댄디"],
            client=Broken(),
            embedding_client=FakeEmbedding(),
        )
        self.assertEqual(result, ())

    def test_blank_query_skips_the_search_entirely(self) -> None:
        client = FakeQdrant([_hit("p1", "댄디", 0.5)], [])
        result = retrieve_principles(
            query="   ",
            styles=["댄디"],
            client=client,
            embedding_client=FakeEmbedding(),
        )
        self.assertEqual(result, ())
        self.assertEqual(client.calls, [])

    def test_prompt_context_hides_internal_fields(self) -> None:
        result, _ = self._run([_hit("p1", "댄디", 0.5)], [], styles=["댄디"], limit=1)
        context = result[0].as_prompt_context()
        self.assertEqual(
            sorted(context), ["axis", "exceptions", "statement", "styles"]
        )
        self.assertNotIn("principle_key", context)

    def test_threshold_is_the_documented_value(self) -> None:
        self.assertEqual(PRINCIPLE_WIDEN_THRESHOLD, 2)


class OrchestratorWiringTests(SimpleTestCase):
    def test_styles_are_collected_from_item_attributes(self) -> None:
        from apps.chat.services.orchestrator import _principle_styles_from_payload

        payload = {
            "compositions": [
                {"items": [{"attributes": {"style": ["댄디", "포멀"]}}]},
                {"items": [{"attributes": {"style": "댄디"}}, {"attributes": {}}]},
            ]
        }
        self.assertEqual(_principle_styles_from_payload(payload), ["댄디", "포멀"])

    def test_principle_context_survives_a_retrieval_failure(self) -> None:
        from apps.chat.services import orchestrator

        with patch.object(
            orchestrator, "retrieve_principles", side_effect=RuntimeError("boom")
        ):
            context = orchestrator._principle_context({}, "가을 데이트룩", {})
        self.assertEqual(context, [])

    def test_principle_context_is_empty_without_a_query(self) -> None:
        from apps.chat.services import orchestrator

        self.assertEqual(orchestrator._principle_context({}, "", {}), [])
