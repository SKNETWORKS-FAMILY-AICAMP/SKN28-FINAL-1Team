"""image-processor 설정.

모든 값은 루트 .env / 환경변수에서 읽는다 (하드코딩 금지 — CLAUDE.md 규칙).
참조 문서:
- Confluence > 설계 > "옷장 이미지 파이프라인 설계서" (큐 3단 구조, manifest)
- Confluence > 설계 > "옷장 기능 전체 설계" (콜백 계약, 임베딩 책임)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 루트 .env (image-processor/의 상위 = 프로젝트 루트)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Redis 큐 (reliable queue: pending → processing → done/dead) ──
# wardrobe-api의 WARDROBE_JOB_QUEUE와 같은 키를 pending으로 사용한다.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# requirepass 비밀번호 (Infisical: REDIS_PASSWORD). URL에 비밀번호를 내장하지 않고
# 이 변수로 별도 주입한다 — URL에 비밀번호가 이미 들어 있으면 URL 쪽이 우선한다.
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
PENDING_KEY = os.getenv("WARDROBE_JOB_QUEUE", "wardrobe:jobs")
PROCESSING_KEY = f"{PENDING_KEY}:processing"
DEAD_KEY = f"{PENDING_KEY}:dead"
RETRY_HASH = f"{PENDING_KEY}:retries"
MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
QUEUE_BLOCK_SEC = int(os.getenv("WORKER_QUEUE_BLOCK_SEC", "5"))

# ── 콜백 (wardrobe-api 구현 계약: X-Internal-Token + job_id 멱등) ──
INTERNAL_TOKEN = os.getenv("WARDROBE_INTERNAL_TOKEN", "")
# 원칙적으로 큐 페이로드의 callback_url을 쓰고, 없을 때만 이 값을 쓴다.
CALLBACK_FALLBACK_URL = os.getenv("WARDROBE_CALLBACK_URL", "")
CALLBACK_RETRIES = int(os.getenv("WORKER_CALLBACK_RETRIES", "3"))
CALLBACK_TIMEOUT = int(os.getenv("WORKER_CALLBACK_TIMEOUT", "15"))

# ── 파이프라인 선택 (pipeline/__init__.py 레지스트리 키) ──
PIPELINE_IMPL = os.getenv("WORKER_PIPELINE", "gemini-edit")

# ── 모델 ──
DEVICE = os.getenv("DEVICE", "")  # 비우면 cuda 가능 시 cuda (임베딩용)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_ENUM_MODEL = os.getenv("GEMINI_ENUM_MODEL", "gemini-3.5-flash")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_FLASH_IMAGE_MODEL", "gemini-3.1-flash-image")
GEMINI_TAG_MODEL = os.getenv("GEMINI_TAG_MODEL", "gemini-3.5-flash")

# ── 임베딩 (설계서에 없던 단계 — 조율안에 따라 Worker 책임으로 추가) ──
EMBED_ENABLED = os.getenv("WORKER_EMBED_ENABLED", "1") == "1"
IMAGE_EMBED_MODEL = os.getenv("WORKER_IMAGE_EMBED_MODEL", "hf-hub:Marqo/marqo-fashionSigLIP")
TEXT_EMBED_MODEL = os.getenv("WORKER_TEXT_EMBED_MODEL", "BAAI/bge-m3")
EMBEDDING_VERSION = os.getenv("WARDROBE_EMBEDDING_VERSION", "fashionsiglip-v1")

# ── 처리 스키마 버전 (manifest에 기록) ──
SCHEMA_VERSION = "1.0"
PIPELINE_VERSION = os.getenv("WORKER_PIPELINE_VERSION", "gemini-edit-v1")
