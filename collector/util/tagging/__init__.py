"""
상품 태깅 공용 패키지 (provider 중립).

- base            : 태그 체계 상수, JSON 스키마, 프롬프트, 병합/파싱 유틸 (외부 의존 없음)
- openai_tagger   : OpenAI 동기 태거 (이미지 auto 재시도 지원)
- openai_batch    : OpenAI Batch API 요청/응답 헬퍼 (DB 의존 없음)
- claude_tagger   : Claude Agent SDK 태거 (구독제 계정 OAuth 토큰 사용)

provider 선택은 환경변수 NAVER_TAGGING_PROVIDER(openai|claude)로 제어한다.
모든 태거는 동일한 인터페이스를 가진다:
    tag(title, category_large, category_small, naver_categories, rule_attrs, image_url=None)
      -> (tags: dict, meta: dict)
"""

from __future__ import annotations

import os

from util.tagging.base import (  # noqa: F401 (re-export)
    LAYER_ROLES,
    SEASONS,
    STYLES,
    merge_tags,
    parse_json_text,
)

PROVIDER_OPENAI = "openai"
PROVIDER_CLAUDE = "claude"


def get_provider() -> str:
    provider = os.getenv("NAVER_TAGGING_PROVIDER", PROVIDER_OPENAI).strip().lower()
    if provider not in (PROVIDER_OPENAI, PROVIDER_CLAUDE):
        raise ValueError(
            f"NAVER_TAGGING_PROVIDER 값이 올바르지 않습니다: {provider} (openai | claude)"
        )
    return provider


def get_sync_tagger():
    """환경변수에 따라 동기 태거 인스턴스를 반환한다."""
    provider = get_provider()
    if provider == PROVIDER_CLAUDE:
        from util.tagging.claude_tagger import ClaudeTagger

        return ClaudeTagger()
    from util.tagging.openai_tagger import OpenAITagger

    return OpenAITagger()
