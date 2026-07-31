"""BGE-M3 dense 텍스트 임베딩 래퍼."""

from __future__ import annotations

import logging

import numpy as np
import torch

logger = logging.getLogger(__name__)


class BgeM3Embedder:
    def __init__(
        self,
        model_id: str,
        *,
        revision: str | None = None,
        device: str = "auto",
        max_length: int = 512,
    ):
        from sentence_transformers import SentenceTransformer

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(
            "BGE-M3 모델 로드: %s (revision=%s, device=%s)",
            model_id,
            revision or "default",
            device,
        )
        self.model = SentenceTransformer(
            model_id,
            revision=revision,
            device=device,
        )
        self.model.max_seq_length = max_length
        dimension = self.model.get_sentence_embedding_dimension()
        if dimension is None:
            probe = self.model.encode(["dimension probe"])
            dimension = int(probe.shape[-1])
        self.dim = int(dimension)

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            batch_size=max(1, len(texts)),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)
