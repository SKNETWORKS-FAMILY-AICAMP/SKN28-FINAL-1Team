import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import redis
from django.test import SimpleTestCase

from apps.style_calendar.contracts import (
    CALENDAR_JOB_SCHEMA_VERSION,
    CALENDAR_JOB_TASK_TYPE,
)
from apps.style_calendar.services import queue, storage


class CalendarQueueProducerTests(SimpleTestCase):
    calendar_id = UUID("11111111-1111-1111-1111-111111111111")

    def setUp(self) -> None:
        self.entry = SimpleNamespace(
            pk=self.calendar_id,
            user_id=7,
            image_s3_key=f"calendar/7/{self.calendar_id}/original.jpg",
            created_at=datetime(2026, 8, 8, 10, 30, tzinfo=timezone.utc),
        )
        self.redis_client = MagicMock()
        patches = [
            patch.object(queue, "QUEUE_KEY", "calendar:jobs"),
            patch.object(queue, "PROCESSING_QUEUE_KEY", "calendar:jobs:processing"),
            patch.object(queue, "WARDROBE_QUEUE_KEY", "wardrobe:jobs"),
            patch.object(
                queue,
                "CALLBACK_BASE_URL",
                "https://api.example.com/api/v1/internal/calendars",
            ),
            patch.object(storage, "BUCKET", "calendar-bucket"),
            patch.object(queue, "_redis", return_value=self.redis_client),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_enqueue_pushes_versioned_payload_to_calendar_queue(self) -> None:
        queue.enqueue(self.entry)

        self.redis_client.lpush.assert_called_once()
        queue_key, raw_payload = self.redis_client.lpush.call_args.args
        payload = json.loads(raw_payload)
        self.assertEqual(queue_key, "calendar:jobs")
        self.assertEqual(payload["schema_version"], CALENDAR_JOB_SCHEMA_VERSION)
        self.assertEqual(payload["task_type"], CALENDAR_JOB_TASK_TYPE)
        self.assertEqual(payload["calendar_id"], str(self.calendar_id))
        self.assertEqual(payload["user_id"], 7)
        self.assertEqual(
            payload["source"],
            {
                "bucket": "calendar-bucket",
                "key": f"calendar/7/{self.calendar_id}/original.jpg",
            },
        )
        self.assertEqual(
            payload["output_prefix"],
            f"calendar/7/{self.calendar_id}/",
        )
        self.assertEqual(
            payload["callback_url"],
            f"https://api.example.com/api/v1/internal/calendars/{self.calendar_id}/callback/",
        )
        self.assertEqual(payload["created_at"], "2026-08-08T10:30:00+00:00")
        self.assertNotIn("wardrobe_item_ids", payload)

    def test_redis_error_is_propagated_to_caller(self) -> None:
        self.redis_client.lpush.side_effect = redis.RedisError("redis down")

        with self.assertRaises(redis.RedisError):
            queue.enqueue(self.entry)

    def test_configuration_rejects_wardrobe_queue_collision(self) -> None:
        with (
            patch.object(queue, "QUEUE_KEY", "wardrobe:jobs"),
            self.assertRaises(queue.CalendarQueueConfigurationError),
        ):
            queue.enqueue(self.entry)

        self.redis_client.lpush.assert_not_called()

    def test_configuration_rejects_same_waiting_and_processing_queue(self) -> None:
        with (
            patch.object(queue, "PROCESSING_QUEUE_KEY", "calendar:jobs"),
            self.assertRaises(queue.CalendarQueueConfigurationError),
        ):
            queue.enqueue(self.entry)

        self.redis_client.lpush.assert_not_called()

    def test_configuration_requires_callback_and_s3_bucket(self) -> None:
        with (
            patch.object(queue, "CALLBACK_BASE_URL", ""),
            self.assertRaises(queue.CalendarQueueConfigurationError),
        ):
            queue.enqueue(self.entry)
        with (
            patch.object(storage, "BUCKET", ""),
            self.assertRaises(queue.CalendarQueueConfigurationError),
        ):
            queue.enqueue(self.entry)

        self.redis_client.lpush.assert_not_called()


class CalendarRedisClientTests(SimpleTestCase):
    def tearDown(self) -> None:
        queue._redis.cache_clear()

    @patch("apps.style_calendar.services.queue.redis.Redis.from_url")
    def test_redis_client_passes_password_separately(self, mock_from_url) -> None:
        queue._redis.cache_clear()
        with (
            patch.object(queue, "REDIS_URL", "redis://redis:6379/0"),
            patch.object(queue, "REDIS_PASSWORD", "secret"),
        ):
            queue._redis()

        mock_from_url.assert_called_once_with(
            "redis://redis:6379/0",
            decode_responses=True,
            password="secret",
        )
