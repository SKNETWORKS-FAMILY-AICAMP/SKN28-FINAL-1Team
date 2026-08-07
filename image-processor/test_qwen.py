import io
import unittest

from PIL import Image

from pipeline.qwen import NormalizeGenerator, SingleItemEnumerator, _json, normalize_tags
from worker import callback_payload_from_manifest


class QwenPipelineSmokeTest(unittest.TestCase):
    def test_normalize_parse_and_taxonomy(self):
        source = io.BytesIO()
        Image.new("RGB", (1500, 500)).save(source, "JPEG")
        item = SingleItemEnumerator().enumerate(source.getvalue(), "image/jpeg")[0]
        result = NormalizeGenerator().generate(source.getvalue(), "image/jpeg", item)
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual((image.format, max(image.size)), ("PNG", 1024))

        parsed = _json(
            '설명 ```json {"category_large":"하의","category_small":"티셔츠",'
            '"style":["캐주얼","시크","포멀"],"usage":["데일리","", " "]} ```'
        )
        tags = normalize_tags(parsed)
        self.assertEqual(tags["category_large"], "상의")
        self.assertEqual(len(tags["style"]), 2)
        self.assertEqual(tags["usage"], ["데일리"])

    def test_callback_removes_blank_usage_from_existing_manifest(self):
        payload = callback_payload_from_manifest({
            "job_id": "job-1",
            "pipeline": {"impl": "qwen-tag"},
            "counts": {"failed": 0},
            "items": [{
                "s3_key": "item.png",
                "tags": {"category_large": "상의", "usage": ["데일리", "", " "]},
                "image_vector": [],
                "text_vector": [],
            }],
        })

        self.assertEqual(payload["items"][0]["usage"], ["데일리"])


if __name__ == "__main__":
    unittest.main()
