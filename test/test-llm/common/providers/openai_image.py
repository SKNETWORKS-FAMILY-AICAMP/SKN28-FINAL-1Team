"""GPT Image 2 (OpenAI images.edit).

기존 common/product_image_generator.py(gpt-image-1)와 같은 API를 쓰되
모델만 gpt-image-2로 교체한 형태.

환경변수:
  OPENAI_API_KEY     (필수)
  OPENAI_IMAGE_MODEL (기본 gpt-image-2)
  OPENAI_IMAGE_SIZE  (기본 auto)
"""
from __future__ import annotations

import base64
import io
import os

from .base import ImageEditProvider


class GptImageProvider(ImageEditProvider):
    key = "gpt-image-2"
    required_env = "OPENAI_API_KEY"

    def __init__(self) -> None:
        from openai import OpenAI  # 지연 import

        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
        self.size = os.getenv("OPENAI_IMAGE_SIZE", "auto")

    def edit(self, image_bytes: bytes, mime: str, prompt: str) -> bytes:
        ext = "png" if "png" in mime else "jpg"
        result = self.client.images.edit(
            model=self.model,
            image=(f"input.{ext}", io.BytesIO(image_bytes), mime),
            prompt=prompt,
            size=self.size,
        )
        if not getattr(result, "data", None):
            raise RuntimeError("OpenAI 이미지 응답에 data가 없습니다.")
        item = result.data[0]
        b64 = getattr(item, "b64_json", None)
        if not b64:
            raise RuntimeError("OpenAI 응답에서 b64_json을 찾지 못했습니다.")
        return base64.b64decode(b64)
