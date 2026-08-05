from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import benchmark


class BenchmarkTests(unittest.TestCase):
    def test_prompt_uses_wardrobe_taxonomy(self) -> None:
        prompt = benchmark.build_prompt("남성 오버핏 라운드 니트")

        self.assertIn("언더웨어/이너웨어", prompt)
        self.assertIn("스카이블루", prompt)
        self.assertIn("그래픽/로고", prompt)
        self.assertIn("오버핏", prompt)
        self.assertNotIn("살짝 넉넉한 핏", prompt)

    def test_dataset_validation_rejects_out_of_taxonomy_value(self) -> None:
        dataset = {
            "samples": [
                {
                    "id": "sample",
                    "file_name": "sample.jpg",
                    "product_name": "니트",
                    "expected": {
                        "category_large": "상의",
                        "color": "네이비",
                        "pattern": "무지",
                        "fit": "살짝 넉넉한 핏",
                    },
                }
            ]
        }

        errors = benchmark.validate_dataset(
            dataset,
            image_dir=Path("unused"),
            require_images=False,
            expected_count=1,
        )

        self.assertTrue(any("expected.fit" in error for error in errors))

    def test_scoring_parses_fenced_json_and_compares_fields(self) -> None:
        dataset = {
            "samples": [
                {
                    "id": "knit",
                    "expected": {
                        "category_large": "상의",
                        "color": "네이비",
                        "pattern": "무지",
                        "fit": "오버핏",
                    },
                }
            ]
        }
        results = [
            {
                "sample_id": "knit",
                "model": "test-model",
                "raw_output": (
                    "```json\n"
                    + json.dumps(dataset["samples"][0]["expected"], ensure_ascii=False)
                    + "\n```"
                ),
                "latency_seconds": 2.5,
                "peak_vram_mb": 4096,
            }
        ]

        rows, summary = benchmark.score_results(dataset, results)

        self.assertTrue(rows[0]["json_valid"])
        self.assertTrue(rows[0]["taxonomy_valid"])
        self.assertTrue(rows[0]["all_fields_match"])
        self.assertEqual(summary["models"]["test-model"]["all_fields_accuracy"], 1.0)

    def test_write_prompts_creates_one_jsonl_record_per_sample(self) -> None:
        dataset = {
            "samples": [
                {
                    "id": "knit",
                    "file_name": "knit.jpg",
                    "product_name": "네이비 니트",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "prompts.jsonl"
            benchmark.write_prompts(dataset, output)
            records = benchmark.load_jsonl(output)

        self.assertEqual(records[0]["sample_id"], "knit")
        self.assertIn("네이비 니트", records[0]["prompt"])


if __name__ == "__main__":
    unittest.main()

