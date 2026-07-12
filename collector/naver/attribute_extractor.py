"""
상품명(title) 기반 속성 규칙 추출기.

네이버 검색 API 응답에는 color/fit/sleeve/pattern/material/length 필드가 없다.
대신 쇼핑몰 상품명에 이런 속성이 관용적으로 포함되므로(예: "화이트 오버핏 반팔 티셔츠"),
어휘 사전 매칭으로 최대한 추출한다. 여기서 못 뽑은 값은 LLM 태깅(llm_tagger)이 채운다.

추출 값 표기는 컨플루언스 문서의 태그 체계를 따른다 (오버핏/레귤러핏/슬림핏, 반팔/긴팔 등).
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional

# ------------------------------------------------------------
# title 클리닝
# ------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")


def clean_title(raw_title: str) -> str:
    """검색 API title의 <b> 태그·HTML 엔티티 제거."""
    text = _TAG_RE.sub("", raw_title or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ------------------------------------------------------------
# 어휘 사전 (표준 표기 → 상품명에 등장하는 변형들)
# 변형은 긴 단어부터 매칭해 부분 오탐(예: "블랙"이 "블랙핑크"에 매칭)을 줄인다.
# ------------------------------------------------------------

COLOR_VOCAB: Dict[str, List[str]] = {
    "블랙": ["블랙", "검정", "흑색", "black"],
    "화이트": ["화이트", "흰색", "백색", "white"],
    "아이보리": ["아이보리", "크림색", "크림", "ivory", "cream"],
    "그레이": ["그레이", "회색", "차콜", "챠콜", "gray", "grey", "charcoal"],
    "네이비": ["네이비", "곤색", "navy"],
    "블루": ["블루", "파랑", "하늘색", "스카이블루", "데님블루", "blue"],
    "그린": ["그린", "초록", "올리브", "카키그린", "민트", "green", "khaki green", "mint"],
    "카키": ["카키", "khaki"],
    "베이지": ["베이지", "샌드", "오트밀", "beige", "sand", "oatmeal"],
    "브라운": ["브라운", "갈색", "초코", "카멜", "모카", "brown", "camel", "mocha"],
    "레드": ["레드", "빨강", "버건디", "와인", "red", "burgundy", "wine"],
    "핑크": ["핑크", "분홍", "인디핑크", "pink"],
    "옐로": ["옐로우", "옐로", "노랑", "머스타드", "yellow", "mustard"],
    "오렌지": ["오렌지", "주황", "orange"],
    "퍼플": ["퍼플", "보라", "라벤더", "purple", "lavender"],
    "실버": ["실버", "은색", "silver"],
    "골드": ["골드", "금색", "gold"],
}

PATTERN_VOCAB: Dict[str, List[str]] = {
    "무지": ["무지", "솔리드", "solid"],
    "체크": ["체크", "타탄", "깅엄", "check", "tartan", "gingham"],
    "스트라이프": ["스트라이프", "줄무늬", "단가라", "stripe"],
    "도트": ["도트", "땡땡이", "dot"],
    "플로럴": ["플로럴", "플라워", "꽃무늬", "floral", "flower"],
    "레오파드": ["레오파드", "호피", "leopard"],
    "카모": ["카모", "카모플라주", "밀리터리 패턴", "camo"],
    "그래픽": ["그래픽", "프린팅", "프린트", "나염", "graphic"],
    "로고": ["로고", "logo"],
    "아가일": ["아가일", "argyle"],
    "페이즐리": ["페이즐리", "paisley"],
}

FIT_VOCAB: Dict[str, List[str]] = {
    "오버핏": ["오버핏", "오버 핏", "루즈핏", "박시핏", "박시", "오버사이즈", "oversize", "loose fit"],
    "레귤러핏": ["레귤러핏", "레귤러 핏", "스탠다드핏", "정핏", "regular fit"],
    "슬림핏": ["슬림핏", "슬림 핏", "스키니", "타이트", "slim fit", "skinny"],
    "와이드핏": ["와이드핏", "와이드 핏", "와이드", "wide"],
    "테이퍼드핏": ["테이퍼드", "tapered"],
    "스트레이트핏": ["스트레이트", "일자핏", "일자", "straight"],
    "부츠컷": ["부츠컷", "세미부츠컷", "bootcut"],
    "릴렉스핏": ["릴렉스핏", "세미오버핏", "세미오버", "relaxed"],
}

MATERIAL_VOCAB: Dict[str, List[str]] = {
    "코튼": ["코튼", "면 100", "순면", "면소재", "cotton"],
    "린넨": ["린넨", "마혼방", "리넨", "linen"],
    "데님": ["데님", "청지", "denim"],
    "울": ["울", "양모", "램스울", "메리노", "wool", "lambswool", "merino"],
    "캐시미어": ["캐시미어", "cashmere"],
    "니트": ["니트", "스웨터조직", "knit"],
    "폴리에스터": ["폴리에스터", "폴리", "polyester", "poly"],
    "나일론": ["나일론", "nylon"],
    "레이온": ["레이온", "비스코스", "rayon", "viscose"],
    "기모": ["기모", "피치기모", "브러쉬드"],
    "플리스": ["플리스", "후리스", "양털", "fleece"],
    "코듀로이": ["코듀로이", "골덴", "corduroy"],
    "트위드": ["트위드", "tweed"],
    "가죽": ["가죽", "레더", "레자", "인조가죽", "leather"],
    "스웨이드": ["스웨이드", "suede"],
    "시어서커": ["시어서커", "seersucker"],
    "와플": ["와플", "waffle"],
    "텐셀": ["텐셀", "모달", "tencel", "modal"],
    "구스다운": ["구스다운", "구스", "goose down"],
    "덕다운": ["덕다운", "duck down"],
    "쿨링": ["쿨링", "냉감", "아이스", "쿨"],
    "발열": ["발열", "히트", "heattech", "히트텍"],
}

SLEEVE_VOCAB: Dict[str, List[str]] = {
    "반팔": ["반팔", "숏슬리브", "하프슬리브", "short sleeve"],
    "긴팔": ["긴팔", "긴소매", "롱슬리브", "long sleeve"],
    "민소매": ["민소매", "나시", "슬리브리스", "탱크", "sleeveless"],
    "7부": ["7부", "칠부"],
    "5부": ["5부", "오부"],
}

LENGTH_VOCAB: Dict[str, List[str]] = {
    "크롭": ["크롭", "크롭트", "crop"],
    "숏": ["숏기장", "숏 기장", "short"],
    "미니": ["미니", "mini"],
    "미디": ["미디", "midi"],
    "롱": ["롱기장", "롱 기장", "맥시", "롱", "long", "maxi"],
    "기본": ["기본기장", "정기장"],
}


# 부분 문자열 오탐 방지: 해당 변형이 아래 컨텍스트 안에서만 등장하면 매칭하지 않는다.
# 예: "겨울 기모 맨투맨"의 "울"은 소재가 아니다.
_EXCLUDE_CONTEXT: Dict[str, List[str]] = {
    "울": ["겨울", "여울", "방울", "울트라", "서울"],
    "미니": ["미니멀"],
    "쿨": ["쿨톤"],
    "탱크": ["탱크로리"],
}


def _mask_excluded(text: str, variant: str) -> str:
    """variant의 오탐 컨텍스트를 텍스트에서 제거한 사본을 반환."""
    for context in _EXCLUDE_CONTEXT.get(variant, []):
        text = text.replace(context, " ")
    return text


def _match_vocab(text: str, vocab: Dict[str, List[str]], multi: bool) -> List[str]:
    """
    어휘 사전 매칭. 변형 단어를 길이 내림차순으로 검사해 긴 표현을 우선한다.
    multi=False면 첫 매칭 하나만 반환.
    """
    lowered = text.lower()
    found: List[str] = []
    variants = sorted(
        ((variant.lower(), canonical) for canonical, vs in vocab.items() for variant in vs),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    for variant, canonical in variants:
        haystack = _mask_excluded(lowered, variant) if variant in _EXCLUDE_CONTEXT else lowered
        if variant in haystack and canonical not in found:
            found.append(canonical)
            if not multi:
                break
    return found


def extract_attributes(title: str) -> Dict[str, Any]:
    """
    클리닝된 상품명에서 문서 태그 필드를 규칙 기반으로 추출한다.

    반환 형태 (없으면 빈 배열/None):
    {
        "color": ["화이트"], "pattern": ["무지"], "material": ["코튼"],
        "fit": "오버핏", "sleeve": "반팔", "length": "크롭"
    }
    """
    color = _match_vocab(title, COLOR_VOCAB, multi=True)
    pattern = _match_vocab(title, PATTERN_VOCAB, multi=True)
    material = _match_vocab(title, MATERIAL_VOCAB, multi=True)
    fit = _match_vocab(title, FIT_VOCAB, multi=False)
    sleeve = _match_vocab(title, SLEEVE_VOCAB, multi=False)
    length = _match_vocab(title, LENGTH_VOCAB, multi=False)

    return {
        "color": color[:3],          # 과다 매칭 방지: 대표 색상 최대 3개
        "pattern": pattern[:2],
        "material": material[:3],
        "fit": fit[0] if fit else None,
        "sleeve": sleeve[0] if sleeve else None,
        "length": length[0] if length else None,
    }
