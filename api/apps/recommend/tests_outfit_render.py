from __future__ import annotations

import base64
from unittest.mock import Mock, call, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from apps.chat.models import ChatIdentity, ChatMessage, ChatRun, ChatSession
from apps.recommend.models import (
    OutfitComposition,
    OutfitCompositionItem,
    RecommendationResult,
)
from apps.recommend.services.outfit_render import (
    LoadedReferenceImage,
    OpenRouterQwenImageProvider,
    OutfitRenderRequest,
    OutfitRenderService,
    ReferenceImageError,
    ReferenceImageLoader,
    RenderDisabled,
    RenderInputError,
    RenderItemReference,
    RenderProviderError,
    RenderSource,
    _detect_media_type,
    _extract_generated_image,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"render-test-png"
JPEG = b"\xff\xd8\xff" + b"render-test-jpeg"
WEBP = b"RIFF\x10\x00\x00\x00WEBP" + b"render-test-webp"
FINGERPRINT = "a" * 64


def _item(
    *,
    position: int = 1,
    slot: str = "TOP",
    source_type: RenderSource = RenderSource.WARDROBE,
    image_ref: str = "items/top.png",
    source_bucket: str = "",
) -> RenderItemReference:
    return RenderItemReference(
        item_id=f"item-{position}",
        position=position,
        slot=slot,
        source_type=source_type,
        image_ref=image_ref,
        source_bucket=source_bucket,
    )


def _request(*items: RenderItemReference) -> OutfitRenderRequest:
    return OutfitRenderRequest(
        composition_id="composition-1",
        composition_fingerprint=FINGERPRINT,
        items=tuple(items),
    )


class ImagePayloadTests(SimpleTestCase):
    def test_detects_supported_image_types_from_bytes(self) -> None:
        self.assertEqual(_detect_media_type(PNG), "image/png")
        self.assertEqual(_detect_media_type(JPEG), "image/jpeg")
        self.assertEqual(_detect_media_type(WEBP), "image/webp")

    def test_rejects_non_image_bytes(self) -> None:
        with self.assertRaises(ReferenceImageError):
            _detect_media_type(b"not-an-image")

    def test_extracts_openrouter_and_chat_response_shapes(self) -> None:
        encoded = base64.b64encode(PNG).decode("ascii")
        self.assertEqual(
            _extract_generated_image({"data": [{"b64_json": encoded}]}), PNG
        )
        self.assertEqual(
            _extract_generated_image(
                {
                    "choices": [
                        {
                            "message": {
                                "images": [
                                    {
                                        "image_url": {
                                            "url": f"data:image/png;base64,{encoded}"
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ),
            PNG,
        )

    def test_corrupt_or_text_only_response_is_not_an_image(self) -> None:
        self.assertIsNone(
            _extract_generated_image({"data": [{"b64_json": "@@@@"}]})
        )
        self.assertIsNone(
            _extract_generated_image(
                {"choices": [{"message": {"content": "생성할 수 없습니다."}}]}
            )
        )


@override_settings(
    OUTFIT_RENDER_WARDROBE_BUCKET="wardrobe-bucket",
    OUTFIT_RENDER_PRODUCT_BUCKET="product-bucket",
    OUTFIT_RENDER_GOLDENSET_BUCKET="golden-bucket",
    OUTFIT_RENDER_MAX_REFERENCE_BYTES=1024,
    OUTFIT_RENDER_REFERENCE_TIMEOUT_SECONDS=3,
)
class ReferenceImageLoaderTests(SimpleTestCase):
    @patch(
        "apps.recommend.services.outfit_render.storage.download_for",
        side_effect=[PNG, JPEG, WEBP],
    )
    def test_resolves_each_source_to_its_own_default_bucket(self, download) -> None:
        loader = ReferenceImageLoader()

        wardrobe = loader.load(_item())
        product = loader.load(
            _item(
                position=2,
                slot="BOTTOM",
                source_type=RenderSource.PRODUCT,
                image_ref="products/bottom.jpg",
            )
        )
        golden = loader.load(
            _item(
                position=3,
                slot="SHOES",
                source_type=RenderSource.GOLDENSET_ITEM,
                image_ref="golden/shoes.webp",
            )
        )

        self.assertEqual(wardrobe.media_type, "image/png")
        self.assertEqual(product.media_type, "image/jpeg")
        self.assertEqual(golden.media_type, "image/webp")
        self.assertEqual(
            download.call_args_list,
            [
                call("wardrobe-bucket", "items/top.png", max_bytes=1024),
                call("product-bucket", "products/bottom.jpg", max_bytes=1024),
                call("golden-bucket", "golden/shoes.webp", max_bytes=1024),
            ],
        )

    @patch("apps.recommend.services.outfit_render.storage.download_for", return_value=PNG)
    def test_explicit_bucket_and_s3_uri_override_source_default(self, download) -> None:
        loader = ReferenceImageLoader()

        loader.load(_item(source_bucket="snapshot-bucket"))
        loader.load(
            _item(
                position=2,
                slot="BOTTOM",
                source_type=RenderSource.PRODUCT,
                image_ref="s3://archive-bucket/folder/item%202.png",
            )
        )

        self.assertEqual(
            download.call_args_list,
            [
                call("snapshot-bucket", "items/top.png", max_bytes=1024),
                call("archive-bucket", "folder/item 2.png", max_bytes=1024),
            ],
        )

    def test_loads_verified_https_image_without_following_redirects(self) -> None:
        response = Mock(
            status_code=200,
            headers={"Content-Length": str(len(PNG))},
        )
        response.iter_content.return_value = [PNG[:8], PNG[8:]]
        session = Mock()
        session.get.return_value = response

        loaded = ReferenceImageLoader(session=session).load(
            _item(
                source_type=RenderSource.PRODUCT,
                image_ref="https://cdn.example.com/items/top.png",
            )
        )

        self.assertEqual(loaded.content, PNG)
        session.get.assert_called_once_with(
            "https://cdn.example.com/items/top.png",
            stream=True,
            allow_redirects=False,
            timeout=3,
        )
        response.close.assert_called_once()

    def test_rejects_http_private_hosts_and_redirects(self) -> None:
        loader = ReferenceImageLoader(session=Mock())
        with self.assertRaises(ReferenceImageError):
            loader.load(_item(image_ref="http://cdn.example.com/item.png"))
        with self.assertRaises(ReferenceImageError):
            loader.load(_item(image_ref="https://127.0.0.1/item.png"))

        response = Mock(status_code=302, headers={})
        loader.session.get.return_value = response
        with self.assertRaises(ReferenceImageError):
            loader.load(_item(image_ref="https://cdn.example.com/redirect.png"))
        response.close.assert_called_once()

    @override_settings(OUTFIT_RENDER_PRODUCT_BUCKET="")
    def test_raw_s3_key_requires_a_source_bucket(self) -> None:
        with self.assertRaises(ReferenceImageError):
            ReferenceImageLoader().load(
                _item(source_type=RenderSource.PRODUCT, image_ref="products/item.jpg")
            )


@override_settings(
    OPENROUTER_API_KEY="test-openrouter-key",
    OUTFIT_RENDER_MODEL="qwen/qwen-image-3-pro",
    OUTFIT_RENDER_URL="https://openrouter.ai/api/v1/images",
    OUTFIT_RENDER_ASPECT_RATIO="9:16",
    OUTFIT_RENDER_RESOLUTION="1K",
    OUTFIT_RENDER_TIMEOUT_SECONDS=180,
)
class OpenRouterProviderTests(SimpleTestCase):
    def _references(self) -> tuple[LoadedReferenceImage, ...]:
        return (
            LoadedReferenceImage(_item(), PNG, "image/png"),
            LoadedReferenceImage(
                _item(
                    position=2,
                    slot="BOTTOM",
                    source_type=RenderSource.PRODUCT,
                    image_ref="product.jpg",
                ),
                JPEG,
                "image/jpeg",
            ),
        )

    def test_uses_image_endpoint_and_sends_all_mixed_references(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [{"b64_json": base64.b64encode(PNG).decode("ascii")}],
            "usage": {"cost": 0.04},
        }
        session = Mock()
        session.post.return_value = response

        content, media_type, usage = OpenRouterQwenImageProvider(
            session=session
        ).generate(prompt="render prompt", references=self._references())

        self.assertEqual(content, PNG)
        self.assertEqual(media_type, "image/png")
        self.assertEqual(usage, {"cost": 0.04})
        url = session.post.call_args.args[0]
        body = session.post.call_args.kwargs["json"]
        self.assertEqual(url, "https://openrouter.ai/api/v1/images")
        self.assertNotIn("messages", body)
        self.assertNotIn("modalities", body)
        self.assertEqual(len(body["input_references"]), 2)
        self.assertTrue(
            body["input_references"][0]["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
        )
        self.assertTrue(
            body["input_references"][1]["image_url"]["url"].startswith(
                "data:image/jpeg;base64,"
            )
        )
        response.close.assert_called_once()

    @override_settings(OPENROUTER_API_KEY="")
    def test_missing_api_key_fails_before_http_call(self) -> None:
        session = Mock()
        with self.assertRaises(RenderProviderError):
            OpenRouterQwenImageProvider(session=session).generate(
                prompt="prompt", references=self._references()
            )
        session.post.assert_not_called()

    def test_provider_error_preserves_status_and_short_body(self) -> None:
        response = Mock(
            status_code=404,
            text='{"error":{"message":"No endpoints found"}}',
        )
        session = Mock()
        session.post.return_value = response

        with self.assertRaises(RenderProviderError) as context:
            OpenRouterQwenImageProvider(session=session).generate(
                prompt="prompt", references=self._references()
            )

        self.assertIn("404", str(context.exception))
        self.assertIn("No endpoints found", str(context.exception))
        response.close.assert_called_once()

    @override_settings(OUTFIT_RENDER_MAX_OUTPUT_BYTES=8)
    def test_rejects_oversized_generated_image(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [{"b64_json": base64.b64encode(PNG).decode("ascii")}]
        }
        session = Mock()
        session.post.return_value = response

        with self.assertRaises(RenderProviderError):
            OpenRouterQwenImageProvider(session=session).generate(
                prompt="prompt", references=self._references()
            )

    def test_rejects_non_image_provider_payload(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "data": [
                {"b64_json": base64.b64encode(b"not-an-image").decode("ascii")}
            ]
        }
        session = Mock()
        session.post.return_value = response

        with self.assertRaises(RenderProviderError):
            OpenRouterQwenImageProvider(session=session).generate(
                prompt="prompt", references=self._references()
            )


class _StubLoader:
    def __init__(self, *, fail_position: int | None = None, size: int = len(PNG)) -> None:
        self.fail_position = fail_position
        self.size = size
        self.loaded: list[RenderItemReference] = []

    def load(self, item: RenderItemReference) -> LoadedReferenceImage:
        self.loaded.append(item)
        if item.position == self.fail_position:
            raise ReferenceImageError("reference failed")
        content = PNG if self.size == len(PNG) else b"\x89PNG\r\n\x1a\n" + b"x" * (self.size - 8)
        return LoadedReferenceImage(item, content, "image/png")


class _StubProvider:
    provider_name = "stub-provider"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[LoadedReferenceImage, ...]]] = []

    def generate(self, *, prompt: str, references: tuple[LoadedReferenceImage, ...]):
        self.calls.append((prompt, references))
        return PNG, "image/png", {"tokens": 12}


@override_settings(
    OUTFIT_RENDER_ENABLED=True,
    OUTFIT_RENDER_MODEL="qwen/qwen-image-3-pro",
    OUTFIT_RENDER_MAX_REFERENCES=8,
    OUTFIT_RENDER_MAX_TOTAL_REFERENCE_BYTES=4096,
)
class OutfitRenderServiceTests(SimpleTestCase):
    def test_renders_all_mixed_sources_in_position_order(self) -> None:
        items = (
            _item(),
            _item(
                position=2,
                slot="BOTTOM",
                source_type=RenderSource.PRODUCT,
                image_ref="product.jpg",
            ),
            _item(
                position=3,
                slot="SHOES",
                source_type=RenderSource.GOLDENSET_ITEM,
                image_ref="golden.png",
            ),
        )
        loader = _StubLoader()
        provider = _StubProvider()

        rendered = OutfitRenderService(loader=loader, provider=provider).render_request(
            _request(*items)
        )

        self.assertEqual(loader.loaded, list(items))
        self.assertEqual(rendered.reference_count, 3)
        self.assertEqual(rendered.provider, "stub-provider")
        self.assertEqual(rendered.model, "qwen/qwen-image-3-pro")
        prompt, references = provider.calls[0]
        self.assertEqual(len(references), 3)
        self.assertIn("slot=TOP, source=WARDROBE", prompt)
        self.assertIn("slot=BOTTOM, source=PRODUCT", prompt)
        self.assertIn("slot=SHOES, source=GOLDENSET_ITEM", prompt)

    def test_one_missing_reference_stops_generation_instead_of_omitting_item(self) -> None:
        provider = _StubProvider()
        service = OutfitRenderService(
            loader=_StubLoader(fail_position=2),
            provider=provider,
        )
        request = _request(
            _item(),
            _item(position=2, slot="BOTTOM", source_type=RenderSource.PRODUCT),
        )

        with self.assertRaises(ReferenceImageError):
            service.render_request(request)

        self.assertEqual(provider.calls, [])

    @override_settings(OUTFIT_RENDER_ENABLED=False)
    def test_disabled_service_does_not_load_images(self) -> None:
        loader = _StubLoader()
        with self.assertRaises(RenderDisabled):
            OutfitRenderService(loader=loader, provider=_StubProvider()).render_request(
                _request(_item())
            )
        self.assertEqual(loader.loaded, [])

    @override_settings(OUTFIT_RENDER_MAX_REFERENCES=2)
    def test_reference_count_is_rejected_without_truncation(self) -> None:
        with self.assertRaises(RenderInputError):
            OutfitRenderService(
                loader=_StubLoader(), provider=_StubProvider()
            ).render_request(
                _request(
                    _item(),
                    _item(position=2, slot="BOTTOM"),
                    _item(position=3, slot="SHOES"),
                )
            )

    @override_settings(OUTFIT_RENDER_MAX_TOTAL_REFERENCE_BYTES=20)
    def test_total_reference_bytes_are_limited_before_provider_call(self) -> None:
        provider = _StubProvider()
        with self.assertRaises(RenderInputError):
            OutfitRenderService(
                loader=_StubLoader(size=16), provider=provider
            ).render_request(
                _request(_item(), _item(position=2, slot="BOTTOM"))
            )
        self.assertEqual(provider.calls, [])

    def test_manual_request_validates_fingerprint_order_and_unique_slots(self) -> None:
        service = OutfitRenderService(loader=_StubLoader(), provider=_StubProvider())
        with self.assertRaises(RenderInputError):
            service.render_request(
                OutfitRenderRequest("composition", "not-a-hash", (_item(),))
            )
        with self.assertRaises(RenderInputError):
            service.render_request(
                _request(_item(position=2), _item(position=1, slot="BOTTOM"))
            )
        with self.assertRaises(RenderInputError):
            service.render_request(
                _request(_item(), _item(position=2, slot="TOP"))
            )


class PersistedCompositionRenderContractTests(TestCase):
    def setUp(self) -> None:
        user = get_user_model().objects.create_user(username="render-owner")
        identity = ChatIdentity.objects.create(
            identity_type=ChatIdentity.IdentityType.MEMBER,
            user=user,
        )
        session = ChatSession.objects.create(
            identity=identity,
            mode=ChatSession.Mode.NEW_ITEM,
        )
        message = ChatMessage.objects.create(
            session=session,
            sequence=1,
            role=ChatMessage.Role.USER,
            content="코디 추천",
        )
        run = ChatRun.objects.create(
            session=session,
            request_message=message,
            status=ChatRun.Status.SUCCEEDED,
        )
        result = RecommendationResult.objects.create(
            identity=identity,
            session=session,
            run=run,
            mode=RecommendationResult.Mode.NEW_ITEM,
            dataset_version="goldenset-v1",
        )
        self.composition = OutfitComposition.objects.create(
            result=result,
            rank=1,
            status=OutfitComposition.Status.VALIDATED,
            composition_fingerprint=FINGERPRINT,
        )
        # 저장 순서와 관계없이 position 순서로 렌더되어야 한다.
        OutfitCompositionItem.objects.create(
            composition=self.composition,
            position=2,
            slot="BOTTOM",
            source_type=OutfitCompositionItem.SourceType.PRODUCT,
            source_id="naver-2",
            source_collection="products_naver_v1",
            source_point_id="product-point-2",
            template_item_point_id="template-2",
            image_ref="https://cdn.example.com/bottom.jpg",
            item_snapshot={"image_bucket": "product-snapshot-bucket"},
        )
        OutfitCompositionItem.objects.create(
            composition=self.composition,
            position=1,
            slot="TOP",
            source_type=OutfitCompositionItem.SourceType.WARDROBE,
            source_id="wardrobe-1",
            source_collection="wardrobe_items",
            source_point_id="wardrobe-point-1",
            template_item_point_id="template-1",
            image_ref="wardrobe/1/top.png",
            item_snapshot={"s3_bucket": "wardrobe-snapshot-bucket"},
        )

    def test_build_request_preserves_mixed_source_and_snapshot_bucket(self) -> None:
        request = OutfitRenderService().build_request(self.composition)

        self.assertEqual([item.position for item in request.items], [1, 2])
        self.assertEqual(
            [item.source_type for item in request.items],
            [RenderSource.WARDROBE, RenderSource.PRODUCT],
        )
        self.assertEqual(request.items[0].source_bucket, "wardrobe-snapshot-bucket")
        self.assertEqual(request.items[1].source_bucket, "product-snapshot-bucket")

    def test_rejected_composition_is_not_renderable(self) -> None:
        self.composition.status = OutfitComposition.Status.REJECTED
        with self.assertRaises(RenderInputError):
            OutfitRenderService().build_request(self.composition)
