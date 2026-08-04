from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from calendar_consumer import (
    CalendarConsumer,
    CalendarJob,
    CalendarJobValidationError,
    ConsumeOutcome,
)


def valid_payload() -> dict:
    return {
        "schema_version": "calendar-job.v1",
        "task_type": "calendar_image_extraction",
        "calendar_id": str(uuid4()),
        "user_id": 7,
        "source": {
            "bucket": "calendar-private",
            "key": "calendar/7/source.jpg",
        },
        "output_prefix": "calendar/7/result",
        "callback_url": "http://api:8000/api/v1/internal/calendars/id/callback/",
        "created_at": "2026-08-04T12:34:56+09:00",
    }


class CalendarJobTests(unittest.TestCase):
    def test_accepts_producer_contract(self) -> None:
        payload = valid_payload()

        job = CalendarJob.from_payload(payload)

        self.assertEqual(job.calendar_id, payload["calendar_id"])
        self.assertEqual(job.user_id, 7)
        self.assertEqual(job.source.bucket, "calendar-private")
        self.assertEqual(job.source.key, "calendar/7/source.jpg")

    def test_rejects_wardrobe_or_unknown_task(self) -> None:
        payload = valid_payload()
        payload["task_type"] = "wardrobe_image_extraction"

        with self.assertRaises(CalendarJobValidationError):
            CalendarJob.from_payload(payload)

    def test_rejects_invalid_json_and_calendar_id(self) -> None:
        with self.assertRaises(CalendarJobValidationError):
            CalendarJob.from_raw("not-json")

        payload = valid_payload()
        payload["calendar_id"] = "not-a-uuid"
        with self.assertRaises(CalendarJobValidationError):
            CalendarJob.from_payload(payload)


class CalendarConsumerTests(unittest.TestCase):
    @patch("calendar_consumer.calendar_queue.ack", return_value=True)
    @patch("calendar_consumer.calendar_queue.fetch")
    def test_successful_handler_is_acked(self, fetch: Mock, ack: Mock) -> None:
        raw = json.dumps(valid_payload())
        fetch.return_value = raw
        handler = Mock()

        outcome = CalendarConsumer(handler).consume_once()

        self.assertEqual(outcome, ConsumeOutcome.ACKED)
        handler.assert_called_once()
        ack.assert_called_once_with(raw)

    @patch("calendar_consumer.calendar_queue.ack")
    @patch("calendar_consumer.calendar_queue.fetch")
    def test_handler_failure_stays_in_processing(self, fetch: Mock, ack: Mock) -> None:
        fetch.return_value = json.dumps(valid_payload())
        handler = Mock(side_effect=RuntimeError("pipeline failed"))

        outcome = CalendarConsumer(handler).consume_once()

        self.assertEqual(outcome, ConsumeOutcome.HELD)
        ack.assert_not_called()

    @patch("calendar_consumer.calendar_queue.ack")
    @patch("calendar_consumer.calendar_queue.fetch", return_value="not-json")
    def test_invalid_payload_stays_in_processing(self, fetch: Mock, ack: Mock) -> None:
        outcome = CalendarConsumer(Mock()).consume_once()

        self.assertEqual(outcome, ConsumeOutcome.HELD)
        ack.assert_not_called()

    @patch("calendar_consumer.calendar_queue.ack")
    @patch("calendar_consumer.calendar_queue.fetch", return_value=None)
    def test_empty_queue_does_nothing(self, fetch: Mock, ack: Mock) -> None:
        outcome = CalendarConsumer(Mock()).consume_once()

        self.assertEqual(outcome, ConsumeOutcome.EMPTY)
        ack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
