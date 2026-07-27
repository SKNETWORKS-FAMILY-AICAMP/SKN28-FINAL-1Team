"""OpenAI 동기 태거.

이미지 활용 모드 (NAVER_LLM_IMAGE_MODE):
- auto  : 텍스트만으로 1차 태깅 → style 또는 color 판단 실패 시 상품 이미지 포함 재시도
- always: 항상 이미지 포함
- never : 텍스트만
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple

from util.tagging.base import (
    MAX_RETRIES,
    TEMPERATURE,
    build_openai_messages,
    failed_meta,
    logger,
    merge_tags,
    openai_response_format,
    tagged_meta,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


class OpenAITagger:
    def __init__(self) -> None:
        if OpenAI is None:
            raise RuntimeError("openai 패키지가 없습니다. requirements를 설치하세요.")
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 없습니다. .env에 설정하세요.")
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.image_mode = os.getenv("NAVER_LLM_IMAGE_MODE", "auto").lower()

    # --------------------------------------------------------
    def tag(
        self,
        title: str,
        category_large: str,
        category_small: str,
        naver_categories: list,
        rule_attrs: Dict[str, Any],
        image_url: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        use_image_first = self.image_mode == "always" and bool(image_url)
        tags = self._call(title, category_large, category_small, naver_categories,
                          rule_attrs, image_url if use_image_first else None)
        used_image = use_image_first

        # auto 모드: 텍스트만으로 style/color 판단이 안 됐으면 이미지 포함 재시도
        if (
            not used_image
            and self.image_mode == "auto"
            and image_url
            and tags is not None
            and (not tags.get("style") or (not tags.get("color") and not rule_attrs.get("color")))
        ):
            logger.debug("이미지 포함 재태깅: %s", title[:50])
            retry = self._call(title, category_large, category_small, naver_categories,
                               rule_attrs, image_url)
            if retry is not None:
                tags = retry
                used_image = True

        if tags is None:
            return {}, failed_meta(self.model, used_image)

        merged, tag_source = merge_tags(rule_attrs, tags)
        return merged, tagged_meta(self.model, tag_source, used_image)

    # --------------------------------------------------------
    def _call(
        self,
        title: str,
        category_large: str,
        category_small: str,
        naver_categories: list,
        rule_attrs: Dict[str, Any],
        image_url: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        messages = build_openai_messages(
            title, category_large, category_small, naver_categories, rule_attrs, image_url
        )
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=TEMPERATURE,
                    messages=messages,
                    response_format=openai_response_format(),
                )
                return json.loads(response.choices[0].message.content)
            except Exception:  # noqa: BLE001
                logger.exception("OpenAI 태깅 실패 (attempt %s/%s): %s",
                                 attempt + 1, MAX_RETRIES + 1, title[:50])
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
        return None
