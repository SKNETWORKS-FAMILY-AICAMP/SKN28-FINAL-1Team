"""
네이버 쇼핑 상품 collector 공통 설정.

모든 값은 .env(.env.example 참고)에서 읽는다. 코드에 시크릿을 하드코딩하지 않는다.
"""

from __future__ import annotations

import logging
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

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
# 이미지 활용 모드:
#   auto   - 텍스트 태깅 결과가 부실하면(스타일/색상 판단 불가) 이미지 포함 재시도
#   always - 항상 이미지 포함 (비용 증가)
#   never  - 텍스트만 사용
LLM_IMAGE_MODE = os.getenv("NAVER_LLM_IMAGE_MODE", "auto").lower()
LLM_MAX_RETRIES = int(os.getenv("NAVER_LLM_MAX_RETRIES", "2"))
LLM_TEMPERATURE = float(os.getenv("NAVER_LLM_TEMPERATURE", "0.1"))

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
