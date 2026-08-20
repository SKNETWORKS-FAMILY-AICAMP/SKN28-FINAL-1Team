"""원칙에 어느 모델이 만들었는지 남기는 규칙.

Gemini 할당량이 막혀 같은 run을 OpenAI로 이어 돌린 적이 있다. 그때 산출물 86건이
전부 `gemini-3.5-flash`로 기록됐다 — 절반 이상이 OpenAI였는데도. 캐시 키와
`model_version`이 둘 다 `settings.gemini_model`로 고정돼 있었기 때문이다.

두 가지가 문제였다.

- **기록이 사실과 다르다.** 나중에 재현하거나 품질을 공급자별로 비교할 수 없다.
- **캐시가 공급자를 넘나든다.** 모델을 바꿔도 키가 같아서, 다른 모델의 결과를
  조용히 재사용한다.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from ml.golden_set.config import GoldenSettings
from ml.golden_set.principles import synthesize_principles


def _settings(**overrides) -> GoldenSettings:
    values = {
        "gemini_api_key": "test",
        "gemini_api_base_url": "https://example.test",
        "gemini_model": "gemini-3.5-flash",
        "gemini_timeout_seconds": 1,
        "max_multimodal_calls": 1,
        "fashion_model_id": "f",
        "text_model_id": "t",
        "device": "cpu",
        "embedding_batch_size": 1,
        "s3_bucket": "b",
    }
    values.update(overrides)
    return GoldenSettings(**values)


class FakeClient:
    """모델 이름을 노출하는 최소 PrincipleClient."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.calls = 0

    def generate_text_json(self, *, prompt, system_instruction, schema) -> dict[str, Any]:
        self.calls += 1
        marker = prompt.index("[")
        evidence, _ = json.JSONDecoder().raw_decode(prompt[marker:])
        return {
            "principles": [
                {
                    "principle_key": "p01",
                    "axis": evidence[0]["claim"]["axis"],
                    "statement": "두 코디에서 반복되는 관계가 있다.",
                    "applies_when": {
                        "style_intents": ["캐주얼"],
                        "pursuit_images": [],
                        "seasons": [],
                        "occasions": [],
                        "garment_conditions": ["무채색 반복"],
                        "unavailable_context": ["TPO"],
                    },
                    "exceptions": ["강한 대비가 의도인 경우"],
                    "principle_type": "SOFT_PRINCIPLE",
                    "knowledge_role": "EXPLANATION_ONLY",
                    "model_confidence": 0.5,
                    "evidence": [
                        {"golden_id": row["golden_id"], "claim_id": row["claim"]["claim_id"]}
                        for row in evidence
                    ],
                }
            ]
        }


def _claim(claim_id: str) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "axis": "A1_COLOR_HARMONY",
        "statement": claim_id + " 문장",
        "evidence_region_ids": ["top"],
        "human_review": {"reviewer_count": 2},
    }


class ProvenanceTests(unittest.TestCase):
    def _run(self, run_dir: Path, client):
        (run_dir).mkdir(parents=True, exist_ok=True)
        (run_dir / "clusters.jsonl").write_text(
            "\n".join(
                json.dumps({"golden_id": gid, "cluster_id": "캐주얼"}, ensure_ascii=False)
                for gid in ("g-1", "g-2")
            ) + "\n",
            encoding="utf-8",
        )
        (run_dir / "approved_claims.jsonl").write_text("", encoding="utf-8")

        def fake_collect(**kwargs):
            return (
                {"g-1": [_claim("C1")], "g-2": [_claim("C1")]},
                {"accepted_image_count": 2, "accepted_claim_count": 2},
            )

        import ml.golden_set.principles as module

        original = module.collect_accepted_claims
        module.collect_accepted_claims = fake_collect
        try:
            return synthesize_principles(
                run_dir=run_dir,
                observation_reviews_csv=run_dir / "obs.csv",
                claim_reviews_csv=run_dir / "claim.csv",
                settings=_settings(),
                client=client,
            )
        finally:
            module.collect_accepted_claims = original

    def test_actual_model_is_recorded_not_the_gemini_setting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient("gpt-4o-mini")
            principles = self._run(Path(tmp) / "run", client)
        self.assertEqual(principles[0]["model_version"], "gpt-4o-mini")
        self.assertEqual(principles[0]["provider"], "openai")

    def test_cache_does_not_cross_providers(self) -> None:
        """모델이 다르면 캐시 키도 달라야 한다 — 다른 모델 결과를 재사용하면 안 된다."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            first = FakeClient("gpt-4o-mini")
            self._run(run_dir, first)
            second = FakeClient("gpt-4o")
            self._run(run_dir, second)
            self.assertEqual(first.calls, 1)
            self.assertEqual(second.calls, 1)   # 캐시를 재사용했다면 0이 된다

    def test_same_model_reuses_the_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._run(run_dir, FakeClient("gpt-4o-mini"))
            again = FakeClient("gpt-4o-mini")
            self._run(run_dir, again)
            self.assertEqual(again.calls, 0)

    def test_client_without_model_falls_back_to_settings(self) -> None:
        """모델 이름을 안 내놓는 클라이언트도 예전처럼 돌아야 한다."""

        class Bare(FakeClient):
            def __init__(self) -> None:
                super().__init__("")
                del self.model

        with tempfile.TemporaryDirectory() as tmp:
            principles = self._run(Path(tmp) / "run", Bare())
        self.assertEqual(principles[0]["model_version"], "gemini-3.5-flash")


if __name__ == "__main__":
    unittest.main()
