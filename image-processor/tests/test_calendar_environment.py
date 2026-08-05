from __future__ import annotations

import unittest
from unittest.mock import patch

import config
from services import calendar_queue


class CalendarEnvironmentValidationTests(unittest.TestCase):
    def test_rejects_whitespace_only_calendar_queue_key(self) -> None:
        with (
            patch.object(config, "CALENDAR_PENDING_KEY", "   "),
            self.assertRaises(calendar_queue.CalendarQueueConfigurationError),
        ):
            calendar_queue.validate_configuration()

    def test_rejects_wardrobe_retry_hash_collision(self) -> None:
        with (
            patch.object(config, "CALENDAR_PENDING_KEY", config.RETRY_HASH),
            self.assertRaises(calendar_queue.CalendarQueueConfigurationError),
        ):
            calendar_queue.validate_configuration()


if __name__ == "__main__":
    unittest.main()
