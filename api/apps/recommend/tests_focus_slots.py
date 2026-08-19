from django.test import SimpleTestCase

from apps.recommend.services.focus_slots import (
    focus_slot_from_snapshot,
    focus_slot_labels,
    normalize_focus_slots,
)


class FocusSlotTests(SimpleTestCase):
    def test_aliases_are_normalized_in_fixed_display_order(self):
        self.assertEqual(
            normalize_focus_slots(["신발", "아우터", "상의", "재킷"]),
            ("TOP", "OUTER", "SHOES"),
        )

    def test_snapshot_normalizes_category_and_layer_values(self):
        self.assertEqual(
            focus_slot_from_snapshot(slot="", category_large="상의"),
            "TOP",
        )
        self.assertEqual(
            focus_slot_from_snapshot(
                slot="",
                category_large="",
                layer_role="outer",
            ),
            "OUTER",
        )

    def test_labels_are_user_facing_korean(self):
        self.assertEqual(focus_slot_labels(["TOP", "OUTER"]), ("상의", "아우터"))
