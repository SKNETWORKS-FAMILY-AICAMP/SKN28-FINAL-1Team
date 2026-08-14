from __future__ import annotations

from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from apps.recommend.checks import chat_recommend_deployment_checks
from apps.recommend.services.virtual_try_on import (
    DIRECT_PROMPT,
    GpuQwenImageProvider,
    MANNEQUIN_PROMPT,
    VirtualTryOnBusyError,
    VirtualTryOnService,
)

PNG = b"\x89PNG\r\n\x1a\nimage"


class VirtualTryOnServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        self.provider = Mock()
        self.provider.generate.return_value = (PNG, "image/png", {})
        self.service = VirtualTryOnService(provider=self.provider)

    def test_direct_fit_keeps_person_first_and_outfit_second(self) -> None:
        self.service.fit_person(PNG, PNG)

        call = self.provider.generate.call_args.kwargs
        self.assertEqual(call["prompt"], DIRECT_PROMPT)
        self.assertEqual(
            [ref.item.slot for ref in call["references"]],
            ["target_person", "outfit"],
        )
        self.assertIn("Do not slim, enlarge, reshape", call["prompt"])

    def test_mannequin_fit_is_one_edit_without_base_clothes(self) -> None:
        self.service.fit_mannequin(PNG, PNG)

        call = self.provider.generate.call_args.kwargs
        self.assertEqual(call["prompt"], MANNEQUIN_PROMPT)
        self.assertEqual(
            [ref.item.slot for ref in call["references"]],
            ["target_person", "outfit"],
        )
        self.assertIn("Do not add a base outfit", call["prompt"])


@override_settings(
    VIRTUAL_TRY_ON_ENABLED=True,
    VTON_GPU_URL="http://gpu.example/v1/virtual-try-on",
    VTON_GPU_TOKEN="shared-secret",
    VTON_GPU_TIMEOUT_SECONDS=600,
    OUTFIT_RENDER_MAX_OUTPUT_BYTES=1024,
)
class GpuQwenImageProviderTests(SimpleTestCase):
    def test_sends_two_images_and_decodes_png(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "image_base64": "iVBORw0KGgppbWFnZQ==",
            "media_type": "image/png",
            "usage": {"model": "Qwen/Qwen-Image-Edit-2511"},
        }
        session = Mock()
        session.post.return_value = response
        service = VirtualTryOnService(provider=GpuQwenImageProvider(session=session))

        result = service.fit_mannequin(PNG, PNG)

        request = session.post.call_args
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer shared-secret")
        self.assertEqual(len(request.kwargs["json"]["images"]), 2)
        self.assertEqual(request.kwargs["timeout"], 600)
        self.assertEqual(result.media_type, "image/png")
        self.assertEqual(result.usage["model"], "Qwen/Qwen-Image-Edit-2511")
        response.close.assert_called_once()

    def test_busy_gpu_is_reported_separately(self) -> None:
        response = Mock(status_code=429, text="")
        session = Mock()
        session.post.return_value = response
        provider = GpuQwenImageProvider(session=session)

        with self.assertRaises(VirtualTryOnBusyError):
            provider.generate(prompt="fit", references=())

        response.close.assert_called_once()


class VirtualTryOnDeploymentCheckTests(SimpleTestCase):
    @override_settings(
        OUTFIT_RENDER_ENABLED=True,
        VIRTUAL_TRY_ON_ENABLED=False,
        OPENROUTER_API_KEY="key",
        OUTFIT_RENDER_RESULT_BUCKET="bucket",
        VTON_GPU_URL="",
        VTON_GPU_TOKEN="",
    )
    def test_outfit_render_does_not_require_vton_settings(self) -> None:
        error_ids = {
            error.id for error in chat_recommend_deployment_checks(None)
        }

        self.assertNotIn("recommend.E008", error_ids)
        self.assertNotIn("recommend.E009", error_ids)

    @override_settings(
        OUTFIT_RENDER_ENABLED=False,
        VIRTUAL_TRY_ON_ENABLED=True,
        VTON_GPU_URL="",
        VTON_GPU_TOKEN="",
        OUTFIT_RENDER_RESULT_BUCKET="",
    )
    def test_enabled_vton_requires_its_own_settings(self) -> None:
        error_ids = {
            error.id for error in chat_recommend_deployment_checks(None)
        }

        self.assertTrue(
            {"recommend.E008", "recommend.E009", "recommend.E010"}.issubset(error_ids)
        )
