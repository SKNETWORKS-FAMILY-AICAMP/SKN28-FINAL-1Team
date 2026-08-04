from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from uuid import uuid4

from calendar_consumer import CalendarJob, CalendarSource
from calendar_manifest import create_manifest
from pipeline import EnumeratedItem, ProcessedItem


def calendar_job() -> CalendarJob:
    return CalendarJob(
        schema_version="calendar-job.v1",
        task_type="calendar_image_extraction",
        calendar_id=str(uuid4()),
        user_id=7,
        source=CalendarSource(
            bucket="calendar-private",
            key="calendar/7/source.jpg",
        ),
        output_prefix="calendar/7/result",
        callback_url="http://api:8000/callback/",
        created_at="2026-08-04T12:34:56+09:00",
    )


def processed_item(*, index: int = 0, succeeded: bool = True) -> ProcessedItem:
    enum = EnumeratedItem(
        descriptor_en="navy jacket",
        label_ko="네이비 재킷",
        category_large="아우터",
        bbox=[100, 200, 800, 700],
    )
    if not succeeded:
        return ProcessedItem(
            index=index,
            enum=enum,
            error="RuntimeError: generation failed",
        )
    return ProcessedItem(
        index=index,
        enum=enum,
        image_png=b"png",
        tags={
            "item_name": "네이비 재킷",
            "category_large": "아우터",
            "category_small": "자켓",
            "_missing_required": ["fit"],
        },
    )


class CalendarManifestTests(unittest.TestCase):
    def test_completed_manifest_contains_callback_reference_fields(self) -> None:
        job = calendar_job()
        completed_at = datetime(2026, 8, 4, 4, 5, 6, tzinfo=UTC)

        manifest = create_manifest(
            job=job,
            pipeline_key="fake-pipeline",
            items=[processed_item()],
            total_sec=1.2345,
            completed_at=completed_at,
        )

        self.assertEqual(manifest["schema_version"], "calendar-result.v1")
        self.assertEqual(manifest["calendar_id"], job.calendar_id)
        self.assertEqual(manifest["status"], "COMPLETED")
        self.assertEqual(
            manifest["output"],
            {
                "bucket": "calendar-private",
                "prefix": "calendar/7/result",
                "manifest_s3_key": "calendar/7/result/manifest.json",
            },
        )
        self.assertEqual(manifest["completed_at"], "2026-08-04T04:05:06+00:00")
        self.assertEqual(manifest["total_sec"], 1.234)
        self.assertFalse(manifest["pipeline"]["embedding_enabled"])
        json.dumps(manifest)

    def test_partial_item_failure_keeps_calendar_completed(self) -> None:
        manifest = create_manifest(
            job=calendar_job(),
            pipeline_key="fake-pipeline",
            items=[processed_item(), processed_item(index=1, succeeded=False)],
            total_sec=1,
        )

        self.assertEqual(manifest["status"], "COMPLETED")
        self.assertEqual(
            manifest["counts"],
            {"detected": 2, "succeeded": 1, "failed": 1},
        )
        self.assertEqual(manifest["items"][1]["status"], "FAILED")

    def test_no_successful_item_marks_manifest_failed(self) -> None:
        manifest = create_manifest(
            job=calendar_job(),
            pipeline_key="fake-pipeline",
            items=[processed_item(succeeded=False)],
            total_sec=1,
        )

        self.assertEqual(manifest["status"], "FAILED")
        self.assertEqual(manifest["counts"]["succeeded"], 0)

    def test_processor_item_id_is_stable_for_calendar_and_index(self) -> None:
        job = calendar_job()

        manifest = create_manifest(
            job=job,
            pipeline_key="fake-pipeline",
            items=[processed_item(index=3)],
            total_sec=1,
        )

        self.assertEqual(
            manifest["items"][0]["processor_item_id"],
            f"{job.calendar_id}:003",
        )
        self.assertNotIn("image_vector", manifest["items"][0])
        self.assertNotIn("text_vector", manifest["items"][0])

    def test_naive_completed_at_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            create_manifest(
                job=calendar_job(),
                pipeline_key="fake-pipeline",
                items=[],
                total_sec=0,
                # timezone 누락 값을 거부하는 계약을 검증한다.
                completed_at=datetime(2026, 8, 4),  # noqa: DTZ001
            )


if __name__ == "__main__":
    unittest.main()
