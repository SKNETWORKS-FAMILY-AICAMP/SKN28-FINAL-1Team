"""착용 이미지 생성 테스트.

핵심은 두 가지다.

- **코디당 한 번만 만든다.** 같은 골든 코디가 여러 사용자·여러 날에 추천되므로,
  이미 있으면 생성 없이 그 키를 쓴다. 여기가 새면 요금이 사용자 수만큼 붙는다.
- **실패해도 추천은 살아남는다.** 이미지가 없으면 아이템 카드로 화면이 성립한다.
"""

from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.recommend.services import outfit_render
from apps.recommend.services.outfit_render import (
    RenderError,
    RenderRef,
    _extract_image,
    _reference_keys,
    ensure_render,
    render_key_for,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"
DATA_URL = "data:image/png;base64," + base64.b64encode(PNG).decode()
BUCKET = "skn28-cozy3"
ITEMS = [
    {"item_key": "095#000", "s3_key": "goldenset/derived/v1/095/item_000.png"},
    {"item_key": "095#001", "s3_key": "goldenset/derived/v1/095/item_001.png"},
    {"item_key": "095#002"},  # 이미지가 없는 아이템 (분리 실패 등)
]
RENDER_KEY = "goldenset/derived/v1/095/render_frontal.png"


class RenderKeyTests(unittest.TestCase):
    def test_render_sits_next_to_item_images(self) -> None:
        """골든셋 산출물과 같은 위치. api가 derived prefix를 따로 알 필요가 없다."""
        self.assertEqual(render_key_for(ITEMS[0]["s3_key"]), RENDER_KEY)

    def test_key_is_the_same_from_any_item(self) -> None:
        """어느 아이템에서 유도해도 같은 키라 별도 캐시 테이블이 필요 없다."""
        self.assertEqual(
            render_key_for("goldenset/derived/v1/095/item_000.png"),
            render_key_for("goldenset/derived/v1/095/item_007.png"),
        )

    def test_different_outfits_do_not_collide(self) -> None:
        self.assertNotEqual(
            render_key_for("goldenset/derived/v1/095/item_000.png"),
            render_key_for("goldenset/derived/v1/096/item_000.png"),
        )

    def test_items_without_image_are_skipped(self) -> None:
        self.assertEqual(len(_reference_keys(ITEMS)), 2)

    @override_settings(DAILY_LOOK_RENDER_MAX_REFERENCES=3)
    def test_reference_count_is_capped(self) -> None:
        """참조 장수만큼 입력 토큰과 요금이 오른다."""
        many = [{"s3_key": f"goldenset/derived/v1/095/item_{n:03d}.png"} for n in range(20)]
        self.assertEqual(len(_reference_keys(many)), 3)


class EnsureRenderTests(TestCase):
    @patch("apps.recommend.services.outfit_render.storage.exists_for", return_value=True)
    @patch("apps.recommend.services.outfit_render._generate")
    def test_existing_render_is_reused_without_generating(self, generate, _exists):
        """이미 만들어 둔 코디면 모델을 부르지 않는다 — 요금이 걸린 지점이다."""
        reference = ensure_render(bucket=BUCKET, items=ITEMS)
        self.assertEqual(reference, RenderRef(BUCKET, RENDER_KEY))
        generate.assert_not_called()

    @patch("apps.recommend.services.outfit_render.storage.put_bytes_for")
    @patch("apps.recommend.services.outfit_render.storage.exists_for", return_value=False)
    @patch("apps.recommend.services.outfit_render._generate", return_value=PNG)
    def test_missing_render_is_generated_and_stored(self, generate, _exists, put):
        reference = ensure_render(bucket=BUCKET, items=ITEMS)
        self.assertEqual(reference.s3_key, RENDER_KEY)
        generate.assert_called_once()
        put.assert_called_once_with(BUCKET, RENDER_KEY, PNG, "image/png")

    @patch("apps.recommend.services.outfit_render.storage.exists_for", return_value=False)
    @patch("apps.recommend.services.outfit_render._generate")
    @override_settings(DAILY_LOOK_RENDER_ENABLED=False)
    def test_disabled_switch_skips_generation(self, generate, _exists):
        self.assertIsNone(ensure_render(bucket=BUCKET, items=ITEMS))
        generate.assert_not_called()

    @patch("apps.recommend.services.outfit_render._generate")
    def test_no_reference_images_skips_generation(self, generate):
        self.assertIsNone(ensure_render(bucket=BUCKET, items=[{"item_key": "x"}]))
        self.assertIsNone(ensure_render(bucket="", items=ITEMS))
        generate.assert_not_called()

    @patch("apps.recommend.services.outfit_render.storage.exists_for", return_value=False)
    @patch(
        "apps.recommend.services.outfit_render._generate",
        side_effect=RenderError("모델 응답에 이미지가 없습니다"),
    )
    def test_generation_failure_propagates_as_render_error(self, _generate, _exists):
        """호출부(daily_look)가 잡아 추천은 살리고 이미지만 비운다."""
        with self.assertRaises(RenderError):
            ensure_render(bucket=BUCKET, items=ITEMS)


class ExtractImageTests(unittest.TestCase):
    """제공자마다 이미지를 담는 자리가 달라 두 형태를 모두 본다."""

    def test_images_array(self) -> None:
        payload = {"choices": [{"message": {"images": [{"image_url": {"url": DATA_URL}}]}}]}
        self.assertEqual(_extract_image(payload), PNG)

    def test_content_string(self) -> None:
        self.assertEqual(
            _extract_image({"choices": [{"message": {"content": DATA_URL}}]}), PNG
        )

    def test_content_list(self) -> None:
        payload = {
            "choices": [
                {"message": {"content": [{"type": "image_url", "image_url": {"url": DATA_URL}}]}}
            ]
        }
        self.assertEqual(_extract_image(payload), PNG)

    def test_text_only_response_is_not_mistaken_for_an_image(self) -> None:
        """모델이 거절문만 돌려주는 경우. 조용히 빈 파일을 저장하면 안 된다."""
        payload = {"choices": [{"message": {"content": "죄송하지만 만들 수 없습니다."}}]}
        self.assertIsNone(_extract_image(payload))

    def test_corrupt_base64(self) -> None:
        payload = {"choices": [{"message": {"content": "data:image/png;base64,@@@@"}}]}
        self.assertIsNone(_extract_image(payload))

    def test_empty_payload(self) -> None:
        self.assertIsNone(_extract_image({}))
        self.assertIsNone(_extract_image({"choices": []}))
