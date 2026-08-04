from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from PIL import Image

from calendar_consumer import CalendarJob, CalendarSource
from calendar_pipeline import (
    CalendarImagePipeline,
    CalendarManifestConflictError,
)
from pipeline import (
    EnumeratedItem,
    ProcessedItem,
    WardrobePipeline,
    build_calendar_pipeline,
)


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


def enumerated_item() -> EnumeratedItem:
    return EnumeratedItem(
        descriptor_en="navy jacket",
        label_ko="네이비 재킷",
        category_large="아우터",
        bbox=[100, 200, 800, 700],
    )


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class CalendarEmbeddingPolicyTests(unittest.TestCase):
    def test_calendar_factory_never_configures_embedder(self) -> None:
        pipeline = build_calendar_pipeline()

        self.assertIsNone(pipeline.embedder)

    def test_pipeline_with_no_embedder_skips_embedding_stage(self) -> None:
        enumerator = Mock()
        enumerator.enumerate.return_value = [enumerated_item()]
        generator = Mock(key="fake-generator")
        generator.generate.return_value = png_bytes()
        tagger = Mock()
        tagger.tag.return_value = {
            "item_name": "네이비 재킷",
            "category_large": "아우터",
            "category_small": "자켓",
        }
        pipeline = WardrobePipeline(enumerator, generator, tagger, embedder=None)

        items = pipeline.process(b"source", "image/jpeg")

        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].ok)
        self.assertEqual(items[0].image_vector, [])
        self.assertEqual(items[0].text_vector, [])
        self.assertNotIn("embed", items[0].timings)


class CalendarImagePipelineTests(unittest.TestCase):
    @patch("calendar_pipeline.s3io.put_json")
    @patch("calendar_pipeline.s3io.upload_png")
    @patch("calendar_pipeline.s3io.download")
    @patch("calendar_pipeline.s3io.get_json", return_value=None)
    def test_process_uploads_items_then_calendar_manifest(
        self,
        get_json: Mock,
        download: Mock,
        upload_png: Mock,
        put_json: Mock,
    ) -> None:
        job = calendar_job()
        download.side_effect = (
            lambda bucket, key, path: Path(path).write_bytes(b"source")
        )
        succeeded = ProcessedItem(
            index=0,
            enum=enumerated_item(),
            image_png=png_bytes(),
            tags={
                "item_name": "네이비 재킷",
                "category_large": "아우터",
                "category_small": "자켓",
                "_missing_required": ["fit"],
            },
        )
        failed = ProcessedItem(
            index=1,
            enum=enumerated_item(),
            error="RuntimeError: generation failed",
        )
        item_pipeline = Mock(key="fake-pipeline")
        item_pipeline.process.return_value = [succeeded, failed]

        manifest = CalendarImagePipeline(item_pipeline).process(job)

        get_json.assert_called_once_with(
            "calendar-private",
            "calendar/7/result/manifest.json",
        )
        download.assert_called_once()
        item_pipeline.process.assert_called_once_with(b"source", "image/jpeg")
        upload_png.assert_called_once()
        put_json.assert_called_once_with(
            "calendar-private",
            "calendar/7/result/manifest.json",
            manifest,
        )
        self.assertEqual(manifest["schema_version"], "calendar-result.v1")
        self.assertFalse(manifest["pipeline"]["embedding_enabled"])
        self.assertEqual(manifest["counts"], {
            "detected": 2,
            "succeeded": 1,
            "failed": 1,
        })
        self.assertEqual(manifest["items"][0]["status"], "EXTRACTED")
        self.assertEqual(manifest["items"][0]["category"], "자켓")
        self.assertEqual(manifest["items"][0]["meta"]["missing_required"], ["fit"])
        self.assertNotIn("image_vector", manifest["items"][0])
        self.assertNotIn("text_vector", manifest["items"][0])
        self.assertEqual(manifest["items"][1]["status"], "FAILED")
        self.assertEqual(manifest["items"][1]["image_s3_key"], "")

    @patch("calendar_pipeline.s3io.download")
    @patch("calendar_pipeline.s3io.get_json")
    def test_existing_matching_manifest_skips_processing(
        self,
        get_json: Mock,
        download: Mock,
    ) -> None:
        job = calendar_job()
        existing = {
            "schema_version": "calendar-result.v1",
            "calendar_id": job.calendar_id,
            "items": [],
        }
        get_json.return_value = existing
        item_pipeline = Mock(key="fake-pipeline")

        result = CalendarImagePipeline(item_pipeline).process(job)

        self.assertIs(result, existing)
        download.assert_not_called()
        item_pipeline.process.assert_not_called()

    def test_conflicting_existing_manifest_is_rejected(self) -> None:
        job = calendar_job()
        item_pipeline = Mock(key="fake-pipeline")
        conflicting = {
            "schema_version": "calendar-result.v1",
            "calendar_id": str(uuid4()),
        }

        with (
            patch("calendar_pipeline.s3io.get_json", return_value=conflicting),
            self.assertRaises(CalendarManifestConflictError),
        ):
            CalendarImagePipeline(item_pipeline).process(job)


if __name__ == "__main__":
    unittest.main()
