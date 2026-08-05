from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import config
from services import calendar_queue


class CalendarQueueTests(unittest.TestCase):
    @patch("services.calendar_queue._redis")
    def test_fetch_moves_oldest_job_to_calendar_processing(self, redis_factory: Mock) -> None:
        client = redis_factory.return_value
        client.blmove.return_value = "raw-job"

        raw = calendar_queue.fetch(timeout=11)

        self.assertEqual(raw, "raw-job")
        client.blmove.assert_called_once_with(
            config.CALENDAR_PENDING_KEY,
            config.CALENDAR_PROCESSING_KEY,
            11,
            src="RIGHT",
            dest="LEFT",
        )

    @patch("services.calendar_queue._redis")
    def test_ack_only_removes_calendar_processing_item(self, redis_factory: Mock) -> None:
        client = redis_factory.return_value
        client.lrem.return_value = 1

        acknowledged = calendar_queue.ack("raw-job")

        self.assertTrue(acknowledged)
        client.lrem.assert_called_once_with(
            config.CALENDAR_PROCESSING_KEY,
            1,
            "raw-job",
        )

    @patch("services.calendar_queue._redis")
    def test_ack_returns_false_when_processing_item_is_missing(
        self,
        redis_factory: Mock,
    ) -> None:
        client = redis_factory.return_value
        client.lrem.return_value = 0

        acknowledged = calendar_queue.ack("missing-job")

        self.assertFalse(acknowledged)

    def test_rejects_wardrobe_queue_collision(self) -> None:
        with (
            patch.object(config, "CALENDAR_PENDING_KEY", config.PENDING_KEY),
            self.assertRaises(calendar_queue.CalendarQueueConfigurationError),
        ):
            calendar_queue.validate_configuration()

    def test_rejects_same_pending_and_processing_key(self) -> None:
        with (
            patch.object(config, "CALENDAR_PENDING_KEY", "calendar:same"),
            patch.object(config, "CALENDAR_PROCESSING_KEY", "calendar:same"),
            self.assertRaises(calendar_queue.CalendarQueueConfigurationError),
        ):
            calendar_queue.validate_configuration()


if __name__ == "__main__":
    unittest.main()
