"""공식 Qwen Image Edit와 LightX2V Lightning을 제공하는 내부 VTON API."""

from __future__ import annotations

import base64
import binascii
import hmac
import io
import json
import logging
import math
import os
import shutil
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PIL import Image

import config

logger = logging.getLogger("vton_server")
HEALTH_PATH = "/health"
GENERATE_PATH = "/v1/virtual-try-on"


class VtonBusyError(RuntimeError):
    """GPU가 이미 다른 VTON 요청을 처리 중이다."""


def _lightning_scheduler_config() -> dict[str, Any]:
    """LightX2V의 공식 Diffusers 예제와 동일한 스케줄러 설정."""
    return {
        "base_image_seq_len": 256,
        "base_shift": math.log(3),
        "invert_sigmas": False,
        "max_image_seq_len": 8192,
        "max_shift": math.log(3),
        "num_train_timesteps": 1000,
        "shift": 1.0,
        "shift_terminal": None,
        "stochastic_sampling": False,
        "time_shift_type": "exponential",
        "use_beta_sigmas": False,
        "use_dynamic_shifting": True,
        "use_exponential_sigmas": False,
        "use_karras_sigmas": False,
    }


def _configure_offload(pipeline: Any, torch_module: Any) -> None:
    """공식 BF16 모델을 24GB GPU에서 실행하도록 CPU RAM과 VRAM에 분산한다."""
    if config.VTON_OFFLOAD_MODE == "group":
        pipeline.enable_group_offload(
            onload_device=torch_module.device(config.VTON_DEVICE),
            offload_device=torch_module.device("cpu"),
            offload_type="leaf_level",
            use_stream=True,
            record_stream=True,
        )
    elif config.VTON_OFFLOAD_MODE == "model":
        pipeline.enable_model_cpu_offload(device=config.VTON_DEVICE)
    elif config.VTON_OFFLOAD_MODE == "none":
        pipeline.to(config.VTON_DEVICE)
    else:
        raise ValueError("VTON_OFFLOAD_MODE must be one of: group, model, none")


def _cache_free_gb() -> float:
    cache_path = os.environ.get("HF_HOME", "/app/.cache/huggingface")
    os.makedirs(cache_path, exist_ok=True)
    return shutil.disk_usage(cache_path).free / (1024**3)


def _ensure_cache_space() -> None:
    free_gb = _cache_free_gb()
    if free_gb < config.VTON_MIN_FREE_DISK_GB:
        raise SystemExit(
            f"VTON cache disk is low: {free_gb:.1f} GiB free "
            f"(< {config.VTON_MIN_FREE_DISK_GB:.1f} GiB)"
        )


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
    """공식 Qwen 베이스에 LightX2V 4-step LoRA를 적용한다."""

    def __init__(self) -> None:
        import torch
        from diffusers import (
            FlowMatchEulerDiscreteScheduler,
            QwenImageEditPlusPipeline,
            QwenImageTransformer2DModel,
        )

        self.torch = torch
        # 단일 GPU 서비스이므로 요청을 직렬화한다. 수평 확장은 컨테이너 복제로 처리한다.
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

        logger.info(
            "VTON 모델 로딩 시작: base=%s, lightning=%s, offload=%s",
            config.VTON_MODEL,
            config.VTON_LIGHTNING_MODEL,
            config.VTON_OFFLOAD_MODE,
        )
        transformer = QwenImageTransformer2DModel.from_pretrained(
            config.VTON_MODEL,
            subfolder="transformer",
            torch_dtype=dtype,
        )
        scheduler = FlowMatchEulerDiscreteScheduler.from_config(
            _lightning_scheduler_config()
        )
        self.pipeline = QwenImageEditPlusPipeline.from_pretrained(
            config.VTON_MODEL,
            transformer=transformer,
            scheduler=scheduler,
            torch_dtype=dtype,
        )
        self.pipeline.load_lora_weights(
            config.VTON_LIGHTNING_MODEL,
            weight_name=config.VTON_LIGHTNING_WEIGHT,
        )
        self.pipeline.vae.enable_tiling()
        _configure_offload(self.pipeline, torch)
        logger.info("VTON 모델 로딩 완료")

    def generate(self, prompt: str, images: list[Image.Image]) -> bytes:
        if not self._lock.acquire(blocking=False):
            raise VtonBusyError
        try:
            generator = self.torch.Generator(device=config.VTON_DEVICE).manual_seed(
                config.VTON_SEED
            )
            with self.torch.inference_mode():
                result = self.pipeline(
                    image=images,
                    prompt=prompt,
                    negative_prompt=" ",
                    num_inference_steps=config.VTON_INFERENCE_STEPS,
                    true_cfg_scale=config.VTON_TRUE_CFG_SCALE,
                    guidance_scale=config.VTON_GUIDANCE_SCALE,
                    generator=generator,
                ).images[0]
        finally:
            self._lock.release()
        output = io.BytesIO()
        result.save(output, format="PNG")
        return output.getvalue()


class VtonRequestHandler(BaseHTTPRequestHandler):
    server_version = "SKN28VTON/1.0"

    def do_GET(self) -> None:
        if self.path != HEALTH_PATH:
            self._json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
            return
        free_gb = _cache_free_gb()
        healthy = free_gb >= config.VTON_MIN_FREE_DISK_GB
        self._json(
            HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE,
            {
                "status": "ok" if healthy else "disk_low",
                "model": config.VTON_MODEL,
                "accelerator": config.VTON_LIGHTNING_MODEL,
                "cache_free_gb": round(free_gb, 1),
            },
        )

    def do_POST(self) -> None:
        if self.path != GENERATE_PATH:
            self._json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
            return
        if not config.VTON_API_TOKEN:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"detail": "token is not configured"},
            )
            return
        if not _authorized(self.headers.get("Authorization")):
            self._json(HTTPStatus.UNAUTHORIZED, {"detail": "invalid bearer token"})
            return

        payload = self._read_json()
        if payload is None:
            return
        try:
            images = _decode_images(payload)
            image = self.server.editor.generate(  # type: ignore[attr-defined]
                payload["prompt"], images
            )
        except VtonBusyError:
            self.send_response(HTTPStatus.TOO_MANY_REQUESTS)
            self.send_header("Retry-After", "30")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
            return
        except Exception:
            logger.exception("가상 피팅 GPU 추론 실패")
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"detail": "inference failed"},
            )
            return

        self._json(
            HTTPStatus.OK,
            {
                "image_base64": base64.b64encode(image).decode("ascii"),
                "media_type": "image/png",
                "usage": {
                    "model": config.VTON_MODEL,
                    "accelerator": config.VTON_LIGHTNING_MODEL,
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
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            logger.info("HTTP client disconnected before receiving the response")

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("HTTP %s - %s", self.address_string(), format % args)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    if not config.VTON_API_TOKEN:
        raise SystemExit("VTON_GPU_TOKEN is required")
    _ensure_cache_space()
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
