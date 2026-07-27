"""
태깅 공통 코어 (provider 중립, 외부 서비스/DB 의존 없음).

태그 값 체계는 컨플루언스 "의류 상품 데이터 카테고리-태그 매핑 문서"를 따른다.
(https://jjeoe0317.atlassian.net/wiki/spaces/SKN281team/pages/14286849)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

# util 패키지를 naver config 없이 단독 임포트해도 .env 값을 읽도록 보장
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

logger = logging.getLogger("tagging")

# 공통 파라미터
TEMPERATURE = float(os.getenv("NAVER_LLM_TEMPERATURE", "0.1"))
MAX_RETRIES = int(os.getenv("NAVER_LLM_MAX_RETRIES", "2"))

# 문서 3-1 계절 태그
SEASONS = ["봄", "여름", "가을", "겨울", "간절기"]

# 문서 4-3 스타일 태그 후보군
STYLES = [
    "캐주얼", "포멀", "미니멀", "스트릿", "스포티", "러블리", "페미닌", "시크",
    "빈티지", "아웃도어", "댄디", "아메카지", "트렌디", "리조트", "베이직",
]

# 문서 5-3 layer_role
LAYER_ROLES = ["기본 상의", "레이어드 상의", "아우터", "하의", "원피스", "신발", "가방", "액세서리", "이너웨어"]

# 태그 JSON 스키마 (bare). OpenAI는 openai_response_format()으로 감싸서 쓰고,
# Claude Agent SDK는 output_format={"type": "json_schema", "schema": TAG_SCHEMA}로 쓴다.
TAG_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "season": {
            "type": "array",
            "items": {"type": "string", "enum": SEASONS},
            "description": "착용 적합 계절. 복수 선택 가능",
        },
        "style": {
            "type": "array",
            "items": {"type": "string", "enum": STYLES},
            "description": "상품 분위기. 대표 분위기 우선, 1~3개",
        },
        "usage": {
            "type": "array",
            "items": {"type": "string"},
            "description": "착용 상황. 예: 데일리, 외출, 출근, 운동, 홈웨어, 수면, 휴양지",
        },
        "color": {
            "type": "array",
            "items": {"type": "string"},
            "description": "대표 색상 (한국어, 최대 3개). 판단 불가 시 빈 배열",
        },
        "pattern": {
            "type": "array",
            "items": {"type": "string"},
            "description": "문양. 예: 무지, 체크, 스트라이프. 판단 불가 시 빈 배열",
        },
        "fit": {
            "type": ["string", "null"],
            "description": "핏. 예: 오버핏, 레귤러핏, 슬림핏. 판단 불가 시 null",
        },
        "material": {
            "type": "array",
            "items": {"type": "string"},
            "description": "소재. 예: 코튼, 니트, 울. 판단 불가 시 빈 배열",
        },
        "sleeve": {
            "type": ["string", "null"],
            "description": "소매 길이(상의류만). 반팔/긴팔/민소매/7부/5부, 해당 없으면 null",
        },
        "length": {
            "type": ["string", "null"],
            "description": "기장. 크롭/기본/롱/미니/미디, 판단 불가 시 null",
        },
        "layer_role": {
            "type": ["string", "null"],
            "description": f"코디 내 레이어드 역할. 다음 중 하나: {', '.join(LAYER_ROLES)}. 해당 없으면 null",
        },
        "layer_order": {
            "type": ["integer", "null"],
            "description": "착용 순서. 1=가장 안쪽, 3=가장 바깥. 의류가 아니면 null",
        },
    },
    "required": [
        "season", "style", "usage", "color", "pattern", "fit",
        "material", "sleeve", "length", "layer_order", "layer_role",
    ],
}

SYSTEM_PROMPT = """\
당신은 패션 상품 데이터 태깅 전문가다. 주어진 상품 정보(상품명, 카테고리, 이미 추출된 속성,
선택적으로 상품 이미지)를 보고 추천 시스템용 태그를 JSON으로 생성한다.

규칙:
- season: 소재/소매/기장/카테고리를 근거로 판단. 여러 계절 착용 가능하면 모두 포함.
  얇은 아우터는 ["봄","가을","간절기"], 패딩/기모는 ["겨울"], 린넨/민소매/샌들은 ["여름"].
- style: 후보군 안에서만 선택. 대표 분위기 1~3개. 특징 없는 일상복은 캐주얼 또는 베이직.
- usage: 데일리/외출/출근/운동/홈웨어/수면/휴양지 등. 언더웨어·파자마는 홈웨어/수면 위주.
- 이미 추출된 속성(rule_extracted)은 신뢰하되, 명백히 틀렸으면 수정한다.
- 비어 있는 속성만 적극적으로 채운다. 근거 없으면 null/빈 배열로 남긴다.
- layer_order: 이너/기본 상의=1, 레이어드 상의=2, 아우터=3, 하의=1, 비의류는 null.
"""


# ------------------------------------------------------------
# 입력 구성
# ------------------------------------------------------------


def build_payload(
    title: str,
    category_large: str,
    category_small: str,
    naver_categories: list,
    rule_attrs: Dict[str, Any],
) -> Dict[str, Any]:
    """모든 provider가 공유하는 상품 입력 페이로드."""
    return {
        "item_name": title,
        "category_large": category_large,
        "category_small": category_small,
        "naver_category_path": " > ".join(c for c in naver_categories if c),
        "rule_extracted": rule_attrs,
    }


def build_openai_messages(
    title: str,
    category_large: str,
    category_small: str,
    naver_categories: list,
    rule_attrs: Dict[str, Any],
    image_url: Optional[str] = None,
) -> list:
    """OpenAI chat.completions 메시지 구성 (동기/Batch 공용)."""
    payload = build_payload(title, category_large, category_small, naver_categories, rule_attrs)
    content: list = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url, "detail": "low"}})
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def openai_response_format() -> dict:
    """OpenAI structured output 스펙."""
    return {
        "type": "json_schema",
        "json_schema": {"name": "fashion_item_tags", "strict": True, "schema": TAG_SCHEMA},
    }


# ------------------------------------------------------------
# 출력 파싱 / 병합
# ------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_text(text: str) -> Optional[Dict[str, Any]]:
    """
    LLM 텍스트 응답에서 JSON 오브젝트를 최대한 관대하게 추출한다.
    (structured output이 없는 provider 대비 방어 로직)
    """
    if not text:
        return None
    candidate = text.strip()

    fence = _FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()

    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass

    # 앞뒤 잡담이 섞인 경우: 첫 '{' ~ 마지막 '}' 구간 시도
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(candidate[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    return None


def merge_tags(
    rule_attrs: Dict[str, Any], llm_tags: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    규칙 추출값 우선 병합. 규칙값이 비어 있으면 LLM 값을 쓰고 출처를 기록한다.
    season/style/usage/layer_*는 LLM 전용 필드.
    """
    merged: Dict[str, Any] = {}
    source: Dict[str, str] = {}

    for field in ("color", "pattern", "material"):
        rule_val = rule_attrs.get(field) or []
        if rule_val:
            merged[field], source[field] = rule_val, "rule"
        else:
            merged[field] = llm_tags.get(field) or []
            if merged[field]:
                source[field] = "llm"

    for field in ("fit", "sleeve", "length"):
        rule_val = rule_attrs.get(field)
        if rule_val:
            merged[field], source[field] = rule_val, "rule"
        else:
            merged[field] = llm_tags.get(field)
            if merged[field]:
                source[field] = "llm"

    for field in ("season", "style", "usage"):
        merged[field] = llm_tags.get(field) or []
        if merged[field]:
            source[field] = "llm"

    for field in ("layer_role", "layer_order"):
        merged[field] = llm_tags.get(field)
        if merged[field] is not None:
            source[field] = "llm"

    # 후보군 밖 값 방어
    merged["season"] = [s for s in merged["season"] if s in SEASONS]
    merged["style"] = [s for s in merged["style"] if s in STYLES][:3]
    if merged.get("layer_role") not in LAYER_ROLES:
        merged["layer_role"] = None
        source.pop("layer_role", None)

    return merged, source


def failed_meta(model_label: str, used_image: bool = False) -> Dict[str, Any]:
    return {
        "tagging_status": "failed",
        "tagging_model": model_label,
        "tagging_used_image": used_image,
        "tag_source": {},
    }


def tagged_meta(model_label: str, tag_source: Dict[str, str], used_image: bool = False) -> Dict[str, Any]:
    return {
        "tagging_status": "tagged",
        "tagging_model": model_label,
        "tagging_used_image": used_image,
        "tag_source": tag_source,
    }
