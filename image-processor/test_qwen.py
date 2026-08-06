import io
import unittest

from PIL import Image

from pipeline.qwen import NormalizeGenerator, SingleItemEnumerator, _json, normalize_tags


class QwenPipelineSmokeTest(unittest.TestCase):
    def test_normalize_parse_and_taxonomy(self):
        source = io.BytesIO()
        Image.new("RGB", (1500, 500)).save(source, "JPEG")
        item = SingleItemEnumerator().enumerate(source.getvalue(), "image/jpeg")[0]
        result = NormalizeGenerator().generate(source.getvalue(), "image/jpeg", item)
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual((image.format, max(image.size)), ("PNG", 1024))

        parsed = _json('설명 ```json {"category_large":"하의","category_small":"티셔츠","style":["캐주얼","시크","포멀"]} ```')
        tags = normalize_tags(parsed)
        self.assertEqual(tags["category_large"], "상의")
        self.assertEqual(len(tags["style"]), 2)


if __name__ == "__main__":
    unittest.main()
