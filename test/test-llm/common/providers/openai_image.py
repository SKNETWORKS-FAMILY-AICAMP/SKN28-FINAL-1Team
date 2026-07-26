"""GPT Image 2 (OpenAI images.edit).

기존 common/product_image_generator.py(gpt-image-1)와 같은 API를 쓰되
모델만 gpt-image-2로 교체한 형태.

moderation 대응:
- 사람이 찍힌 실사 사진 편집은 출력 단계(moderation_stage=output) 오탐이 잦다.
- images.edit의 moderation 파라미터는 공식 문서화가 불완전 → extra_body로
  시도하고, "unknown parameter"로 거부되면 없이 재호출한다.
- 출력 단계 차단은 확률적(같은 입력도 재생성 시 통과 가능) → 1회 자동 재시도.

환경변수:
  OPENAI_API_KEY          (필수)
  OPENAI_IMAGE_MODEL      (기본 gpt-image-2)
  OPENAI_IMAGE_SIZE       (기본 auto)
  OPENAI_IMAGE_MODERATION (기본 low, 빈 문자열이면 파라미터 미전송)
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
        self.moderation = os.getenv("OPENAI_IMAGE_MODERATION", "low")
        self._moderation_param_ok = True  # unknown parameter로 거부되면 False

    def edit(self, image_bytes: bytes, mime: str, prompt: str) -> bytes:
        last_err: Exception | None = None
        for _attempt in range(2):  # moderation_blocked(출력 단계)만 1회 재시도
            try:
                return self._call(image_bytes, mime, prompt)
            except Exception as e:
                if "moderation_blocked" not in str(e):
                    raise
                last_err = e
        raise last_err  # 재시도까지 차단되면 그대로 보고

    def _call(self, image_bytes: bytes, mime: str, prompt: str) -> bytes:
        ext = "png" if "png" in mime else "jpg"
        kwargs = dict(
            model=self.model,
            prompt=prompt,
            size=self.size,
        )
        if self.moderation and self._moderation_param_ok:
            try:
                result = self.client.images.edit(
                    image=(f"input.{ext}", io.BytesIO(image_bytes), mime),
                    extra_body={"moderation": self.moderation},
                    **kwargs,
                )
                return self._decode(result)
            except Exception as e:
                msg = str(e).lower()
                if "unknown parameter" in msg and "moderation" in msg:
                    self._moderation_param_ok = False  # 이후 호출부터 미전송
                else:
                    raise
        result = self.client.images.edit(
            image=(f"input.{ext}", io.BytesIO(image_bytes), mime),
            **kwargs,
        )
        return self._decode(result)

    @staticmethod
    def _decode(result) -> bytes:
        if not getattr(result, "data", None):
            raise RuntimeError("OpenAI 이미지 응답에 data가 없습니다.")
        b64 = getattr(result.data[0], "b64_json", None)
        if not b64:
            raise RuntimeError("OpenAI 응답에서 b64_json을 찾지 못했습니다.")
        return base64.b64decode(b64)
