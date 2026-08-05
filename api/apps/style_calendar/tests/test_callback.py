from __future__ import annotations

from copy import deepcopy
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.style_calendar.contracts import (
    CALENDAR_CALLBACK_SCHEMA_VERSION,
    CalendarCallbackStatus,
    CalendarSourceType,
    CalendarStatus,
)
from apps.style_calendar.models import CalendarEntry, CalendarItem
from apps.style_calendar.serializers import CalendarCallbackSerializer
from apps.style_calendar.services import callback as calendar_callback
from apps.users.models import User


class CalendarCallbackApiTests(TestCase):
    token = "calendar-callback-secret"

    def setUp(self) -> None:
        token_patcher = patch.dict(
            "os.environ",
            {"WARDROBE_INTERNAL_TOKEN": self.token},
        )
        token_patcher.start()
        self.addCleanup(token_patcher.stop)

        self.user = User.objects.create(username="callback-user")
        self.entry = CalendarEntry.objects.create(
            user=self.user,
            date=date(2026, 8, 4),
            source_type=CalendarSourceType.PHOTO_UPLOAD.value,
            image_s3_key=f"calendar/{self.user.pk}/source/original.jpg",
            status=CalendarStatus.REGISTERED.value,
        )
        self.url = reverse(
            "style_calendar:calendar-callback",
            kwargs={"calendar_id": self.entry.pk},
        )
        self.client = APIClient()
        self.client.credentials(HTTP_X_INTERNAL_TOKEN=self.token)

    def processing_payload(self) -> dict:
        return {
            "schema_version": CALENDAR_CALLBACK_SCHEMA_VERSION,
            "calendar_id": str(self.entry.pk),
            "status": CalendarCallbackStatus.PROCESSING.value,
        }

    def completed_payload(self) -> dict:
        prefix = f"calendar/{self.user.pk}/{self.entry.pk}/"
        return {
            "schema_version": CALENDAR_CALLBACK_SCHEMA_VERSION,
            "calendar_id": str(self.entry.pk),
            "status": CalendarCallbackStatus.COMPLETED.value,
            "manifest_s3_key": f"{prefix}manifest.json",
            "completed_at": "2026-08-04T04:05:06Z",
            "items": [
                {
                    "processor_item_id": f"{self.entry.pk}:000",
                    "status": "extracted",
                    "image_s3_key": f"{prefix}item_000.png",
                    "category": "자켓",
                    "tags": {"category_large": "아우터"},
                    "bbox": [100, 200, 800, 700],
                    "sort_order": 0,
                    "error": "",
                },
                {
                    "processor_item_id": f"{self.entry.pk}:001",
                    "status": "failed",
                    "image_s3_key": "",
                    "category": "하의",
                    "tags": {},
                    "bbox": None,
                    "sort_order": 1,
                    "error": "RuntimeError: generation failed",
                },
            ],
        }

    def test_callback_requires_valid_internal_token(self) -> None:
        without_token = APIClient().post(
            self.url,
            self.processing_payload(),
            format="json",
        )
        wrong_token_client = APIClient()
        wrong_token_client.credentials(HTTP_X_INTERNAL_TOKEN="wrong")
        wrong_token = wrong_token_client.post(
            self.url,
            self.processing_payload(),
            format="json",
        )

        self.assertEqual(without_token.status_code, 403)
        self.assertEqual(wrong_token.status_code, 403)

    def test_processing_callback_updates_status_once(self) -> None:
        first = self.client.post(self.url, self.processing_payload(), format="json")
        second = self.client.post(self.url, self.processing_payload(), format="json")

        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.data["duplicate"])
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["duplicate"])
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, CalendarStatus.PROCESSING.value)
        self.assertIsNotNone(self.entry.processing_started_at)

    def test_completed_callback_creates_items_atomically(self) -> None:
        response = self.client.post(
            self.url,
            self.completed_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["num_items"], 2)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, CalendarStatus.COMPLETED.value)
        self.assertEqual(
            self.entry.manifest_s3_key,
            f"calendar/{self.user.pk}/{self.entry.pk}/manifest.json",
        )
        self.assertIsNotNone(self.entry.processing_started_at)
        self.assertIsNotNone(self.entry.processing_completed_at)
        self.assertIsNotNone(self.entry.callback_applied_at)
        items = list(self.entry.items.order_by("sort_order"))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].internal_status, "EXTRACTED")
        self.assertEqual(items[0].category, "자켓")
        self.assertEqual(items[1].internal_status, "FAILED")
        self.assertIn("generation failed", items[1].processing_error)

    def test_final_callback_is_idempotent_by_calendar_id(self) -> None:
        first = self.client.post(
            self.url,
            self.completed_payload(),
            format="json",
        )
        second_payload = self.completed_payload()
        second_payload["items"] = [second_payload["items"][0]]
        second = self.client.post(self.url, second_payload, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["duplicate"])
        self.assertEqual(self.entry.items.count(), 2)

    def test_failed_callback_records_failed_items_and_error(self) -> None:
        prefix = f"calendar/{self.user.pk}/{self.entry.pk}/"
        payload = {
            "schema_version": CALENDAR_CALLBACK_SCHEMA_VERSION,
            "calendar_id": str(self.entry.pk),
            "status": CalendarCallbackStatus.FAILED.value,
            "manifest_s3_key": f"{prefix}manifest.json",
            "completed_at": "2026-08-04T04:05:06Z",
            "error_code": "NO_ITEM_EXTRACTED",
            "error_message": "처리 성공한 아이템이 없습니다.",
            "items": [
                {
                    "processor_item_id": f"{self.entry.pk}:000",
                    "status": "failed",
                    "image_s3_key": "",
                    "category": "상의",
                    "tags": {},
                    "bbox": None,
                    "sort_order": 0,
                    "error": "tagging failed",
                }
            ],
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, CalendarStatus.FAILED.value)
        self.assertEqual(self.entry.processing_error_code, "NO_ITEM_EXTRACTED")
        self.assertEqual(self.entry.items.get().internal_status, "FAILED")

    def test_failed_callback_without_code_uses_generic_failure_code(self) -> None:
        payload = {
            "schema_version": CALENDAR_CALLBACK_SCHEMA_VERSION,
            "calendar_id": str(self.entry.pk),
            "status": CalendarCallbackStatus.FAILED.value,
            "completed_at": "2026-08-04T04:05:06Z",
            "error_message": "provider unavailable",
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(
            self.entry.processing_error_code,
            "IMAGE_PROCESSING_FAILED",
        )

    def test_rejects_url_body_id_mismatch_and_unknown_schema(self) -> None:
        mismatch = self.processing_payload()
        mismatch["calendar_id"] = str(uuid4())
        mismatch_response = self.client.post(self.url, mismatch, format="json")
        invalid_schema = self.processing_payload()
        invalid_schema["schema_version"] = "calendar-callback.v2"
        schema_response = self.client.post(self.url, invalid_schema, format="json")

        self.assertEqual(mismatch_response.status_code, 400)
        self.assertEqual(schema_response.status_code, 400)

    def test_rejects_result_key_outside_calendar_prefix(self) -> None:
        payload = self.completed_payload()
        payload["items"][0]["image_s3_key"] = "calendar/other/result.png"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, CalendarStatus.REGISTERED.value)
        self.assertEqual(self.entry.items.count(), 0)

    def test_rejects_callback_for_direct_wardrobe_calendar(self) -> None:
        direct_entry = CalendarEntry.objects.create(
            user=self.user,
            date=date(2026, 8, 5),
            source_type=CalendarSourceType.WARDROBE_SELECTED.value,
            image_s3_key="calendar/direct/item.png",
            status=CalendarStatus.COMPLETED.value,
        )
        url = reverse(
            "style_calendar:calendar-callback",
            kwargs={"calendar_id": direct_entry.pk},
        )
        payload = self.processing_payload()
        payload["calendar_id"] = str(direct_entry.pk)

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, 409)

    def test_missing_calendar_returns_not_found(self) -> None:
        missing_id = uuid4()
        url = reverse(
            "style_calendar:calendar-callback",
            kwargs={"calendar_id": missing_id},
        )
        payload = self.processing_payload()
        payload["calendar_id"] = str(missing_id)

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, 404)

    def test_completed_callback_requires_extracted_item(self) -> None:
        payload = self.completed_payload()
        payload["items"] = [payload["items"][1]]

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, CalendarStatus.REGISTERED.value)
        self.assertEqual(self.entry.items.count(), 0)

    def test_callback_rejects_duplicate_processor_item_id(self) -> None:
        payload = self.completed_payload()
        duplicate = deepcopy(payload["items"][0])
        duplicate["sort_order"] = 2
        duplicate["image_s3_key"] = (
            f"calendar/{self.user.pk}/{self.entry.pk}/item_duplicate.png"
        )
        payload["items"].append(duplicate)

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.entry.items.count(), 0)

    def test_callback_database_error_rolls_back_entry_and_items(self) -> None:
        serializer = CalendarCallbackSerializer(data=self.completed_payload())
        serializer.is_valid(raise_exception=True)

        with (
            patch.object(
                CalendarItem.objects,
                "bulk_create",
                side_effect=RuntimeError("database write failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            calendar_callback.apply_callback(
                calendar_id=self.entry.pk,
                data=serializer.validated_data,
            )

        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, CalendarStatus.REGISTERED.value)
        self.assertEqual(self.entry.items.count(), 0)
