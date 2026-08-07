"""골든셋 이미지·텍스트 임베딩 백엔드."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

from .artifacts import read_jsonl, write_json
from .config import GoldenSettings


class ImageEmbeddingBackend(Protocol):
    name: str
    dim: int

    def encode_paths(self, paths: list[Path]) -> np.ndarray: ...


class TextEmbeddingBackend(Protocol):
    name: str
    dim: int

    def encode_texts(self, texts: list[str]) -> np.ndarray: ...


class FashionSigLIPBackend:
    """기존 indexer의 FashionSigLIP 설정과 동일한 오프라인 배치 백엔드."""

    def __init__(self, model_id: str, device: str = "auto") -> None:
        import open_clip
        import torch

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._torch = torch
        self._device = device
        self._device_type = torch.device(device).type
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            model_id
        )
        self._model = self._model.to(device).eval()
        self.name = model_id
        # 실제 차원은 첫 배치에서 확정한다.
        self.dim = 0

    def encode_paths(self, paths: list[Path]) -> np.ndarray:
        if not paths:
            return np.empty((0, self.dim), dtype=np.float32)
        images = []
        for path in paths:
            with Image.open(path) as image:
                images.append(self._preprocess(image.convert("RGB")))
        batch = self._torch.stack(images).to(self._device)
        with (
            self._torch.no_grad(),
            self._torch.autocast(
                self._device_type,
                enabled=self._device_type == "cuda",
            ),
        ):
            values = self._model.encode_image(batch)
        values = values / values.norm(dim=-1, keepdim=True)
        result = values.float().cpu().numpy()
        self.dim = int(result.shape[1])
        return result


class BgeM3Backend:
    def __init__(self, model_id: str, device: str = "auto") -> None:
        from sentence_transformers import SentenceTransformer

        kwargs = {} if device == "auto" else {"device": device}
        self._model = SentenceTransformer(model_id, **kwargs)
        self.name = model_id
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)
        return np.asarray(
            self._model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )


class DeterministicImageBackend:
    """네트워크·GPU 없는 테스트와 파이프라인 dry-run용 백엔드."""

    name = "deterministic-test-image-v1"

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim

    def encode_paths(self, paths: list[Path]) -> np.ndarray:
        rows = []
        for path in paths:
            digest = hashlib.sha256(path.read_bytes()).digest()
            seed = int.from_bytes(digest[:8], "big", signed=False)
            rng = np.random.default_rng(seed)
            vector = rng.normal(size=self.dim).astype(np.float32)
            rows.append(vector / np.linalg.norm(vector))
        return np.vstack(rows) if rows else np.empty((0, self.dim), dtype=np.float32)


class DeterministicTextBackend:
    name = "deterministic-test-text-v1"

    def __init__(self, dim: int = 48) -> None:
        self.dim = dim

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for value in texts:
            digest = hashlib.sha256(value.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big", signed=False)
            rng = np.random.default_rng(seed)
            vector = rng.normal(size=self.dim).astype(np.float32)
            rows.append(vector / np.linalg.norm(vector))
        return np.vstack(rows) if rows else np.empty((0, self.dim), dtype=np.float32)


def embed_manifest_images(
    *,
    run_dir: Path,
    settings: GoldenSettings,
    backend_name: str = "fashion",
) -> tuple[list[str], np.ndarray, str]:
    images = [
        row
        for row in read_jsonl(run_dir / "images.jsonl")
        if row.get("duplicate_kind") != "exact"
    ]
    if backend_name == "deterministic":
        backend: ImageEmbeddingBackend = DeterministicImageBackend()
    elif backend_name == "fashion":
        backend = FashionSigLIPBackend(settings.fashion_model_id, settings.device)
    else:
        raise ValueError(f"지원하지 않는 이미지 임베딩 백엔드: {backend_name}")

    ids: list[str] = []
    chunks: list[np.ndarray] = []
    batch_size = max(1, settings.embedding_batch_size)
    for start in range(0, len(images), batch_size):
        batch = images[start : start + batch_size]
        ids.extend(str(row["golden_id"]) for row in batch)
        chunks.append(
            backend.encode_paths([Path(str(row["local_path"])) for row in batch])
        )
    vectors = np.vstack(chunks).astype(np.float32)
    np.savez_compressed(
        run_dir / "image_embeddings.npz",
        ids=np.asarray(ids),
        vectors=vectors,
    )
    write_json(
        run_dir / "image_embeddings.meta.json",
        {"model": backend.name, "dim": int(vectors.shape[1]), "count": len(ids)},
    )
    return ids, vectors, backend.name


def load_embeddings(path: Path) -> tuple[list[str], np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        ids = [str(value) for value in data["ids"].tolist()]
        vectors = np.asarray(data["vectors"], dtype=np.float32)
    return ids, vectors
