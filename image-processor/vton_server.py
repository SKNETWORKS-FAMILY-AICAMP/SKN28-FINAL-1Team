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

from PIL import Image, ImageOps

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
    if not isinstance(encoded_images, list) or not 1 <= len(encoded_images) <= 6:
        raise ValueError("between one and six reference images are required")

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
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (OSError, ValueError) as exc:
            raise ValueError("invalid image") from exc
        images.append(image)
    return images


def _color_histogram(image: Image.Image) -> list[float]:
    """흰 배경을 제외한 저해상도 HSV 분포를 의류 색상 지문으로 쓴다."""
    histogram = [0] * 192
    resized = image.convert("HSV").resize((128, 128))
    pixels = (
        resized.get_flattened_data()
        if hasattr(resized, "get_flattened_data")
        else resized.getdata()
    )
    for hue, saturation, value in pixels:
        if saturation < 15 and value > 220:
            continue
        index = (
            (hue * 12 // 256) * 16
            + (saturation * 4 // 256) * 4
            + value * 4 // 256
        )
        histogram[index] += 1
    total = sum(histogram)
    return [count / total for count in histogram] if total else [0.0] * 192


def _garment_color_similarity(
    result: Image.Image,
    garments: list[Image.Image],
) -> float | None:
    if not garments:
        return None
    result_histogram = _color_histogram(result)
    garment_histograms = [_color_histogram(image) for image in garments]
    reference = [
        sum(values) / len(garment_histograms)
        for values in zip(*garment_histograms)
    ]
    return sum(
        min(expected, actual)
        for expected, actual in zip(reference, result_histogram)
    )


class QwenImageEditor:
    """한 파이프라인에서 기본 Qwen과 LightX2V 4-step을 전환한다."""

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
        lightning_scheduler = FlowMatchEulerDiscreteScheduler.from_config(
            _lightning_scheduler_config()
        )
        self.pipeline = QwenImageEditPlusPipeline.from_pretrained(
            config.VTON_MODEL,
            transformer=transformer,
            torch_dtype=dtype,
        )
        self.base_scheduler = self.pipeline.scheduler
        self.lightning_scheduler = lightning_scheduler
        self.pipeline.load_lora_weights(
            config.VTON_LIGHTNING_MODEL,
            weight_name=config.VTON_LIGHTNING_WEIGHT,
        )
        self.pipeline.vae.enable_tiling()
        _configure_offload(self.pipeline, torch)
        logger.info("VTON 모델 로딩 완료")

    def generate(
        self,
        prompt: str,
        images: list[Image.Image],
        *,
        profile: str = "fast",
        seed: int | None = None,
    ) -> tuple[bytes, float | None, int]:
        if not self._lock.acquire(blocking=False):
            raise VtonBusyError
        try:
            if profile == "quality":
                self.pipeline.disable_lora()
                self.pipeline.scheduler = self.base_scheduler
                steps = config.VTON_QUALITY_INFERENCE_STEPS
                true_cfg_scale = config.VTON_QUALITY_TRUE_CFG_SCALE
            elif profile == "fast":
                self.pipeline.enable_lora()
                self.pipeline.scheduler = self.lightning_scheduler
                steps = config.VTON_INFERENCE_STEPS
                true_cfg_scale = config.VTON_TRUE_CFG_SCALE
            else:
                raise ValueError("profile must be fast or quality")
            initial_seed = config.VTON_SEED if seed is None else seed
            max_attempts = 1 + (
                config.VTON_FIDELITY_RETRIES
                if profile == "quality" and len(images) > 1
                else 0
            )
            best_result = None
            best_score = None
            attempts = 0
            for offset in range(max_attempts):
                attempts += 1
                generator = self.torch.Generator(
                    device=config.VTON_DEVICE
                ).manual_seed(initial_seed + offset)
                with self.torch.inference_mode():
                    result = self.pipeline(
                        image=images,
                        prompt=prompt,
                        negative_prompt=config.VTON_NEGATIVE_PROMPT,
                        num_inference_steps=steps,
                        true_cfg_scale=true_cfg_scale,
                        guidance_scale=config.VTON_GUIDANCE_SCALE,
                        generator=generator,
                    ).images[0]
                score = _garment_color_similarity(result, images[1:])
                if best_score is None or (score is not None and score > best_score):
                    best_result, best_score = result, score
                if score is None or score >= config.VTON_FIDELITY_MIN_SCORE:
                    break
        finally:
            self._lock.release()
        output = io.BytesIO()
        best_result.save(output, format="PNG")
        return output.getvalue(), best_score, attempts


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
            profile = payload.get("profile", "fast")
            seed = payload.get("seed")
            if profile not in {"fast", "quality"}:
                raise ValueError("profile must be fast or quality")
            if seed is not None and (not isinstance(seed, int) or seed < 0):
                raise ValueError("seed must be a non-negative integer")
            image, fidelity_score, attempts = self.server.editor.generate(  # type: ignore[attr-defined]
                payload["prompt"], images, profile=profile, seed=seed
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
                    "profile": profile,
                    "accelerator": (
                        config.VTON_LIGHTNING_MODEL if profile == "fast" else ""
                    ),
                    "inference_steps": (
                        config.VTON_INFERENCE_STEPS
                        if profile == "fast"
                        else config.VTON_QUALITY_INFERENCE_STEPS
                    ),
                    "fidelity_score": (
                        round(fidelity_score, 4)
                        if fidelity_score is not None
                        else None
                    ),
                    "attempts": attempts,
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
