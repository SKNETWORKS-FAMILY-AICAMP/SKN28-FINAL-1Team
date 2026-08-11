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
    PROVIDER_MAX_REFERENCES,
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

    @override_settings(DAILY_LOOK_RENDER_MAX_REFERENCES=99)
    def test_provider_hard_limit_wins_over_settings(self) -> None:
        """.env에 옛 값(5)이 남은 서버에서 그대로 재현되던 400을 막는다.

            Provider rejections: Alibaba: input_references:
            must have between 0 and 4 items

        qwen/qwen-image-3-pro는 제공자가 Alibaba 하나뿐이라 5장을 보내면 다른
        곳으로 넘어가지 못하고 요청 자체가 실패한다.
        """
        many = [{"s3_key": f"k/item_{n:03d}.png"} for n in range(20)]
        self.assertEqual(len(_reference_keys(many)), PROVIDER_MAX_REFERENCES)
        self.assertLessEqual(PROVIDER_MAX_REFERENCES, 4)

    @override_settings(DAILY_LOOK_RENDER_MAX_REFERENCES=4)
    def test_silhouette_survives_when_accessories_are_dropped(self) -> None:
        """자리가 모자라면 가방·액세서리를 버리고 옷을 남긴다.

        예전엔 payload 순서대로 앞에서 잘랐다. 그 순서엔 의미가 없어서 가방이
        남고 바지가 빠지면, 생성된 사진이 그 코디가 아니게 된다.
        """
        items = [
            {"s3_key": "a.png", "category_large": "가방", "item_name": "토트백"},
            {"s3_key": "b.png", "category_large": "액세서리", "item_name": "모자"},
            {"s3_key": "c.png", "category_large": "상의", "item_name": "셔츠"},
            {"s3_key": "d.png", "category_large": "하의", "item_name": "슬랙스"},
            {"s3_key": "e.png", "category_large": "신발", "item_name": "로퍼"},
            {"s3_key": "f.png", "category_large": "아우터", "item_name": "코트"},
        ]
        keys = _reference_keys(items)
        self.assertEqual(len(keys), 4)
        self.assertEqual(set(keys), {"c.png", "d.png", "e.png", "f.png"})
        # 전달 순서는 원래 순서를 지킨다 (모델에 주는 순서가 결과에 영향을 준다)
        self.assertEqual(keys, ["c.png", "d.png", "e.png", "f.png"])

    @override_settings(DAILY_LOOK_RENDER_MAX_REFERENCES=4)
    def test_selection_is_deterministic_for_ties(self) -> None:
        """같은 코디는 매번 같은 참조 조합이어야 한다 (착용 이미지는 재사용된다)."""
        items = [
            {"s3_key": f"{n}.png", "category_large": "액세서리"} for n in range(6)
        ]
        self.assertEqual(_reference_keys(items), _reference_keys(items))
        self.assertEqual(_reference_keys(items), ["0.png", "1.png", "2.png", "3.png"])

    @override_settings(DAILY_LOOK_RENDER_MAX_REFERENCES=4)
    def test_unknown_category_is_not_dropped_before_clothing(self) -> None:
        """분류가 비어도 옷일 수 있다. 가방·액세서리보다는 앞에 둔다."""
        items = [
            {"s3_key": "bag.png", "category_large": "가방"},
            {"s3_key": "acc.png", "category_large": "액세서리"},
            {"s3_key": "unknown.png"},
            {"s3_key": "top.png", "category_large": "상의"},
            {"s3_key": "bottom.png", "category_large": "하의"},
        ]
        keys = _reference_keys(items)
        self.assertIn("unknown.png", keys)
        self.assertNotIn("acc.png", keys)


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


class ImageApiResponseTests(unittest.TestCase):
    """OpenRouter 이미지 전용 API(POST /api/v1/images) 응답 형태.

    처음엔 채팅 API에 modalities=["image","text"]를 붙였다가 404를 받았다.
    "No endpoints found that support the requested output modalities" — 이미지
    생성은 별도 엔드포인트를 쓴다.
    """

    def test_data_b64_json(self) -> None:
        payload = {
            "created": 1748372400,
            "data": [{"b64_json": base64.b64encode(PNG).decode(), "media_type": "image/png"}],
            "usage": {"total_tokens": 4175, "cost": 0.04},
        }
        self.assertEqual(_extract_image(payload), PNG)

    def test_data_url_variant(self) -> None:
        self.assertEqual(_extract_image({"data": [{"url": DATA_URL}]}), PNG)

    def test_chat_shape_still_parsed(self) -> None:
        """모델을 바꾸면 채팅 형태로 오는 경우가 있어 둘 다 본다."""
        payload = {"choices": [{"message": {"images": [{"image_url": {"url": DATA_URL}}]}}]}
        self.assertEqual(_extract_image(payload), PNG)

    def test_empty_data_array(self) -> None:
        self.assertIsNone(_extract_image({"data": []}))

    def test_corrupt_b64_json(self) -> None:
        self.assertIsNone(_extract_image({"data": [{"b64_json": "@@@@"}]}))


class RequestShapeTests(TestCase):
    """요청이 이미지 API 규약대로 나가는지."""

    @patch("apps.recommend.services.outfit_render.storage.download_for", return_value=PNG)
    @patch("apps.recommend.services.outfit_render.requests.post")
    def test_uses_images_endpoint_with_input_references(self, post, _download):
        post.return_value = type("R", (), {
            "status_code": 200,
            "json": lambda self: {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
        })()
        outfit_render._generate(bucket=BUCKET, reference_keys=[ITEMS[0]["s3_key"]])

        url = post.call_args.args[0]
        body = post.call_args.kwargs["json"]
        self.assertTrue(url.endswith("/api/v1/images"), url)
        # 채팅 API 규약이 남아 있으면 다시 404가 난다
        self.assertNotIn("messages", body)
        self.assertNotIn("modalities", body)
        self.assertIn("prompt", body)
        self.assertEqual(len(body["input_references"]), 1)
        self.assertTrue(
            body["input_references"][0]["image_url"]["url"].startswith("data:image/png;base64,")
        )

    @patch("apps.recommend.services.outfit_render.storage.download_for", return_value=PNG)
    @patch("apps.recommend.services.outfit_render.requests.post")
    def test_http_error_body_is_kept_in_the_message(self, post, _download):
        """404의 실제 사유는 본문에만 담긴다. 삼키면 원인을 못 찾는다."""
        post.return_value = type("R", (), {
            "status_code": 404,
            "text": '{"error":{"message":"No endpoints found...","code":404}}',
            "json": lambda self: {},
        })()
        with self.assertRaises(RenderError) as ctx:
            outfit_render._generate(bucket=BUCKET, reference_keys=[ITEMS[0]["s3_key"]])
        self.assertIn("404", str(ctx.exception))
        self.assertIn("No endpoints found", str(ctx.exception))
