from __future__ import annotations

from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.recommend.checks import chat_recommend_deployment_checks
from apps.recommend.services.virtual_try_on import (
    DIRECT_PROMPT,
    GpuQwenImageProvider,
    MANNEQUIN_PROMPT,
    VirtualTryOnBusyError,
    VirtualTryOnService,
    body_profile_contract,
    load_body_profile,
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
        self.assertIn("featureless pure white", call["prompt"])
        self.assertIn("Do not redesign", call["prompt"])

    def test_mannequin_fit_adds_saved_body_constraints(self) -> None:
        body_profile = {
            "measurements": {"height": 168.0, "waist": 76.0, "hip": 96.0},
            "silhouette": "triangle",
        }

        self.service.fit_mannequin(PNG, PNG, body_profile=body_profile)

        prompt = self.provider.generate.call_args.kwargs["prompt"]
        self.assertIn('"height": 168.0', prompt)
        self.assertIn('"silhouette": "triangle"', prompt)
        self.assertIn("Do not print, label, or otherwise expose", prompt)

    def test_body_profile_change_changes_cache_contract(self) -> None:
        first = body_profile_contract({"measurements": {"waist": 76.0}})
        second = body_profile_contract({"measurements": {"waist": 82.0}})

        self.assertNotEqual(first, second)


class StoredBodyProfileTests(SimpleTestCase):
    @patch("apps.recommend.services.virtual_try_on.BodyMeasurement.objects.filter")
    def test_loads_existing_measurements_and_shape_classification(
        self,
        filter_mock: Mock,
    ) -> None:
        user = Mock(is_authenticated=True)
        measurement = Mock(
            gender="female",
            height=Decimal("168.0"),
            weight=Decimal("58.0"),
            chest=Decimal("92.0"),
            waist=Decimal("76.0"),
            hip=Decimal("98.0"),
            shoulder=Decimal("40.0"),
            torso_leg_ratio=Decimal("0.780"),
        )
        for field in ("thigh", "calf", "arm", "neck_length", "thigh_calf_ratio"):
            setattr(measurement, field, None)
        filter_mock.return_value.first.return_value = measurement

        profile = load_body_profile(user)

        filter_mock.assert_called_once_with(user=user)
        self.assertEqual(profile["measurements"]["waist"], 76.0)
        self.assertEqual(profile["measurements"]["torso_leg_ratio"], 0.78)
        self.assertEqual(profile["silhouette"], "triangle")

    @patch("apps.recommend.services.virtual_try_on.BodyMeasurement.objects.filter")
    def test_empty_measurement_keeps_existing_mannequin_behavior(
        self,
        filter_mock: Mock,
    ) -> None:
        user = Mock(is_authenticated=True)
        measurement = Mock(gender="")
        for field in (
            "height",
            "weight",
            "chest",
            "waist",
            "hip",
            "thigh",
            "calf",
            "arm",
            "shoulder",
            "neck_length",
            "thigh_calf_ratio",
            "torso_leg_ratio",
        ):
            setattr(measurement, field, None)
        filter_mock.return_value.first.return_value = measurement

        self.assertEqual(load_body_profile(user), {})


class VirtualTryOnCommandTests(SimpleTestCase):
    @patch(
        "apps.recommend.management.commands.test_virtual_try_on."
        "VirtualTryOnService"
    )
    @patch("apps.recommend.management.commands.test_virtual_try_on.load_body_profile")
    @patch("apps.recommend.management.commands.test_virtual_try_on.User.objects.get")
    def test_mannequin_uses_saved_body_profile(
        self,
        user_get: Mock,
        profile_loader: Mock,
        service_class: Mock,
    ) -> None:
        user_get.return_value = Mock(pk=2)
        profile = {"measurements": {"height": 168.0}}
        profile_loader.return_value = profile
        service_class.return_value.fit_mannequin.return_value = Mock(content=PNG)

        with TemporaryDirectory() as directory:
            person = Path(directory) / "person.jpg"
            outfit = Path(directory) / "outfit.jpg"
            output = Path(directory) / "result.png"
            person.write_bytes(PNG)
            outfit.write_bytes(PNG)

            call_command(
                "test_virtual_try_on",
                person=str(person),
                outfit=str(outfit),
                mode="mannequin",
                user_id=2,
                output=str(output),
                stdout=StringIO(),
            )

        profile_loader.assert_called_once_with(user_get.return_value)
        service_class.return_value.fit_mannequin.assert_called_once_with(
            PNG,
            PNG,
            body_profile=profile,
        )


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
