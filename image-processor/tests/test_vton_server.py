from __future__ import annotations

import base64
import io
import math
import threading
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from vton_server import (
    QwenImageEditor,
    VtonBusyError,
    _authorized,
    _decode_images,
    _ensure_cache_space,
    _configure_offload,
    _lightning_scheduler_config,
)


def image_base64() -> str:
    output = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


class VtonServerInputTests(unittest.TestCase):
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

    def test_rejects_missing_outfit_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly two"):
            _decode_images({"prompt": "dress", "images": [image_base64()]})

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

    @patch("vton_server.config.VTON_MIN_FREE_DISK_GB", 20)
    @patch("vton_server._cache_free_gb", return_value=10)
    def test_low_cache_disk_stops_startup(self, _free_gb) -> None:
        with self.assertRaisesRegex(SystemExit, "disk is low"):
            _ensure_cache_space()


if __name__ == "__main__":
    unittest.main()
