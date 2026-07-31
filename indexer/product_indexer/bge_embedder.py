"""BGE-M3 dense 텍스트 임베딩 래퍼.

safetensors 강제 로드 주의사항:
transformers 4.5x부터 `check_torch_load_is_safe()`가 `.bin`(pickle) 체크포인트를
읽을 때 torch>=2.6을 요구한다 (CVE-2025-32434). 베이스 이미지의 torch는 2.3.1이라
BAAI/bge-m3의 `pytorch_model.bin`을 고르는 순간 ValueError로 죽는다. 같은 저장소에
`model.safetensors`가 함께 있고 safetensors 경로에는 이 제한이 없으므로
`use_safetensors=True`로 로더가 항상 safetensors를 고르게 고정한다.
torch를 올리는 대신 이 방법을 쓰는 이유는 open_clip/marqo-fashionSigLIP과
numpy<2 핀이 torch 2.3 기준으로 맞춰져 있어 함께 검증해야 하기 때문이다.
"""

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
            # .bin(pickle) 대신 safetensors만 사용 — 위 docstring 참고.
            model_kwargs={"use_safetensors": True},
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
