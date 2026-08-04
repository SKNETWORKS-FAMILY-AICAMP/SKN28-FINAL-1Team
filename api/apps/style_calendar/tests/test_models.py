from django.db import models
from django.test import SimpleTestCase

from apps.style_calendar.models import (
    CalendarEntry,
    CalendarItem,
    CalendarWardrobeItem,
)


class CalendarModelMetadataTests(SimpleTestCase):
    def test_explicit_table_names_and_comments(self) -> None:
        self.assertEqual(CalendarEntry._meta.db_table, "calendar_entry")
        self.assertEqual(CalendarItem._meta.db_table, "calendar_item")
        self.assertEqual(
            CalendarWardrobeItem._meta.db_table,
            "calendar_wardrobe_item",
        )
        self.assertTrue(CalendarEntry._meta.db_table_comment)
        self.assertTrue(CalendarItem._meta.db_table_comment)
        self.assertTrue(CalendarWardrobeItem._meta.db_table_comment)

    def test_every_database_field_has_comment(self) -> None:
        for model in (CalendarEntry, CalendarItem, CalendarWardrobeItem):
            for field in model._meta.local_fields:
                with self.subTest(model=model.__name__, field=field.name):
                    self.assertTrue(field.db_comment)

    def test_calendar_and_wardrobe_item_have_explicit_many_to_many_relation(
        self,
    ) -> None:
        field = CalendarEntry._meta.get_field("wardrobe_items")

        self.assertTrue(field.many_to_many)
        self.assertIs(field.remote_field.through, CalendarWardrobeItem)

    def test_calendar_wardrobe_link_requires_both_sides(self) -> None:
        calendar_field = CalendarWardrobeItem._meta.get_field("calendar")
        wardrobe_field = CalendarWardrobeItem._meta.get_field("wardrobe_item")

        self.assertFalse(calendar_field.null)
        self.assertFalse(wardrobe_field.null)
        self.assertIs(calendar_field.remote_field.on_delete, models.CASCADE)
        self.assertIs(wardrobe_field.remote_field.on_delete, models.CASCADE)

    def test_processor_item_has_no_wardrobe_relation(self) -> None:
        field_names = {field.name for field in CalendarItem._meta.local_fields}

        self.assertNotIn("wardrobe_item", field_names)
        self.assertNotIn("source_type", field_names)

    def test_calendar_schema_has_no_embedding_or_matching_fields(self) -> None:
        field_names = {
            field.name
            for model in (CalendarEntry, CalendarItem, CalendarWardrobeItem)
            for field in model._meta.local_fields
        }

        self.assertFalse(
            field_names
            & {
                "embedding",
                "image_embedding",
                "text_embedding",
                "match_score",
                "matched",
                "unmatched",
            }
        )

    def test_expected_database_constraints_are_declared(self) -> None:
        entry_constraints = {
            constraint.name for constraint in CalendarEntry._meta.constraints
        }
        item_constraints = {
            constraint.name for constraint in CalendarItem._meta.constraints
        }
        link_constraints = {
            constraint.name
            for constraint in CalendarWardrobeItem._meta.constraints
        }

        self.assertEqual(entry_constraints, {"uq_calendar_user_date"})
        self.assertEqual(
            item_constraints,
            {"uq_cal_item_processor"},
        )
        self.assertEqual(link_constraints, {"uq_cal_wardrobe_link"})
