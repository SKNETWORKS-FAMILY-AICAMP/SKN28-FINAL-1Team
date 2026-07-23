"""Claude Agent SDK 태거 (클로드 구독제 계정 사용).

인증
- 구독제(Pro/Max) 계정: `claude setup-token`으로 발급한 OAuth 토큰을
  CLAUDE_CODE_OAUTH_TOKEN 환경변수로 설정한다. API 종량 과금 대신 구독 사용량을 쓴다.
- ANTHROPIC_API_KEY가 설정돼 있으면 그것도 동작한다 (API 과금).

특징
- claude-agent-sdk의 output_format(json_schema)으로 구조화 출력을 강제하고,
  ResultMessage.structured_output에서 태그를 읽는다 (실패 시 텍스트 파싱 fallback).
- 도구/파일시스템 설정을 전부 비활성화한 순수 단발 질의로 실행한다
  (tools=[], setting_sources=[] → CLAUDE.md 등 미로드).
- 이미지 입력은 지원하지 않는다 (텍스트 태깅 전용).

요구사항: pip install claude-agent-sdk (Claude Code CLI 포함/필요. 미설치 시 명확히 실패)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from typing import Any, Dict, Optional, Tuple

from util.tagging.base import (
    MAX_RETRIES,
    SYSTEM_PROMPT,
    TAG_SCHEMA,
    build_payload,
    failed_meta,
    logger,
    merge_tags,
    parse_json_text,
    tagged_meta,
)

try:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
except ImportError:  # pragma: no cover
    ClaudeAgentOptions = None
    ResultMessage = None
    query = None


class ClaudeTagger:
    def __init__(self) -> None:
        if query is None:
            raise RuntimeError(
                "claude-agent-sdk 패키지가 없습니다. "
                "`pip install claude-agent-sdk` 후 사용하세요 (Claude Code CLI 필요)."
            )
        if not os.getenv("CLAUDE_CODE_OAUTH_TOKEN") and not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(
                "CLAUDE_CODE_OAUTH_TOKEN이 없습니다. 구독제 계정에서 `claude setup-token`으로 "
                "발급해 .env에 설정하세요 (또는 ANTHROPIC_API_KEY)."
            )
        # CLI가 PATH에 없으면 조기 경고 (SDK 번들 CLI가 있으면 동작할 수 있어 raise는 안 함)
        if shutil.which("claude") is None:
            logger.warning(
                "claude CLI가 PATH에 없습니다. SDK 번들 CLI로 시도하지만, 실패하면 "
                "`npm install -g @anthropic-ai/claude-code`로 설치하세요 "
                "(Docker: INSTALL_CLAUDE_CLI=true 빌드)."
            )
        # 빈 값이면 CLI 기본 모델 사용
        self.model = os.getenv("NAVER_CLAUDE_MODEL", "").strip() or None
        self.model_label = f"claude:{self.model or 'default'}"
        # 상품마다 asyncio.run으로 루프를 새로 만들면 서브프로세스 정리 경고가 누적되므로
        # 태거 인스턴스가 이벤트 루프 하나를 소유하고 재사용한다.
        self._loop = asyncio.new_event_loop()

    # --------------------------------------------------------
    def tag(
        self,
        title: str,
        category_large: str,
        category_small: str,
        naver_categories: list,
        rule_attrs: Dict[str, Any],
        image_url: Optional[str] = None,  # 인터페이스 호환용. Claude 모드는 이미지 미지원.
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        payload = build_payload(title, category_large, category_small, naver_categories, rule_attrs)
        prompt = (
            json.dumps(payload, ensure_ascii=False)
            + "\n\n위 상품을 태깅하라. 스키마에 맞는 JSON만 출력한다."
        )

        tags: Optional[Dict[str, Any]] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                tags = self._loop.run_until_complete(self._query(prompt))
                if tags is not None:
                    break
            except Exception:  # noqa: BLE001
                logger.exception("Claude 태깅 실패 (attempt %s/%s): %s",
                                 attempt + 1, MAX_RETRIES + 1, title[:50])
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

        if tags is None:
            return {}, failed_meta(self.model_label)

        merged, tag_source = merge_tags(rule_attrs, tags)
        return merged, tagged_meta(self.model_label, tag_source)

    # --------------------------------------------------------
    def _options(self) -> "ClaudeAgentOptions":
        return ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            model=self.model,
            max_turns=1,
            tools=[],              # 내장 도구 전부 비활성 (순수 태깅 질의)
            setting_sources=[],    # 파일시스템 설정/CLAUDE.md 미로드 (SDK isolation)
            output_format={"type": "json_schema", "schema": TAG_SCHEMA},
        )

    async def _query(self, prompt: str) -> Optional[Dict[str, Any]]:
        """단발 질의. structured_output 우선, 실패 시 결과 텍스트 파싱."""
        result: Optional[ResultMessage] = None
        async for message in query(prompt=prompt, options=self._options()):
            if ResultMessage is not None and isinstance(message, ResultMessage):
                result = message

        if result is None:
            logger.warning("Claude 응답에 ResultMessage가 없습니다.")
            return None
        if result.is_error:
            # errors 필드는 SDK 버전에 따라 없을 수 있어 getattr로 방어
            logger.warning(
                "Claude 질의 오류: subtype=%s, errors=%s",
                result.subtype, (getattr(result, "errors", None) or [])[:3],
            )
            return None

        structured = result.structured_output
        if isinstance(structured, dict):
            return structured

        return parse_json_text(result.result or "")
