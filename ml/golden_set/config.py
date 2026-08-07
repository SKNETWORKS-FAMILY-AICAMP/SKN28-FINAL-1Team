"""환경변수 기반 골든셋 파일럿 설정."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_project_env() -> None:
    """루트 .env를 기존 프로세스 환경보다 낮은 우선순위로 읽는다."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    explicit = os.getenv("ENV_FILE")
    path = Path(explicit) if explicit else Path(__file__).resolve().parents[2] / ".env"
    if path.exists():
        load_dotenv(path, override=False)


@dataclass(frozen=True)
class GoldenSettings:
    gemini_api_key: str
    gemini_api_base_url: str
    gemini_model: str
    gemini_timeout_seconds: int
    fashion_model_id: str
    text_model_id: str
    device: str
    embedding_batch_size: int
    max_multimodal_calls: int

    @classmethod
    def from_env(cls) -> GoldenSettings:
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_api_base_url=os.getenv(
                "GEMINI_API_BASE_URL",
                "https://generativelanguage.googleapis.com",
            ).rstrip("/"),
            gemini_model=os.getenv("GOLDEN_GEMINI_MODEL")
            or os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
            gemini_timeout_seconds=int(
                os.getenv("GOLDEN_GEMINI_TIMEOUT_SECONDS", "90")
            ),
            fashion_model_id=os.getenv("GOLDEN_FASHION_EMBED_MODEL")
            or os.getenv("FASHION_EMBED_MODEL", "hf-hub:Marqo/marqo-fashionSigLIP"),
            text_model_id=os.getenv("GOLDEN_TEXT_EMBED_MODEL")
            or os.getenv("TEXT_EMBED_MODEL", "BAAI/bge-m3"),
            device=os.getenv("GOLDEN_DEVICE", "auto"),
            embedding_batch_size=int(os.getenv("GOLDEN_EMBED_BATCH_SIZE", "16")),
            max_multimodal_calls=int(os.getenv("GOLDEN_MAX_MULTIMODAL_CALLS", "15")),
        )
