"""추구미(Pursuit) 비즈니스 로직.

view에서 호출하는 함수들을 모아둔다. 검증/조회/저장 책임을 view와 분리.

담당:
- 옵션 마스터(PreferenceOption) 조회 — 카테고리별 그룹핑
- Pursuit 조회/저장 — nested payload 통째로
"""

from __future__ import annotations

import logging
from collections import OrderedDict

from apps.users.models import PreferenceOption, Pursuit
from apps.users.constants import PREFERENCE_CATEGORIES

logger = logging.getLogger(__name__)

# 옵션
def get_options_grouped_by_category() -> "OrderedDict[str, dict]":
    """전체 옵션을 카테고리별로 그룹핑해서 반환.

    프론트에 내려주는 형식:
        {
            "seasons": {
                "key": "seasons", 
                "label": "계절", 
                "options": [
                    {
                    "code": "spring", 
                    "label": "봄", 
                    "meta": {}}, ...
                    ]
                    },
            "styles":{
                "key": "styles",  
                "label": "스타일", 
                "options": [...]},
            ...
        }

    PREFERENCE_CATEGORIES 순서대로 (프론트 화면 순서와 일치).
    """
    # DB에서 (category, order 순) 전부 가져옴
    qs = PreferenceOption.objects.all().order_by("category", "order", "id")
    grouped: "OrderedDict[str, dict]" = OrderedDict()

    # 카테고리 키/라벨을 PREFERENCE_CATEGORIES 기준으로 먼저 셋업
    for key, label in PREFERENCE_CATEGORIES:
        grouped[key] = {"key": key, "label": label, "options": []}

    for opt in qs:
        if opt.category not in grouped:
            # 정의되지 않은 카테고리면 스킵 (안전)
            continue
        grouped[opt.category]["options"].append({
            "code": opt.code,
            "label": opt.label,
            "meta": opt.meta or {},
        })

    return grouped

# 사용자 선택

def _empty_payload() -> dict:
    """빈 payload — preferred/avoided 둘 다 모든 카테고리 키에 대해 [].

    새 user 응답용. PREFERENCE_CATEGORIES가 단일 진실 소스.
    """
    return {
        "preferred": {key: [] for key, _ in PREFERENCE_CATEGORIES},
        "avoided":   {key: [] for key, _ in PREFERENCE_CATEGORIES},
    }


def get_pursuit(user) -> dict:
    """사용자의 Pursuit payload를 가져온다. 없으면 빈 payload 반환 (DB 저장 X).

    view에서 GET 응답 만들 때 사용.
    BodyMeasurementView 정책과 동일: 404 대신 빈 응답.
    """
    obj = Pursuit.objects.filter(user=user).first()
    if obj is None:
        return _empty_payload()

    payload = obj.payload or {}
    # 누락된 카테고리 키가 있으면 빈 배열로 채워서 일관성 유지
    empty = _empty_payload()
    for mode in ("preferred", "avoided"):
        mode_data = payload.get(mode) or {}
        for key, _ in PREFERENCE_CATEGORIES:
            empty[mode][key] = list(mode_data.get(key, []) or [])
    return empty


def upsert_pursuit(user, *, preferred: dict, avoided: dict) -> Pursuit:
    """사용자의 Pursuit payload를 통째로 갈아끼운다. 없으면 새로 만듦 (upsert).

    view에서 PUT 요청 처리할 때 사용.
    """
    payload = {
        "preferred": {key: list(preferred.get(key, []) or []) for key, _ in PREFERENCE_CATEGORIES},
        "avoided":   {key: list(avoided.get(key, []) or [])   for key, _ in PREFERENCE_CATEGORIES},
    }

    obj, created = Pursuit.objects.update_or_create(
        user=user,
        defaults={"payload": payload},
    )
    logger.info(
        "pursuit %s: user_id=%s",
        "created" if created else "updated",
        user.pk,
    )
    return obj
