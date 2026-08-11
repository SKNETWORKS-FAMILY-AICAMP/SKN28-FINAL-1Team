from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.recommend.services.item_retriever import ItemSource
from apps.recommend.services.outfit_types import (
    OutfitComposition,
    OutfitItem,
    OutfitSlot,
    RecommendationMode,
)
from apps.recommend.services.validator import (
    DjangoEligibilityGateway,
    OutfitValidator,
    SourceEligibility,
    ValidationContext,
    ValidationSeverity,
)


def _item(
    slot_id: str,
    source_type: ItemSource,
    source_id: str,
    *,
    category_large: str = "상의",
    image_ref: str = "items/item.jpg",
    price: int | None = None,
    payload: dict | None = None,
) -> OutfitItem:
    collections = {
        ItemSource.WARDROBE: "wardrobe_items",
        ItemSource.GOLDENSET_ITEM: "goldenset_items",
        ItemSource.PRODUCT: "products_naver_v1",
    }
    item_payload = {
        "category_large": category_large,
        "image_s3_key": image_ref,
    }
    item_payload.update(payload or {})
    if price is not None:
        item_payload["price"] = price
    return OutfitItem(
        slot_id=slot_id,
        template_point_id=f"template-{slot_id}",
        category_large=category_large,
        layer_role=str(item_payload.get("layer_role") or ""),
        source_type=source_type,
        source_id=source_id,
        source_collection=collections[source_type],
        point_id=f"point-{source_id}",
        image_ref=image_ref,
        price=price,
        score=0.8,
        reasons=("후보 선택",),
        payload=item_payload,
    )


def _composition(
    *items: OutfitItem,
    missing: tuple[str, ...] = (),
    total_price: int | None = None,
    slots: tuple[OutfitSlot, ...] = (),
) -> OutfitComposition:
    if total_price is None:
        total_price = sum(
            item.price or 0 for item in items if item.source_type is ItemSource.PRODUCT
        )
    return OutfitComposition(
        mode=RecommendationMode.WARDROBE_BASED,
        items=tuple(items),
        missing_slot_ids=missing,
        total_product_price=total_price,
        slots=slots,
    )


class FakeEligibilityGateway:
    def __init__(self, statuses=None) -> None:
        self.statuses = statuses or {}
        self.user_ids: list[int | None] = []

    def check(self, items, *, user_id):
        self.user_ids.append(user_id)
        return {
            item.identity: self.statuses.get(
                item.identity,
                SourceEligibility(
                    eligible=True,
                    current_price=(
                        item.price if item.source_type is ItemSource.PRODUCT else None
                    ),
                ),
            )
            for item in items
        }


def _codes(result, severity: ValidationSeverity | None = None) -> set[str]:
    return {
        issue.code
        for issue in result.issues
        if severity is None or issue.severity is severity
    }


class OutfitValidatorTests(SimpleTestCase):
    def test_valid_composition_can_proceed_to_render(self) -> None:
        top = _item(
            "top",
            ItemSource.WARDROBE,
            "owned-top",
            payload={
                "season": ["간절기"],
                "usage": ["출근"],
                "layer_role": "기본 상의",
                "layer_order": 1,
            },
        )
        bottom = _item(
            "bottom",
            ItemSource.GOLDENSET_ITEM,
            "golden-bottom",
            category_large="하의",
            payload={"season": ["봄", "가을"], "usage": ["출근"]},
        )
        slots = (
            OutfitSlot("top", "template-top", "상의"),
            OutfitSlot("bottom", "template-bottom", "하의"),
        )
        gateway = FakeEligibilityGateway()

        result = OutfitValidator(eligibility_gateway=gateway).validate(
            _composition(top, bottom, slots=slots),
            context=ValidationContext(
                user_id=7,
                weather={"temperature": 18},
                occasion="출근",
            ),
        )

        self.assertTrue(result.valid)
        self.assertTrue(result.can_render)
        self.assertEqual(result.errors, ())
        self.assertEqual(gateway.user_ids, [7])

    def test_missing_slot_and_image_are_hard_errors(self) -> None:
        item = _item(
            "top",
            ItemSource.GOLDENSET_ITEM,
            "golden-top",
            image_ref="",
        )
        slots = (
            OutfitSlot("top", "template-top", "상의"),
            OutfitSlot("bottom", "template-bottom", "하의"),
        )

        result = OutfitValidator(eligibility_gateway=FakeEligibilityGateway()).validate(
            _composition(item, missing=("bottom",), slots=slots)
        )

        self.assertFalse(result.valid)
        self.assertEqual(
            {"REQUIRED_SLOT_MISSING", "ITEM_IMAGE_MISSING"},
            _codes(result, ValidationSeverity.ERROR),
        )

    def test_duplicate_item_category_and_layer_conflicts_are_rejected(self) -> None:
        duplicated_inner = _item(
            "top-inner",
            ItemSource.WARDROBE,
            "same",
            payload={"layer_role": "기본 상의", "layer_order": 2},
        )
        duplicated_outer = OutfitItem(
            **{
                **duplicated_inner.__dict__,
                "slot_id": "top-outer",
                "template_point_id": "template-top-outer",
                "layer_role": "아우터",
                "payload": {
                    **duplicated_inner.payload,
                    "layer_role": "아우터",
                    "layer_order": 1,
                },
            }
        )
        bottom_a = _item(
            "bottom-a",
            ItemSource.GOLDENSET_ITEM,
            "bottom-a",
            category_large="하의",
        )
        bottom_b = _item(
            "bottom-b",
            ItemSource.GOLDENSET_ITEM,
            "bottom-b",
            category_large="하의",
        )

        result = OutfitValidator(eligibility_gateway=FakeEligibilityGateway()).validate(
            _composition(duplicated_inner, duplicated_outer, bottom_a, bottom_b)
        )

        self.assertTrue(
            {
                "DUPLICATE_ITEM",
                "CATEGORY_CONFLICT",
                "LAYER_ORDER_CONFLICT",
            }.issubset(_codes(result, ValidationSeverity.ERROR))
        )

    def test_explicit_avoidance_is_error_but_context_mismatch_is_warning(self) -> None:
        item = _item(
            "top",
            ItemSource.GOLDENSET_ITEM,
            "golden-top",
            payload={
                "color": ["블랙"],
                "season": ["겨울"],
                "usage": ["데일리"],
                "material": ["울"],
            },
        )

        result = OutfitValidator(eligibility_gateway=FakeEligibilityGateway()).validate(
            _composition(item),
            context=ValidationContext(
                season="여름",
                occasion="출근",
                avoided_tags={"color": ("블랙",)},
                contextual_avoided_tags={"material": ("울",)},
            ),
        )

        self.assertIn("EXPLICIT_TAG_EXCLUDED", _codes(result, ValidationSeverity.ERROR))
        self.assertTrue(
            {"SEASON_MISMATCH", "OCCASION_MISMATCH", "CONTEXT_RULE_MISMATCH"}.issubset(
                _codes(result, ValidationSeverity.WARNING)
            )
        )

    def test_live_source_failure_is_returned_with_slot_context(self) -> None:
        item = _item("top", ItemSource.WARDROBE, "owned-top")
        gateway = FakeEligibilityGateway(
            {
                item.identity: SourceEligibility(
                    eligible=False,
                    code="WARDROBE_ITEM_FORBIDDEN",
                    message="다른 사용자의 아이템",
                )
            }
        )

        result = OutfitValidator(eligibility_gateway=gateway).validate(
            _composition(item),
            context=ValidationContext(user_id=7),
        )

        issue = next(
            issue for issue in result.errors if issue.code == "WARDROBE_ITEM_FORBIDDEN"
        )
        self.assertEqual(issue.slot_id, "top")
        self.assertEqual(issue.source_id, "owned-top")

    def test_current_catalog_price_is_used_for_total_budget(self) -> None:
        item = _item(
            "top",
            ItemSource.PRODUCT,
            "naver-1",
            price=40_000,
            payload={"source": "naver"},
        )
        gateway = FakeEligibilityGateway(
            {
                item.identity: SourceEligibility(
                    eligible=True,
                    current_price=55_000,
                )
            }
        )

        result = OutfitValidator(eligibility_gateway=gateway).validate(
            _composition(item),
            context=ValidationContext(total_budget=50_000),
        )

        self.assertEqual(result.effective_total_product_price, 55_000)
        self.assertIn("TOTAL_BUDGET_EXCEEDED", _codes(result, ValidationSeverity.ERROR))
        self.assertTrue(
            {"PRODUCT_PRICE_CHANGED", "COMPOSITION_PRICE_STALE"}.issubset(
                _codes(result, ValidationSeverity.WARNING)
            )
        )


class DjangoEligibilityGatewayRuleTests(SimpleTestCase):
    def test_naver_discontinued_product_is_not_eligible(self) -> None:
        product = SimpleNamespace(product_type=3)

        status = DjangoEligibilityGateway._naver_status(product)

        self.assertFalse(status.eligible)
        self.assertEqual(status.code, "PRODUCT_NOT_ON_SALE")

    def test_catalog_product_requires_tag_link_and_price(self) -> None:
        status = DjangoEligibilityGateway._catalog_status(
            tagging_status="tagged",
            link=None,
            price=10_000,
        )

        self.assertFalse(status.eligible)
        self.assertEqual(status.code, "PRODUCT_LINK_MISSING")
