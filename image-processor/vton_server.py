"""Qwen-Image-Edit-2511을 제공하는 GPU 내부 가상 피팅 API."""

from __future__ import annotations

import base64
import binascii
import hmac
import io
import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PIL import Image

import config

logger = logging.getLogger("vton_server")
HEALTH_PATH = "/health"
GENERATE_PATH = "/v1/virtual-try-on"


def _authorized(header: str | None) -> bool:
    if not config.VTON_API_TOKEN or not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header[7:].strip(), config.VTON_API_TOKEN)


def _decode_images(payload: dict[str, Any]) -> list[Image.Image]:
    prompt = payload.get("prompt")
    encoded_images = payload.get("images")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8_000:
        raise ValueError("prompt is required")
    if not isinstance(encoded_images, list) or len(encoded_images) != 2:
        raise ValueError("exactly two reference images are required")

    images: list[Image.Image] = []
    for encoded in encoded_images:
        if not isinstance(encoded, str):
            raise ValueError("image must be base64 text")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("invalid base64 image") from exc
        if not content or len(content) > config.VTON_MAX_IMAGE_BYTES:
            raise ValueError("invalid image size")
        try:
            with Image.open(io.BytesIO(content)) as source:
                if source.width * source.height > config.VTON_MAX_IMAGE_PIXELS:
                    raise ValueError("image dimensions are too large")
                source.load()
                image = source.convert("RGB")
        except (OSError, ValueError) as exc:
            raise ValueError("invalid image") from exc
        images.append(image)
    return images


class QwenImageEditor:
    """모델을 한 번만 적재하고 GPU 추론은 직렬화한다."""

    def __init__(self) -> None:
        import torch
        from diffusers import QwenImageEditPlusPipeline
        from diffusers.quantizers import PipelineQuantizationConfig

        self.torch = torch
        # ponytail: GPU 한 장에서는 직렬 추론이 가장 안전하다. 다중 GPU가 생기면 worker를 복제한다.
        self._lock = threading.Lock()
        dtype = {
            "bf16": torch.bfloat16,
            "fp16": torch.float16,
            "fp32": torch.float32,
        }.get(config.VTON_DTYPE)
        if dtype is None:
            if not config.VTON_DEVICE.startswith("cuda"):
                dtype = torch.float32
            elif torch.cuda.is_bf16_supported():
                dtype = torch.bfloat16
            else:
                dtype = torch.float16
        logger.info("VTON 모델 NF4 4비트 로딩 시작: %s", config.VTON_MODEL)
        quantization_config = PipelineQuantizationConfig(
            quant_backend="bitsandbytes_4bit",
            quant_kwargs={
                "load_in_4bit": True,
                "bnb_4bit_quant_type": "nf4",
                "bnb_4bit_compute_dtype": dtype,
                "bnb_4bit_use_double_quant": True,
            },
            components_to_quantize=["transformer", "text_encoder"],
        )
        self.pipeline = QwenImageEditPlusPipeline.from_pretrained(
            config.VTON_MODEL,
            torch_dtype=dtype,
            quantization_config=quantization_config,
            device_map="cuda",
        )
        if config.VTON_CPU_OFFLOAD:
            self.pipeline.enable_model_cpu_offload()
        logger.info("VTON 모델 로딩 완료")

    def generate(self, prompt: str, images: list[Image.Image]) -> bytes:
        generator = self.torch.Generator(device=config.VTON_DEVICE).manual_seed(
            config.VTON_SEED
        )
        with self._lock, self.torch.inference_mode():
            result = self.pipeline(
                image=images,
                prompt=prompt,
                negative_prompt=" ",
                num_inference_steps=config.VTON_INFERENCE_STEPS,
                true_cfg_scale=config.VTON_TRUE_CFG_SCALE,
                guidance_scale=1.0,
                generator=generator,
            ).images[0]
        output = io.BytesIO()
        result.save(output, format="PNG")
        return output.getvalue()


class VtonRequestHandler(BaseHTTPRequestHandler):
    server_version = "SKN28VTON/1.0"

    def do_GET(self) -> None:
        if self.path != HEALTH_PATH:
            self._json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
            return
        self._json(HTTPStatus.OK, {"status": "ok", "model": config.VTON_MODEL})

    def do_POST(self) -> None:
        if self.path != GENERATE_PATH:
            self._json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
            return
        if not config.VTON_API_TOKEN:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"detail": "token is not configured"})
            return
        if not _authorized(self.headers.get("Authorization")):
            self._json(HTTPStatus.UNAUTHORIZED, {"detail": "invalid bearer token"})
            return

        payload = self._read_json()
        if payload is None:
            return
        try:
            images = _decode_images(payload)
            image = self.server.editor.generate(payload["prompt"], images)  # type: ignore[attr-defined]
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
            return
        except Exception:
            logger.exception("가상 피팅 GPU 추론 실패")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"detail": "inference failed"})
            return

        self._json(
            HTTPStatus.OK,
            {
                "image_base64": base64.b64encode(image).decode("ascii"),
                "media_type": "image/png",
                "usage": {
                    "model": config.VTON_MODEL,
                    "inference_steps": config.VTON_INFERENCE_STEPS,
                },
            },
        )

    def _read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 1 or length > config.VTON_MAX_REQUEST_BYTES:
            self._json(HTTPStatus.BAD_REQUEST, {"detail": "invalid request size"})
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"detail": "invalid JSON"})
            return None
        if not isinstance(payload, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"detail": "JSON object required"})
            return None
        return payload

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("HTTP %s - %s", self.address_string(), format % args)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if not config.VTON_API_TOKEN:
        raise SystemExit("VTON_GPU_TOKEN is required")
    server = ThreadingHTTPServer(
        (config.VTON_API_HOST, config.VTON_API_PORT),
        VtonRequestHandler,
    )
    server.editor = QwenImageEditor()  # type: ignore[attr-defined]
    logger.info("VTON GPU API 시작: %s:%s", config.VTON_API_HOST, config.VTON_API_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
