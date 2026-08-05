from unittest.mock import patch

from django.test import SimpleTestCase

from apps.style_calendar.services import queue, storage


class CalendarEnvironmentValidationTests(SimpleTestCase):
    def setUp(self) -> None:
        patches = [
            patch.object(queue, "REDIS_URL", "redis://redis:6379/0"),
            patch.object(queue, "QUEUE_KEY", "calendar:jobs"),
            patch.object(
                queue,
                "PROCESSING_QUEUE_KEY",
                "calendar:jobs:processing",
            ),
            patch.object(queue, "WARDROBE_QUEUE_KEY", "wardrobe:jobs"),
            patch.object(
                queue,
                "CALLBACK_BASE_URL",
                "https://api.example.com/api/v1/internal/calendars",
            ),
            patch.object(storage, "BUCKET", "calendar-bucket"),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_requires_non_blank_redis_url(self) -> None:
        with (
            patch.object(queue, "REDIS_URL", ""),
            self.assertRaises(queue.CalendarQueueConfigurationError),
        ):
            queue.validate_configuration()

    def test_rejects_whitespace_only_calendar_queue_key(self) -> None:
        with (
            patch.object(queue, "QUEUE_KEY", "   "),
            self.assertRaises(queue.CalendarQueueConfigurationError),
        ):
            queue.validate_configuration()

    def test_rejects_all_wardrobe_queue_key_collisions(self) -> None:
        wardrobe_keys = (
            "wardrobe:jobs",
            "wardrobe:jobs:processing",
            "wardrobe:jobs:dead",
            "wardrobe:jobs:retries",
        )

        for key in wardrobe_keys:
            with (
                self.subTest(key=key),
                patch.object(queue, "QUEUE_KEY", key),
                self.assertRaises(queue.CalendarQueueConfigurationError),
            ):
                queue.validate_configuration()

    def test_storage_rejects_whitespace_only_bucket(self) -> None:
        with self.assertRaises(storage.CalendarStorageConfigurationError):
            storage._require_bucket("   ", "CALENDAR_S3_BUCKET")
