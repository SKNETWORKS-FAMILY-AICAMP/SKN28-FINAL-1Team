from __future__ import annotations

from django.test import SimpleTestCase

from apps.recommend.services.composer import (
    CompositionError,
    CompositionRequest,
    OutfitComposer,
    RecommendationMode,
)
from apps.recommend.services.item_retriever import (
    ItemCandidate,
    ItemRetrievalResult,
    ItemSource,
    TemplateItem,
)
from apps.recommend.services.qdrant import GOLDEN_ITEM_COLLECTION


def _template(
    point_id: str,
    *,
    layer_role: str,
    image_ref: str = "",
) -> TemplateItem:
    payload = {
        "category_large": "상의" if layer_role == "TOP" else "하의",
        "layer_role": layer_role,
    }
    if image_ref:
        payload["image_s3_key"] = image_ref
    return TemplateItem(point_id=point_id, payload=payload)


def _candidate(
    source_type: ItemSource,
    source_id: str,
    *,
    score: float = 0.8,
    price: int | None = None,
    image_ref: str = "items/item.jpg",
) -> ItemCandidate:
    collections = {
        ItemSource.WARDROBE: "wardrobe_items",
        ItemSource.GOLDENSET_ITEM: GOLDEN_ITEM_COLLECTION,
        ItemSource.PRODUCT: "products_naver_v1",
    }
    payload = {"image_s3_key": image_ref} if image_ref else {}
    if price is not None:
        payload["price"] = price
    return ItemCandidate(
        point_id=f"point-{source_id}",
        source_type=source_type,
        source_id=source_id,
        source_collection=collections[source_type],
        score=score,
        reasons=(f"{source_type.value} 후보",),
        payload=payload,
    )


def _slot(
    template: TemplateItem,
    *candidates: ItemCandidate,
) -> ItemRetrievalResult:
    return ItemRetrievalResult(
        template=template,
        candidates=tuple(candidates),
        vector_name="image",
    )


class OutfitComposerTests(SimpleTestCase):
    def setUp(self) -> None:
        self.composer = OutfitComposer()

    def test_wardrobe_mode_prioritizes_owned_item_over_higher_similarity(self) -> None:
        slot = _slot(
            _template("golden-top", layer_role="TOP", image_ref="golden/top.jpg"),
            _candidate(ItemSource.WARDROBE, "owned-top", score=0.7),
            _candidate(ItemSource.PRODUCT, "product-top", score=0.99, price=50_000),
        )

        result = self.composer.compose(
            CompositionRequest(
                mode=RecommendationMode.WARDROBE_BASED,
                slot_results=(slot,),
            )
        )

        self.assertTrue(result.complete)
        self.assertEqual(result.items[0].source_id, "owned-top")
        self.assertEqual(result.owned_count, 1)
        self.assertEqual(result.total_product_price, 0)
        self.assertIn("보유 아이템 우선", result.items[0].reasons[0])

    def test_wardrobe_mode_does_not_fall_back_to_other_sources(self) -> None:
        slot = _slot(
            _template(
                "golden-bottom", layer_role="BOTTOM", image_ref="golden/bottom.jpg"
            ),
            _candidate(ItemSource.PRODUCT, "product-bottom", price=30_000),
        )

        result = self.composer.compose(
            CompositionRequest(
                mode=RecommendationMode.WARDROBE_BASED,
                slot_results=(slot,),
            )
        )

        self.assertFalse(result.complete)
        self.assertEqual(result.items, ())
        self.assertEqual(result.missing_slot_ids, ("BOTTOM:golden-bottom",))

    def test_new_item_mode_includes_product_with_owned_items(self) -> None:
        top = _slot(
            _template("golden-top", layer_role="TOP", image_ref="golden/top.jpg"),
            _candidate(ItemSource.WARDROBE, "owned-top", score=0.99),
            _candidate(ItemSource.PRODUCT, "product-top", score=0.7, price=40_000),
        )
        bottom = _slot(
            _template(
                "golden-bottom",
                layer_role="BOTTOM",
                image_ref="golden/bottom.jpg",
            ),
            _candidate(ItemSource.WARDROBE, "owned-bottom", score=0.6),
        )

        result = self.composer.compose(
            CompositionRequest(
                mode=RecommendationMode.NEW_ITEM,
                slot_results=(top, bottom),
            )
        )

        self.assertEqual(
            [item.source_id for item in result.items],
            ["product-top", "owned-bottom"],
        )
        self.assertEqual(result.purchasable_count, 1)
        self.assertEqual(result.owned_count, 1)
        self.assertEqual(result.total_product_price, 40_000)

    def test_total_budget_is_applied_across_all_slots(self) -> None:
        top = _slot(
            _template("golden-top", layer_role="TOP", image_ref="golden/top.jpg"),
            _candidate(ItemSource.PRODUCT, "product-top", price=70_000),
        )
        bottom = _slot(
            _template(
                "golden-bottom",
                layer_role="BOTTOM",
                image_ref="golden/bottom.jpg",
            ),
            _candidate(ItemSource.PRODUCT, "product-bottom", price=40_000),
            _candidate(ItemSource.WARDROBE, "owned-bottom"),
        )

        result = self.composer.compose(
            CompositionRequest(
                mode=RecommendationMode.NEW_ITEM,
                slot_results=(top, bottom),
                total_budget=100_000,
            )
        )

        self.assertEqual(
            [item.source_id for item in result.items],
            ["product-top", "owned-bottom"],
        )
        self.assertEqual(result.total_product_price, 70_000)

    def test_same_candidate_is_not_selected_for_two_slots(self) -> None:
        duplicated = _candidate(ItemSource.WARDROBE, "same-item")
        top = _slot(
            _template("golden-top", layer_role="TOP", image_ref="golden/top.jpg"),
            duplicated,
        )
        bottom = _slot(
            _template(
                "golden-bottom",
                layer_role="BOTTOM",
                image_ref="golden/bottom.jpg",
            ),
            duplicated,
        )

        result = self.composer.compose(
            CompositionRequest(
                mode=RecommendationMode.WARDROBE_BASED,
                slot_results=(top, bottom),
            )
        )

        source_ids = [item.source_id for item in result.items]
        self.assertEqual(source_ids.count("same-item"), 1)
        self.assertEqual(len(result.missing_slot_ids), 1)

    def test_slot_without_image_eligible_candidate_is_reported_missing(self) -> None:
        slot = _slot(
            _template("golden-top", layer_role="TOP"),
            _candidate(ItemSource.WARDROBE, "owned-top", image_ref=""),
        )

        result = self.composer.compose(
            CompositionRequest(
                mode=RecommendationMode.WARDROBE_BASED,
                slot_results=(slot,),
            )
        )

        self.assertFalse(result.complete)
        self.assertEqual(result.items, ())
        self.assertEqual(result.missing_slot_ids, ("TOP:golden-top",))
        self.assertTrue(result.warnings)

    def test_duplicate_template_slot_is_rejected(self) -> None:
        template = _template(
            "golden-top",
            layer_role="TOP",
            image_ref="golden/top.jpg",
        )
        slot = _slot(template)

        with self.assertRaises(CompositionError):
            self.composer.compose(
                CompositionRequest(
                    mode=RecommendationMode.WARDROBE_BASED,
                    slot_results=(slot, slot),
                )
            )
