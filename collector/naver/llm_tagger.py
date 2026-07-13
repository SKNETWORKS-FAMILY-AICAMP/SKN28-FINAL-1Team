"""
OpenAI 기반 LLM 태깅.

규칙 추출(attribute_extractor)로 못 채운 태그(season/style/usage/layer_role/layer_order 및
누락된 color/fit 등)를 DB insert 전에 LLM으로 채운다.

이미지 활용 (NAVER_LLM_IMAGE_MODE):
- auto  : 텍스트만으로 1차 태깅 → style 또는 color 판단 실패 시 상품 이미지를 포함해 재시도
- always: 항상 이미지 포함
- never : 텍스트만

태그 값 체계는 컨플루언스 "의류 상품 데이터 카테고리-태그 매핑 문서"를 따른다.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

from config import (
    LLM_IMAGE_MODE,
    LLM_MAX_RETRIES,
    LLM_TEMPERATURE,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    logger,
)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

# 문서 3-1 계절 태그
SEASONS = ["봄", "여름", "가을", "겨울", "간절기"]

# 문서 4-3 스타일 태그 후보군
STYLES = [
    "캐주얼", "포멀", "미니멀", "스트릿", "스포티", "러블리", "페미닌", "시크",
    "빈티지", "아웃도어", "댄디", "아메카지", "트렌디", "리조트", "베이직",
]

# 문서 5-3 layer_role
LAYER_ROLES = ["기본 상의", "레이어드 상의", "아우터", "하의", "원피스", "신발", "가방", "액세서리", "이너웨어"]

_JSON_SCHEMA = {
    "name": "fashion_item_tags",
    "strict": True,
    "schema": {
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
    },
}

_SYSTEM_PROMPT = """\
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


def build_messages(
    title: str,
    category_large: str,
    category_small: str,
    naver_categories: list[str],
    rule_attrs: Dict[str, Any],
    image_url: Optional[str] = None,
) -> list[dict]:
    """chat.completions 메시지 구성. 동기 태깅과 Batch API가 공용으로 쓴다."""
    payload = {
        "item_name": title,
        "category_large": category_large,
        "category_small": category_small,
        "naver_category_path": " > ".join(c for c in naver_categories if c),
        "rule_extracted": rule_attrs,
    }
    content: list[dict] = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url, "detail": "low"}})
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def response_format() -> dict:
    """structured output 스펙. 동기/배치 공용."""
    return {"type": "json_schema", "json_schema": _JSON_SCHEMA}


def merge_tags(rule_attrs: Dict[str, Any], llm_tags: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
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


class LLMTagger:
    def __init__(self) -> None:
        if OpenAI is None:
            raise RuntimeError("openai 패키지가 없습니다. requirements.naver.txt를 설치하세요.")
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 없습니다. .env에 설정하세요.")
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL

    # --------------------------------------------------------
    def tag(
        self,
        title: str,
        category_large: str,
        category_small: str,
        naver_categories: list[str],
        rule_attrs: Dict[str, Any],
        image_url: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        상품 1건 태깅. (tags, meta) 반환.
        meta = {"tagging_status", "tagging_model", "tagging_used_image", "tag_source"}
        """
        use_image_first = LLM_IMAGE_MODE == "always" and bool(image_url)
        tags = self._call(title, category_large, category_small, naver_categories,
                          rule_attrs, image_url if use_image_first else None)
        used_image = use_image_first

        # auto 모드: 텍스트만으로 style/color 판단이 안 됐으면 이미지 포함 재시도
        if (
            not used_image
            and LLM_IMAGE_MODE == "auto"
            and image_url
            and tags is not None
            and (not tags.get("style") or (not tags.get("color") and not rule_attrs.get("color")))
        ):
            logger.debug("이미지 포함 재태깅: %s", title[:50])
            retry = self._call(title, category_large, category_small, naver_categories,
                               rule_attrs, image_url)
            if retry is not None:
                tags = retry
                used_image = True

        if tags is None:
            return {}, {
                "tagging_status": "failed",
                "tagging_model": self.model,
                "tagging_used_image": used_image,
                "tag_source": {},
            }

        merged, tag_source = merge_tags(rule_attrs, tags)
        return merged, {
            "tagging_status": "tagged",
            "tagging_model": self.model,
            "tagging_used_image": used_image,
            "tag_source": tag_source,
        }

    # --------------------------------------------------------
    def _call(
        self,
        title: str,
        category_large: str,
        category_small: str,
        naver_categories: list[str],
        rule_attrs: Dict[str, Any],
        image_url: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        messages = build_messages(
            title, category_large, category_small, naver_categories, rule_attrs, image_url
        )

        for attempt in range(LLM_MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=LLM_TEMPERATURE,
                    messages=messages,
                    response_format=response_format(),
                )
                return json.loads(response.choices[0].message.content)
            except Exception:  # noqa: BLE001
                logger.exception("LLM 태깅 실패 (attempt %s/%s): %s",
                                 attempt + 1, LLM_MAX_RETRIES + 1, title[:50])
                if attempt < LLM_MAX_RETRIES:
                    time.sleep(2 ** attempt)
        return None

