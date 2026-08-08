from __future__ import annotations

import csv
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from ml.golden_set.analysis import analyze_run
from ml.golden_set.anchors import build_anchor_scores
from ml.golden_set.clustering import cluster_embeddings
from ml.golden_set.config import GoldenSettings
from ml.golden_set.embedding import embed_manifest_images
from ml.golden_set.manifest import build_manifest
from ml.golden_set.principles import (
    apply_principle_reviews,
    synthesize_principles,
)
from ml.golden_set.prompts import AXES
from ml.golden_set.qdrant_index import index_run
from ml.golden_set.review import collect_accepted_claims, create_review_templates


class FakeAnalysisClient:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_image(
        self,
        *,
        image_path: Path,
        prompt: str,
        system_instruction: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls += 1
        return {
            "observations": [
                {
                    "region_id": "r1",
                    "item_name": "상의",
                    "category_large": "상의",
                    "bbox": [100, 100, 800, 500],
                    "visible_attributes": ["블루", "레귤러핏"],
                    "uncertain_attributes": ["정확한 소재"],
                }
            ],
            "look_tags": {
                "style": ["캐주얼"],
                "season_cues": ["봄"],
                "colors": ["블루"],
                "overall_silhouette": "정돈된 실루엣",
            },
            "axis_assessability": [
                {
                    "axis": axis,
                    "mode": (
                        "FULL"
                        if axis
                        in {
                            "A1_COLOR_HARMONY",
                            "A2_SILHOUETTE_PROPORTION",
                            "A5_MATERIAL_PATTERN",
                            "A6_STYLE_COHESION",
                            "A7_COMPLETENESS_DETAIL",
                        }
                        else "UNAVAILABLE"
                    ),
                    "reason": "이미지 근거 기준",
                }
                for axis in AXES
            ],
            "claims": [
                {
                    "claim_id": "c1",
                    "axis": "A1_COLOR_HARMONY",
                    "statement": "낮은 채도의 색 구성이 안정적인 인상을 만든다.",
                    "evidence_region_ids": ["r1"],
                    "evidence_type": "OBJECT",
                    "relation_polarity": "HARMONY",
                    "contribution_direction": "CONTEXT_DEPENDENT",
                    "importance_rank": 1,
                    "model_confidence": 0.8,
                    "disagreement_risk": "low",
                }
            ],
            "relationship_summary": {
                "strongest_harmony_claim_id": "c1",
                "conflict_claim_ids": [],
                "no_conflict_reason": "이미지에서 뚜렷한 충돌 관계가 보이지 않음",
            },
            "minimum_edit": {
                "target_region_id": "r1",
                "target_attribute": "색 채도",
                "change": "색 채도를 높인다.",
                "tested_axis": "A1_COLOR_HARMONY",
                "expected_effect": "안정감이 줄고 강조가 커질 수 있다.",
                "expected_direction": "CHANGE_ONLY",
                "single_variable_change": True,
                "preserves_style_intent": True,
                "requires_visual_variant": True,
                "hypothesis_only": True,
            },
            "unassessable": [
                {"attribute_or_axis": "소재", "reason": "사진만으로 확정 불가"}
            ],
        }


class FakePrincipleClient:
    def generate_text_json(
        self,
        *,
        prompt: str,
        system_instruction: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        marker = prompt.index("[")
        evidence = json.loads(prompt[marker:])
        first = evidence[0]
        return {
            "principles": [
                {
                    "principle_key": "muted-color-balance",
                    "axis": first["claim"]["axis"],
                    "statement": "낮은 채도 색 조합은 안정적인 인상을 만들 수 있다.",
                    "applies_when": {
                        "style_intents": ["캐주얼"],
                        "pursuit_images": ["차분한"],
                        "seasons": [],
                        "occasions": [],
                        "garment_conditions": ["낮은 채도 색 반복"],
                        "unavailable_context": ["TPO"],
                    },
                    "exceptions": ["강한 대비가 의도인 경우"],
                    "principle_type": "SOFT_PRINCIPLE",
                    "knowledge_role": "NEEDS_COUNTEREXAMPLE",
                    "evidence": [
                        {
                            "golden_id": row["golden_id"],
                            "claim_id": row["claim"]["claim_id"],
                        }
                        for row in evidence
                    ],
                    "model_confidence": 0.55,
                }
            ]
        }


class FailingAnalysisClient:
    def __init__(self) -> None:
        self.calls = 0

    def analyze_image(self, **_: Any) -> dict[str, Any]:
        self.calls += 1
        raise RuntimeError("invalid response")


class GoldenCycleTests(unittest.TestCase):
    def test_full_pilot_cycle_with_two_independent_reviewers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "images"
            run_dir = root / "run-pilot"
            input_dir.mkdir()
            for index in range(6):
                _make_pattern_image(input_dir / f"look-{index}.png", index)

            settings = GoldenSettings(
                gemini_api_key="test",
                gemini_api_base_url="https://example.test",
                gemini_model="fake-gemini",
                gemini_timeout_seconds=1,
                fashion_model_id="unused",
                text_model_id="unused",
                device="cpu",
                embedding_batch_size=3,
                max_multimodal_calls=10,
            )
            manifest = build_manifest(
                input_dir=input_dir,
                run_dir=run_dir,
                dataset_name="pilot",
                dataset_version="pilot-v2",
            )
            self.assertEqual(len(manifest), 6)

            ids, vectors, _ = embed_manifest_images(
                run_dir=run_dir,
                settings=settings,
                backend_name="deterministic",
            )
            self.assertEqual(len(ids), 6)
            self.assertEqual(vectors.shape, (6, 32))
            clusters = cluster_embeddings(run_dir=run_dir, cluster_count=2)
            self.assertEqual(
                {row["cluster_id"] for row in clusters},
                {"cluster-000", "cluster-001"},
            )

            analysis_client = FakeAnalysisClient()
            analyze_run(
                run_dir=run_dir,
                settings=settings,
                analyze_all=True,
                client=analysis_client,
            )
            self.assertEqual(analysis_client.calls, 6)
            analyze_run(
                run_dir=run_dir,
                settings=settings,
                analyze_all=True,
                client=analysis_client,
            )
            self.assertEqual(analysis_client.calls, 6)

            paths = create_review_templates(run_dir=run_dir, pair_count=8)
            observation_reviews = run_dir / "observation_reviews.csv"
            _complete_observation_reviews(paths.observation, observation_reviews)
            claim_reviews = run_dir / "claim_reviews.csv"
            _complete_claim_reviews(paths.claim, claim_reviews)
            pair_reviews = run_dir / "pairwise_reviews.csv"
            _complete_pairwise(paths.pairwise, pair_reviews)

            accepted, report = collect_accepted_claims(
                observation_reviews_csv=observation_reviews,
                claim_reviews_csv=claim_reviews,
                run_dir=run_dir,
            )
            self.assertEqual(sum(len(rows) for rows in accepted.values()), 6)
            self.assertEqual(report["pending_claims"], [])

            anchors = build_anchor_scores(
                pairwise_csv=pair_reviews,
                observation_reviews_csv=observation_reviews,
                run_dir=run_dir,
            )
            self.assertEqual(len(anchors), 6)
            self.assertEqual(
                {row["score_band"] for row in anchors}, {"high", "mid", "low"}
            )
            self.assertTrue(
                all(row["human_axis_scores_1_5"] for row in anchors)
            )

            principles = synthesize_principles(
                run_dir=run_dir,
                observation_reviews_csv=observation_reviews,
                claim_reviews_csv=claim_reviews,
                settings=settings,
                client=FakePrincipleClient(),
            )
            self.assertEqual(len(principles), 2)
            self.assertTrue(
                all(row["knowledge_role"] == "NEEDS_COUNTEREXAMPLE" for row in principles)
            )
            principle_reviews = run_dir / "principle_reviews.csv"
            _complete_principle_reviews(
                run_dir / "principle_reviews.template.csv",
                principle_reviews,
            )
            reviewed = apply_principle_reviews(
                run_dir=run_dir,
                principle_reviews_csv=principle_reviews,
            )
            self.assertTrue(all(row["status"] == "APPROVED" for row in reviewed))
            self.assertTrue(
                all(row["knowledge_role"] == "EXPLANATION_ONLY" for row in reviewed)
            )

            plan = index_run(
                run_dir=run_dir,
                settings=replace(settings, text_model_id="unused"),
                text_backend_name="deterministic",
                dry_run=True,
            )
            self.assertEqual(plan["principle_points"], 2)
            # 코디 포인트는 앵커 유무와 무관하게 만든다 (앵커는 얹는 선택 정보).
            self.assertEqual(plan["outfit_points"], 6)
            self.assertEqual(plan["outfits_with_anchor"], 6)
            # 아이템 추출을 돌리지 않은 run이므로 아이템 포인트는 없다.
            self.assertEqual(plan["item_points"], 0)

    def test_one_reviewer_is_not_enough_to_accept_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            (run_dir / "analyses.jsonl").write_text("", encoding="utf-8")
            observation = run_dir / "observation.csv"
            claim = run_dir / "claim.csv"
            _write_rows(
                observation,
                [
                    {
                        "reviewer_label": "reviewer-a",
                        "golden_id": "g1",
                        "image_assessable": "YES",
                        "observation_verdict": "APPROVE",
                    }
                ],
            )
            _write_rows(
                claim,
                [
                    {
                        "reviewer_label": "reviewer-a",
                        "golden_id": "g1",
                        "claim_id": "c1",
                        "evidence_correct": "YES",
                        "human_judgment": "CONTRIBUTES",
                        "verdict": "APPROVE",
                    }
                ],
            )
            accepted, report = collect_accepted_claims(
                observation_reviews_csv=observation,
                claim_reviews_csv=claim,
                run_dir=run_dir,
            )
            self.assertEqual(accepted, {})
            self.assertEqual(report["accepted_image_count"], 0)

    def test_failed_calls_still_respect_multimodal_attempt_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "images"
            run_dir = root / "run-pilot"
            input_dir.mkdir()
            for index in range(4):
                _make_pattern_image(input_dir / f"look-{index}.png", index)
            settings = GoldenSettings(
                gemini_api_key="test",
                gemini_api_base_url="https://example.test",
                gemini_model="fake-gemini",
                gemini_timeout_seconds=1,
                fashion_model_id="unused",
                text_model_id="unused",
                device="cpu",
                embedding_batch_size=2,
                max_multimodal_calls=2,
            )
            build_manifest(
                input_dir=input_dir,
                run_dir=run_dir,
                dataset_name="pilot",
                dataset_version="attempt-limit-v2",
            )
            embed_manifest_images(
                run_dir=run_dir,
                settings=settings,
                backend_name="deterministic",
            )
            cluster_embeddings(run_dir=run_dir, cluster_count=2)
            client = FailingAnalysisClient()
            results = analyze_run(
                run_dir=run_dir,
                settings=settings,
                analyze_all=True,
                client=client,
            )
            self.assertEqual(client.calls, 2)
            self.assertEqual(len(results), 4)
            manifest = json.loads(
                (run_dir / "run_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["multimodal_call_attempts_last_run"], 2)
            self.assertEqual(manifest["successful_multimodal_calls_last_run"], 0)

    def test_risky_claim_is_excluded_even_with_two_approvals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            (run_dir / "analyses.jsonl").write_text("", encoding="utf-8")
            observation = run_dir / "observation.csv"
            claim = run_dir / "claim.csv"
            _write_rows(
                observation,
                [
                    {
                        "reviewer_label": reviewer,
                        "golden_id": "g1",
                        "image_assessable": "YES",
                        "items_complete": "YES",
                        "bbox_grounding_1_3": "3",
                        "unassessable_complete": "YES",
                        "observation_verdict": "APPROVE",
                    }
                    for reviewer in ("reviewer-a", "reviewer-b")
                ],
            )
            _write_rows(
                claim,
                [
                    {
                        "reviewer_label": reviewer,
                        "golden_id": "g1",
                        "claim_id": "c1",
                        "evidence_correct": "YES",
                        "human_judgment": "CONTRIBUTES",
                        "overgeneralization_risk": "YES",
                        "stereotype_risk": "NO",
                        "verdict": "APPROVE",
                    }
                    for reviewer in ("reviewer-a", "reviewer-b")
                ],
            )
            accepted, report = collect_accepted_claims(
                observation_reviews_csv=observation,
                claim_reviews_csv=claim,
                run_dir=run_dir,
            )
            self.assertEqual(accepted, {})
            self.assertEqual(report["excluded_claims"], ["g1:c1"])


def _make_pattern_image(path: Path, seed: int) -> None:
    image = Image.new("RGB", (48, 64), (20 + seed * 20, 40, 120))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (3 + seed, 5, 20 + seed * 2, 30 + seed),
        fill=(200, 30 + seed * 10, 50),
    )
    draw.line((0, seed * 5 + 3, 47, 63 - seed * 4), fill="white", width=2)
    image.save(path)


def _complete_observation_reviews(template: Path, output: Path) -> None:
    rows, fields = _read_template(template)
    completed = []
    for row in rows:
        for reviewer in ("reviewer-a", "reviewer-b"):
            reviewed = dict(row)
            reviewed.update(
                {
                    "reviewer_label": reviewer,
                    "image_assessable": "YES",
                    "items_complete": "YES",
                    "bbox_grounding_1_3": "3",
                    "unassessable_complete": "YES",
                    "q_color_1_5": "4",
                    "q_silhouette_proportion_1_5": "4",
                    "q_material_pattern_1_5": "4",
                    "q_style_cohesion_1_5": "4",
                    "q_completeness_detail_1_5": "4",
                    "observation_verdict": "APPROVE",
                    "human_confidence_1_3": "3",
                }
            )
            completed.append(reviewed)
    _write_rows(output, completed, fields)


def _complete_claim_reviews(template: Path, output: Path) -> None:
    rows, fields = _read_template(template)
    completed = []
    for row in rows:
        for reviewer in ("reviewer-a", "reviewer-b"):
            reviewed = dict(row)
            reviewed.update(
                {
                    "reviewer_label": reviewer,
                    "evidence_correct": "YES",
                    "human_judgment": "CONTEXT_DEPENDENT",
                    "verdict": "APPROVE",
                    "human_confidence_1_3": "3",
                    "overgeneralization_risk": "NO",
                    "stereotype_risk": "NO",
                }
            )
            completed.append(reviewed)
    _write_rows(output, completed, fields)


def _complete_pairwise(template: Path, output: Path) -> None:
    rows, fields = _read_template(template)
    completed = []
    for index, row in enumerate(rows):
        for reviewer in ("reviewer-a", "reviewer-b"):
            reviewed = dict(row)
            reviewed.update(
                {
                    "reviewer_label": reviewer,
                    "winner": "left" if index % 2 == 0 else "right",
                    "confidence_1_3": "2",
                    "reason_axis": "MIXED",
                }
            )
            completed.append(reviewed)
    _write_rows(output, completed, fields)


def _complete_principle_reviews(template: Path, output: Path) -> None:
    rows, fields = _read_template(template)
    completed = []
    for row in rows:
        for reviewer in ("reviewer-a", "reviewer-b"):
            reviewed = dict(row)
            reviewed.update(
                {
                    "reviewer_label": reviewer,
                    "verdict": "APPROVE",
                    "knowledge_role": "EXPLANATION_ONLY",
                    "human_confidence_1_3": "3",
                }
            )
            completed.append(reviewed)
    _write_rows(output, completed, fields)


def _read_template(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _write_rows(
    path: Path,
    rows: list[dict[str, str]],
    fields: list[str] | None = None,
) -> None:
    fieldnames = fields or sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()


class _StubEnum:
    """image-processor의 EnumeratedItem 자리를 대신하는 최소 스텁."""

    def __init__(self, index: int) -> None:
        self.descriptor_en = f"the test garment {index}"
        self.label_ko = f"테스트 아이템 {index}"
        self.category_large = "상의"
        self.occluded_by = []
        self.view_angle = "front"
        self.bbox = [10, 20, 900, 800]


class _StubProcessed:
    def __init__(self, index: int, *, failed: bool = False) -> None:
        self.index = index
        self.enum = _StubEnum(index)
        self.image_png = None if failed else b"\x89PNG-fake"
        self.tags = (
            None
            if failed
            else {
                "item_name": f"테스트 상의 {index}",
                "category_large": "상의",
                "category_small": "티셔츠",
                "season": ["봄", "가을"],
                "style": ["미니멀"],
                "usage": ["데일리"],
                "color": "화이트",
                "pattern": "무지",
                "fit": "레귤러핏",
                "material": "코튼",
                "sleeve": "반팔",
                "length": "기본",
                "layer_role": "기본 상의",
                "layer_order": 1,
                "_missing_required": [],
            }
        )
        self.image_vector = [] if failed else [0.1] * 4
        self.text_vector = [] if failed else [0.2] * 5
        self.error = "boom" if failed else None


class _StubEmbedder:
    version = "stub-embed-v1"


class _StubPipeline:
    """WardrobePipeline 계약(process/key/embedder)만 흉내낸다."""

    key = "stub-crop"
    embedder = _StubEmbedder()

    def __init__(self, per_image: int = 2) -> None:
        self.per_image = per_image
        self.calls = 0

    def process(self, image_bytes: bytes, mime: str) -> list:
        self.calls += 1
        # 마지막 아이템 하나는 실패로 만들어 부분 실패 경로도 태운다.
        return [_StubProcessed(i) for i in range(self.per_image)] + [
            _StubProcessed(self.per_image, failed=True)
        ]


class _FakeS3:
    """items.py가 쓰는 s3io 함수만 메모리 dict로 대체한다."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def install(self, monkey_target) -> None:
        monkey_target.get_json = self.get_json
        monkey_target.put_json = self.put_json
        monkey_target.put_bytes = self.put_bytes
        monkey_target.get_bytes = self.get_bytes

    def put_bytes(self, bucket, key, data, content_type):  # noqa: ARG002
        self.objects[(bucket, key)] = data
        return key

    def get_bytes(self, bucket, key):
        return self.objects[(bucket, key)]

    def put_json(self, bucket, key, value):
        self.objects[(bucket, key)] = json.dumps(value, ensure_ascii=False).encode()
        return key

    def get_json(self, bucket, key):
        raw = self.objects.get((bucket, key))
        return None if raw is None else json.loads(raw)


class GoldenItemPipelineTests(unittest.TestCase):
    def _prepare_run(self, root: Path) -> tuple[Path, GoldenSettings]:
        input_dir = root / "images"
        run_dir = root / "run-items"
        input_dir.mkdir()
        for index in range(2):
            _make_pattern_image(input_dir / f"look-{index}.png", index)
        settings = GoldenSettings(
            gemini_api_key="test",
            gemini_api_base_url="https://example.test",
            gemini_model="fake-gemini",
            gemini_timeout_seconds=1,
            fashion_model_id="unused",
            text_model_id="unused",
            device="cpu",
            embedding_batch_size=2,
            max_multimodal_calls=10,
            s3_bucket="test-bucket",
            dataset_version="items-v1",
        )
        build_manifest(
            input_dir=input_dir,
            run_dir=run_dir,
            dataset_name="pilot",
            dataset_version="items-v1",
        )
        embed_manifest_images(
            run_dir=run_dir, settings=settings, backend_name="deterministic"
        )
        cluster_embeddings(run_dir=run_dir, cluster_count=2)
        return run_dir, settings

    def test_items_are_extracted_reused_and_indexed(self) -> None:
        from ml.golden_set import items as items_module
        from ml.golden_set import s3io as s3io_module

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_dir, settings = self._prepare_run(root)

            fake = _FakeS3()
            original = (
                s3io_module.get_json,
                s3io_module.put_json,
                s3io_module.put_bytes,
                s3io_module.get_bytes,
            )
            fake.install(s3io_module)
            try:
                pipeline = _StubPipeline(per_image=2)
                rows = items_module.extract_items(
                    run_dir=run_dir, settings=settings, pipeline=pipeline
                )
                # 코디 2장 × (성공 2 + 실패 1)
                self.assertEqual(pipeline.calls, 2)
                self.assertEqual(len(rows), 6)
                self.assertEqual(
                    sum(1 for row in rows if row["status"] == "SUCCEEDED"), 4
                )
                self.assertEqual(rows[0]["layer_role"], "기본 상의")
                self.assertEqual(rows[0]["item_key"], f"{rows[0]['golden_id']}#000")

                keys, image_vectors, text_vectors = items_module.load_item_vectors(
                    run_dir / "item_embeddings.npz"
                )
                self.assertEqual(len(keys), 4)
                self.assertEqual(image_vectors.shape, (4, 4))
                self.assertEqual(text_vectors.shape, (4, 5))

                # 두 번째 호출은 S3 완료 manifest를 재사용해 파이프라인을 타지 않는다.
                again = items_module.extract_items(
                    run_dir=run_dir, settings=settings, pipeline=pipeline
                )
                self.assertEqual(pipeline.calls, 2)
                self.assertEqual(len(again), 6)
                meta = json.loads(
                    (run_dir / "items.meta.json").read_text(encoding="utf-8")
                )
                self.assertEqual(meta["reused_images"], 2)
                self.assertEqual(meta["processed_images"], 0)

                plan = index_run(
                    run_dir=run_dir,
                    settings=settings,
                    text_backend_name="deterministic",
                    dry_run=True,
                )
                self.assertEqual(plan["outfit_points"], 2)
                # 실패 아이템과 벡터 없는 아이템은 적재 대상에서 빠진다.
                self.assertEqual(plan["item_points"], 4)
                self.assertEqual(plan["items_without_vector"], 2)
                self.assertEqual(plan["outfits_with_anchor"], 0)
                self.assertFalse(plan["exposable"])
            finally:
                (
                    s3io_module.get_json,
                    s3io_module.put_json,
                    s3io_module.put_bytes,
                    s3io_module.get_bytes,
                ) = original

    def test_point_ids_are_deterministic_and_share_django_namespace(self) -> None:
        from ml.golden_set.point_ids import POINT_NAMESPACE
        from ml.golden_set.qdrant_index import item_point_id, outfit_point_id

        # api/apps/recommend/services/qdrant.py 의 _POINT_NAMESPACE 와 같아야 한다.
        # 다르면 같은 키에 다른 UUID가 나와 중복 upsert·삭제 무효화가 조용히 생긴다.
        self.assertEqual(
            str(POINT_NAMESPACE), "6b2c1f3a-9d4e-4c8b-8a71-2f0e5d9c3b17"
        )
        self.assertEqual(outfit_point_id("v1", "g1"), outfit_point_id("v1", "g1"))
        self.assertNotEqual(outfit_point_id("v1", "g1"), outfit_point_id("v2", "g1"))
        self.assertNotEqual(outfit_point_id("v1", "g1"), item_point_id("v1", "g1"))
