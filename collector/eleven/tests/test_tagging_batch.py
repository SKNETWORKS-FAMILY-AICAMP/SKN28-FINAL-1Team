import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import batch_tagger
import eleven_collector_db as collector
from util.tagging.openai_batch import parse_result_lines


class OpenAIBatchUtilTests(unittest.TestCase):
    def test_parse_result_lines_splits_success_and_failure(self):
        success = json.dumps(
            {
                "custom_id": "7",
                "response": {
                    "status_code": 200,
                    "body": {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {"season": ["여름"]},
                                        ensure_ascii=False,
                                    )
                                }
                            }
                        ]
                    },
                },
            },
            ensure_ascii=False,
        )
        failed = json.dumps({"custom_id": "8", "error": {"code": "x"}})
        error_file_line = json.dumps({"custom_id": "9"})

        results, failed_ids = parse_result_lines(
            [success, failed],
            [error_file_line],
        )

        self.assertEqual(results, {7: {"season": ["여름"]}})
        self.assertEqual(failed_ids, [8, 9])


class ElevenBatchTaggerTests(unittest.TestCase):
    def _product(self):
        return {
            "id": 11,
            "title": "화이트 반팔 티셔츠",
            "image_url": "https://example.com/product.jpg",
            "eleven_category1": "여성의류",
            "eleven_category2": "티셔츠",
            "eleven_category3": "",
            "eleven_category4": "",
            "category_large": "상의",
            "category_small": "티셔츠",
        }

    def test_request_line_uses_shared_openai_batch_format(self):
        request = json.loads(batch_tagger._request_line(self._product()))

        self.assertEqual(request["custom_id"], "11")
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["url"], "/v1/chat/completions")
        self.assertEqual(request["body"]["model"], batch_tagger.OPENAI_MODEL)

    def test_submit_pending_tracks_batch_and_queues_products(self):
        client = SimpleNamespace(
            files=SimpleNamespace(
                create=Mock(return_value=SimpleNamespace(id="file-1"))
            ),
            batches=SimpleNamespace(
                create=Mock(return_value=SimpleNamespace(id="batch-1"))
            ),
        )
        conn = object()

        with (
            patch.object(batch_tagger, "_client", return_value=client),
            patch.object(
                batch_tagger.db,
                "fetch_pending_products",
                side_effect=[[self._product()], []],
            ),
            patch.object(batch_tagger.db, "insert_tagging_batch") as insert,
            patch.object(
                batch_tagger.db, "set_products_tagging_status"
            ) as set_status,
        ):
            submitted = batch_tagger.submit_pending(conn)

        self.assertEqual(submitted, 1)
        insert.assert_called_once()
        set_status.assert_called_once_with(conn, [11], "queued")

    def test_collect_job_uses_batch_submit_in_batch_mode(self):
        fake_batch_module = ModuleType("batch_tagger")
        fake_batch_module.submit_pending = Mock()
        conn = object()
        entries = [object()]

        with (
            patch.object(collector, "TAGGING_MODE", "batch"),
            patch.object(collector, "collect") as collect,
            patch.dict(sys.modules, {"batch_tagger": fake_batch_module}),
        ):
            collector.run_collect_job(
                conn,
                entries,
                limit_per_keyword=3,
                skip_llm=False,
            )

        collect.assert_called_once_with(
            conn,
            entries,
            3,
            skip_llm=True,
            dry_run=False,
        )
        fake_batch_module.submit_pending.assert_called_once_with(conn)

    def test_cli_exposes_batch_jobs(self):
        self.assertEqual(
            collector.parse_args(["--job", "batch-submit"]).job,
            "batch-submit",
        )
        self.assertEqual(
            collector.parse_args(["--job", "batch-poll"]).job,
            "batch-poll",
        )


if __name__ == "__main__":
    unittest.main()
