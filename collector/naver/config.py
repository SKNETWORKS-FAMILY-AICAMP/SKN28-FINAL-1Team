"""
네이버 쇼핑 상품 collector 공통 설정.

모든 값은 .env(.env.example 참고)에서 읽는다. 코드에 시크릿을 하드코딩하지 않는다.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# collector/ 를 sys.path에 추가해 공용 util 패키지를 임포트할 수 있게 한다.
# (naver/ 모듈들은 어디서 실행하든 config를 먼저 임포트하므로 여기서 처리)
_COLLECTOR_ROOT = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_ROOT not in sys.path:
    sys.path.insert(0, _COLLECTOR_ROOT)

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

# ------------------------------------------------------------
# 네이버 오픈 API
# ------------------------------------------------------------
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()
NAVER_SHOP_API_URL = os.getenv(
    "NAVER_SHOP_API_URL", "https://openapi.naver.com/v1/search/shop.json"
)

# 검색 파라미터 기본값
# display: 한 번에 가져올 결과 수 (10~100)
# start 최대값: 1000 → 키워드당 최대 1,000여 건까지 수집 가능
NAVER_DISPLAY = int(os.getenv("NAVER_DISPLAY", "100"))
NAVER_MAX_START = int(os.getenv("NAVER_MAX_START", "1000"))
NAVER_SORT = os.getenv("NAVER_SORT", "sim")  # sim | date | asc | dsc
# 중고(used), 렌탈(rental), 해외직구(cbshop) 상품 제외
NAVER_EXCLUDE = os.getenv("NAVER_EXCLUDE", "used:rental:cbshop")

# 키워드당 수집 목표 건수 (start 페이징 상한과 별개로 조기 종료용)
MAX_ITEMS_PER_KEYWORD = int(os.getenv("NAVER_MAX_ITEMS_PER_KEYWORD", "300"))
# API 호출 간 대기 (초). 네이버 개발 가이드에 명시적 QPS 제한은 없으나 과도호출 방지.
REQUEST_INTERVAL_SECONDS = float(os.getenv("NAVER_REQUEST_INTERVAL_SECONDS", "0.15"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("COLLECTOR_MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("COLLECTOR_RETRY_DELAY_SECONDS", "10"))

# 키워드 확장: 성별 프리픽스 ("남성,여성" 처럼 콤마 구분. 빈 값이면 확장 안 함)
KEYWORD_GENDER_PREFIXES = [
    p.strip()
    for p in os.getenv("NAVER_KEYWORD_GENDER_PREFIXES", "").split(",")
    if p.strip()
]

# ------------------------------------------------------------
# OpenAI LLM 태깅
# ------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# NAVER_LLM_IMAGE_MODE / NAVER_LLM_MAX_RETRIES / NAVER_LLM_TEMPERATURE 는
# util/tagging 패키지가 같은 env 키를 직접 읽는다 (여기서 중복 정의하지 않음).

# 태깅 provider:
#   openai - OpenAI API (sync/batch 모두 지원)
#   claude - Claude Agent SDK, 구독제 계정 OAuth 토큰 사용 (sync만 지원, 이미지 미지원)
TAGGING_PROVIDER = os.getenv("NAVER_TAGGING_PROVIDER", "openai").strip().lower()

# 태깅 모드:
#   sync  - 수집 중 상품별 실시간 태깅 (기존 방식)
#   batch - 수집은 pending으로 저장 후 OpenAI Batch API로 태깅 (비용 50% 절감, 최대 24h 지연)
TAGGING_MODE = os.getenv("NAVER_TAGGING_MODE", "batch").lower()
BATCH_MAX_REQUESTS = int(os.getenv("NAVER_BATCH_MAX_REQUESTS", "10000"))  # 배치당 요청 수 (API 한도 50,000)
BATCH_COMPLETION_WINDOW = os.getenv("NAVER_BATCH_COMPLETION_WINDOW", "24h")
BATCH_POLL_SECONDS = int(os.getenv("NAVER_BATCH_POLL_SECONDS", "600"))  # 스케줄러의 배치 상태 확인 주기
# Batch는 조건부 이미지 재시도가 불가능하므로 이미지 포함 여부를 고정한다.
# gpt-4o-mini는 이미지 토큰 과금이 커서 기본 false (텍스트만).
BATCH_INCLUDE_IMAGE = os.getenv("NAVER_BATCH_INCLUDE_IMAGE", "false").lower() in {"1", "true", "yes"}

# ------------------------------------------------------------
# DB (weather collector와 동일한 키 사용)
# ------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_NAME = os.getenv("POSTGRES_DB", os.getenv("DB_NAME", "fashion_db"))
DB_USER = os.getenv("POSTGRES_USER", os.getenv("DB_USER", "postgres"))
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", os.getenv("DB_PASSWORD", ""))
DB_HOST = os.getenv("POSTGRES_HOST", os.getenv("DB_HOST", "localhost"))
DB_PORT = os.getenv("POSTGRES_PORT", os.getenv("DB_PORT", "5432"))

# ------------------------------------------------------------
# 스케줄러
# ------------------------------------------------------------
# 매일 이 시각(KST)에 전체 수집 1회 실행
SCHEDULE_HOUR = int(os.getenv("NAVER_SCHEDULE_HOUR", "3"))
SCHEDULE_MINUTE = int(os.getenv("NAVER_SCHEDULE_MINUTE", "0"))
SCHEDULER_POLL_SECONDS = int(os.getenv("SCHEDULER_POLL_SECONDS", "30"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("naver_collector")

# Batch API는 OpenAI 전용이므로 claude provider에서는 sync로 강제 전환한다.
if TAGGING_PROVIDER == "claude" and TAGGING_MODE == "batch":
    logger.warning(
        "NAVER_TAGGING_PROVIDER=claude는 batch 모드를 지원하지 않아 sync로 전환합니다."
    )
    TAGGING_MODE = "sync"
