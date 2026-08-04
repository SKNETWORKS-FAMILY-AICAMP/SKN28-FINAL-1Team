"""파이프라인 조립(factory).

WardrobePipeline은 4개 컴포넌트(열거·생성·태깅·임베딩)의 컴포지션이다.
구현 교체는 이 파일의 레지스트리에 새 빌더를 등록하고
WORKER_PIPELINE 환경변수로 선택하면 된다. 예:
  "gemini-edit" : test-llm2 로직 (열거·편집·태깅 모두 Gemini)  ← 기본
  "sam3-crop"   : (예정) SAM3 세그멘테이션 크롭 + Gemini 태깅
"""
from __future__ import annotations

import logging
import time

import config

from .base import (  # noqa: F401 — 패키지 공개 API
    Embedder,
    EnumeratedItem,
    ItemEnumerator,
    ItemTagger,
    ProcessedItem,
    ProductImageGenerator,
)
from .embedding import NullEmbedder, SigLIPBgeEmbedder, caption_from_tags
from .taxonomy import missing_required

logger = logging.getLogger(__name__)


class WardrobePipeline:
    """원본 사진 1장 → ProcessedItem 목록.

    아이템 단위 실패는 error에 기록하고 계속 진행한다 — 부분 성공 허용.
    """

    def __init__(
        self,
        enumerator: ItemEnumerator,
        generator: ProductImageGenerator,
        tagger: ItemTagger,
        embedder: Embedder | None,
    ) -> None:
        self.enumerator = enumerator
        self.generator = generator
        self.tagger = tagger
        self.embedder = embedder

    @property
    def key(self) -> str:
        return self.generator.key

    def process(self, image_bytes: bytes, mime: str) -> list[ProcessedItem]:
        t0 = time.perf_counter()
        enumerated = self.enumerator.enumerate(image_bytes, mime)
        enum_sec = round(time.perf_counter() - t0, 3)
        logger.info("열거 완료: %d개 아이템 (%.1fs)", len(enumerated), enum_sec)

        results: list[ProcessedItem] = []
        for i, enum_item in enumerate(enumerated):
            item = ProcessedItem(index=i, enum=enum_item,
                                 timings={"enumerate": enum_sec})
            try:
                t = time.perf_counter()
                item.image_png = self.generator.generate(image_bytes, mime, enum_item)
                item.timings["generate"] = round(time.perf_counter() - t, 3)

                t = time.perf_counter()
                item.tags = self.tagger.tag(item.image_png)
                item.timings["tag"] = round(time.perf_counter() - t, 3)

                if self.embedder is not None:
                    t = time.perf_counter()
                    item.image_vector = self.embedder.embed_image(item.image_png)
                    item.text_vector = self.embedder.embed_text(
                        caption_from_tags(item.tags)
                    )
                    item.timings["embed"] = round(time.perf_counter() - t, 3)

                item.tags["_missing_required"] = missing_required(item.tags)
            # 한 아이템의 실패가 나머지 아이템 처리를 막지 않게 격리한다.
            except Exception as e:
                logger.exception("아이템 %d(%s) 처리 실패", i, enum_item.label_ko)
                item.error = f"{type(e).__name__}: {e}"
            results.append(item)
        return results


# ── factory ──────────────────────────────────────────────
def _build_gemini_edit_with(embedder: Embedder | None) -> WardrobePipeline:
    from .gemini.editor import GeminiImageEditor
    from .gemini.enumerator import GeminiEnumerator
    from .gemini.tagger import GeminiTagger

    return WardrobePipeline(
        enumerator=GeminiEnumerator(),
        generator=GeminiImageEditor(),
        tagger=GeminiTagger(),
        embedder=embedder,
    )


def _build_gemini_edit() -> WardrobePipeline:
    embedder: Embedder = (
        SigLIPBgeEmbedder() if config.EMBED_ENABLED else NullEmbedder()
    )
    return _build_gemini_edit_with(embedder)


# 새 구현은 여기 등록: {"sam3-crop": _build_sam3_crop, ...}
_REGISTRY = {
    "gemini-edit": _build_gemini_edit,
}


def build_pipeline(name: str | None = None) -> WardrobePipeline:
    key = name or config.PIPELINE_IMPL
    if key not in _REGISTRY:
        raise ValueError(
            f"알 수 없는 파이프라인: {key!r} (등록된 구현: {sorted(_REGISTRY)})"
        )
    return _REGISTRY[key]()


def build_calendar_pipeline(name: str | None = None) -> WardrobePipeline:
    """임베딩을 구성하거나 호출하지 않는 캘린더 이미지 파이프라인."""

    key = name or config.PIPELINE_IMPL
    if key != "gemini-edit":
        raise ValueError(
            f"알 수 없는 캘린더 파이프라인: {key!r} "
            "(등록된 구현: ['gemini-edit'])"
        )
    return _build_gemini_edit_with(embedder=None)
