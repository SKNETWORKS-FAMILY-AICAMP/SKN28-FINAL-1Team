from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.recommend.models import (
    GoldenTemplateSnapshot,
    OutfitComposition,
    OutfitCompositionItem,
    RecommendationResult,
)


class RecommendationModelTests(TestCase):
    def _result(
        self,
        *,
        mode: str = RecommendationResult.Mode.NEW_ITEM,
        run_id: uuid.UUID | None = None,
    ) -> RecommendationResult:
        return RecommendationResult.objects.create(
            identity_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            run_id=run_id or uuid.uuid4(),
            mode=mode,
            dataset_version="goldenset-2026-08-01",
        )

    def _composition(
        self,
        result: RecommendationResult,
        *,
        rank: int = 1,
    ) -> OutfitComposition:
        return OutfitComposition.objects.create(
            result=result,
            rank=rank,
            status=OutfitComposition.Status.VALIDATED,
            composition_fingerprint="a" * 64,
            total_product_price=59_000,
            validation_reasons=[{"code": "VALID", "message": "검증 통과"}],
            warnings=[],
        )

    def _item(
        self,
        composition: OutfitComposition,
        *,
        position: int,
        slot: str,
        source_type: str,
        source_id: str,
        source_collection: str,
        price_snapshot: int | None = None,
    ) -> OutfitCompositionItem:
        return OutfitCompositionItem.objects.create(
            composition=composition,
            position=position,
            slot=slot,
            source_type=source_type,
            source_id=source_id,
            source_collection=source_collection,
            source_point_id=f"point-{source_id}",
            template_item_point_id=f"template-{slot}",
            replacement_score=0.91,
            image_ref=f"images/{source_id}.jpg",
            price_snapshot=price_snapshot,
            reasons=["골든 템플릿 슬롯과 카테고리·레이어가 일치함"],
            item_snapshot={"name": source_id, "slot": slot},
        )

    def test_full_recommendation_graph_preserves_template_and_item_snapshots(self):
        result = self._result()
        template = GoldenTemplateSnapshot.objects.create(
            result=result,
            golden_id="golden-outfit-17",
            point_id="outfit-point-17",
            retrieval_score=0.94,
            payload_snapshot={"style": ["미니멀"], "season": ["가을"]},
            reasons=[{"source": "preference", "delta": 8.0}],
        )
        composition = self._composition(result)
        wardrobe_item = self._item(
            composition,
            position=1,
            slot="TOP",
            source_type=OutfitCompositionItem.SourceType.WARDROBE,
            source_id="wardrobe-101",
            source_collection="wardrobe_items",
        )
        product_item = self._item(
            composition,
            position=2,
            slot="BOTTOM",
            source_type=OutfitCompositionItem.SourceType.PRODUCT,
            source_id="naver-202",
            source_collection="naver_products",
            price_snapshot=59_000,
        )

        result.refresh_from_db()
        self.assertEqual(result.golden_template, template)
        self.assertEqual(list(result.compositions.all()), [composition])
        self.assertEqual(
            list(composition.items.all()),
            [wardrobe_item, product_item],
        )
        self.assertEqual(product_item.price_snapshot, 59_000)
        self.assertEqual(template.payload_snapshot["style"], ["미니멀"])

    def test_recommendation_mode_matches_two_confirmed_product_modes(self):
        self.assertEqual(
            set(RecommendationResult.Mode.values),
            {"WARDROBE_BASED", "NEW_ITEM"},
        )

    def test_goldenset_item_cannot_be_saved_as_final_composition_item(self):
        composition = self._composition(self._result())
        item = OutfitCompositionItem(
            composition=composition,
            position=1,
            slot="TOP",
            source_type="GOLDENSET_ITEM",
            source_id="golden-item-1",
            source_collection="goldenset_items",
            source_point_id="golden-point-1",
            template_item_point_id="golden-point-1",
            image_ref="goldenset/item-1.jpg",
        )

        with self.assertRaises(ValidationError):
            item.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            item.save(force_insert=True)

    def test_one_chat_run_cannot_create_duplicate_results(self):
        run_id = uuid.uuid4()
        self._result(run_id=run_id)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._result(run_id=run_id)

    def test_composition_rank_is_limited_to_one_through_three(self):
        result = self._result()

        with self.assertRaises(IntegrityError), transaction.atomic():
            OutfitComposition.objects.create(result=result, rank=4)

    def test_result_cannot_have_duplicate_composition_rank(self):
        result = self._result()
        self._composition(result, rank=1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            OutfitComposition.objects.create(result=result, rank=1)

    def test_composition_rejects_duplicate_slot_and_source_item(self):
        composition = self._composition(self._result())
        self._item(
            composition,
            position=1,
            slot="TOP",
            source_type=OutfitCompositionItem.SourceType.WARDROBE,
            source_id="wardrobe-1",
            source_collection="wardrobe_items",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._item(
                composition,
                position=2,
                slot="TOP",
                source_type=OutfitCompositionItem.SourceType.WARDROBE,
                source_id="wardrobe-2",
                source_collection="wardrobe_items",
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._item(
                composition,
                position=2,
                slot="BOTTOM",
                source_type=OutfitCompositionItem.SourceType.WARDROBE,
                source_id="wardrobe-1",
                source_collection="wardrobe_items",
            )

    def test_deleting_result_cascades_to_template_compositions_and_items(self):
        result = self._result()
        GoldenTemplateSnapshot.objects.create(
            result=result,
            golden_id="golden-1",
            point_id="point-1",
            retrieval_score=0.9,
        )
        composition = self._composition(result)
        self._item(
            composition,
            position=1,
            slot="TOP",
            source_type=OutfitCompositionItem.SourceType.WARDROBE,
            source_id="wardrobe-1",
            source_collection="wardrobe_items",
        )

        result.delete()

        self.assertFalse(GoldenTemplateSnapshot.objects.exists())
        self.assertFalse(OutfitComposition.objects.exists())
        self.assertFalse(OutfitCompositionItem.objects.exists())
