from __future__ import annotations

import base64
import io
import math
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

from PIL import Image

from vton_server import (
    QwenImageEditor,
    VtonBusyError,
    _authorized,
    _decode_images,
    _ensure_cache_space,
    _configure_offload,
    _garment_color_similarity,
    _lightning_scheduler_config,
)


def image_base64() -> str:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def rotated_jpeg_base64() -> str:
    output = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (4, 2), "white").save(output, format="JPEG", exif=exif)
    return base64.b64encode(output.getvalue()).decode("ascii")


class VtonServerInputTests(unittest.TestCase):
    def test_garment_color_similarity_prefers_same_color(self) -> None:
        navy = Image.new("RGB", (32, 32), (10, 20, 80))
        red = Image.new("RGB", (32, 32), (180, 20, 20))

        same = _garment_color_similarity(navy, [navy])
        different = _garment_color_similarity(red, [navy])

        self.assertGreater(same, different)

    def test_lightning_scheduler_matches_distilled_model(self) -> None:
        scheduler = _lightning_scheduler_config()

        self.assertEqual(scheduler["base_shift"], math.log(3))
        self.assertEqual(scheduler["max_shift"], math.log(3))
        self.assertTrue(scheduler["use_dynamic_shifting"])
        self.assertFalse(scheduler["stochastic_sampling"])

    @patch("vton_server.config.VTON_OFFLOAD_MODE", "group")
    def test_group_offload_targets_cpu_and_configured_gpu(self) -> None:
        pipeline = Mock()
        torch_module = Mock()
        torch_module.device.side_effect = lambda value: value

        _configure_offload(pipeline, torch_module)

        pipeline.enable_group_offload.assert_called_once_with(
            onload_device="cuda",
            offload_device="cpu",
            offload_type="leaf_level",
            use_stream=True,
            record_stream=True,
        )

    @patch("vton_server.config.VTON_API_TOKEN", "shared-secret")
    def test_bearer_token_is_required(self) -> None:
        self.assertTrue(_authorized("Bearer shared-secret"))
        self.assertFalse(_authorized("Bearer wrong"))
        self.assertFalse(_authorized(None))

    def test_two_reference_images_are_decoded(self) -> None:
        images = _decode_images(
            {"prompt": "dress the mannequin", "images": [image_base64(), image_base64()]}
        )

        self.assertEqual(len(images), 2)
        self.assertTrue(all(image.mode == "RGB" for image in images))

    def test_applies_jpeg_exif_orientation(self) -> None:
        images = _decode_images(
            {"prompt": "build mannequin", "images": [rotated_jpeg_base64()]}
        )

        self.assertEqual(images[0].size, (2, 4))

    def test_rejects_missing_outfit_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "between one and six"):
            _decode_images({"prompt": "dress", "images": []})

    def test_accepts_single_body_reference_for_mannequin_base(self) -> None:
        images = _decode_images({"prompt": "build mannequin", "images": [image_base64()]})

        self.assertEqual(len(images), 1)

    def test_accepts_individual_garment_references(self) -> None:
        images = _decode_images(
            {"prompt": "dress", "images": [image_base64()] * 4}
        )

        self.assertEqual(len(images), 4)

    @patch("vton_server.config.VTON_MAX_IMAGE_PIXELS", 1)
    def test_rejects_excessive_image_dimensions(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid image"):
            _decode_images(
                {"prompt": "dress", "images": [image_base64(), image_base64()]}
            )

    def test_busy_editor_rejects_without_waiting(self) -> None:
        editor = QwenImageEditor.__new__(QwenImageEditor)
        editor._lock = threading.Lock()
        editor._lock.acquire()

        with self.assertRaises(VtonBusyError):
            editor.generate("fit", [])

    @patch("vton_server.config.VTON_FIDELITY_RETRIES", 0)
    @patch("vton_server.config.VTON_QUALITY_INFERENCE_STEPS", 30)
    @patch("vton_server.config.VTON_QUALITY_TRUE_CFG_SCALE", 4.0)
    def test_quality_profile_disables_lightning_lora(self) -> None:
        editor = QwenImageEditor.__new__(QwenImageEditor)
        editor._lock = threading.Lock()
        editor.torch = MagicMock()
        editor.torch.Generator.return_value.manual_seed.return_value = Mock()
        editor.pipeline = Mock()
        editor.pipeline.return_value.images = [Image.new("RGB", (2, 2), "navy")]
        editor.base_scheduler = Mock()
        editor.lightning_scheduler = Mock()

        _image, _score, attempts = editor.generate(
            "fit", [Image.new("RGB", (2, 2), "white")], profile="quality"
        )

        editor.pipeline.disable_lora.assert_called_once_with()
        self.assertIs(editor.pipeline.scheduler, editor.base_scheduler)
        self.assertEqual(editor.pipeline.call_args.kwargs["num_inference_steps"], 30)
        self.assertEqual(editor.pipeline.call_args.kwargs["true_cfg_scale"], 4.0)
        self.assertEqual(attempts, 1)

    @patch("vton_server.config.VTON_MIN_FREE_DISK_GB", 20)
    @patch("vton_server._cache_free_gb", return_value=10)
    def test_low_cache_disk_stops_startup(self, _free_gb) -> None:
        with self.assertRaisesRegex(SystemExit, "disk is low"):
            _ensure_cache_space()


if __name__ == "__main__":
    unittest.main()
