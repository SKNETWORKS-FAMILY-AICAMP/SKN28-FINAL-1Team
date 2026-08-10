"""성별 표기를 한 곳에서만 해석한다.

성별은 추천에서 유일한 **하드 룰**이다. 남성 사용자에게 여성 코디가 나가면
순위가 낮아도 오작동으로 읽힌다. 그런데 이 값은 DB → 스냅샷 JSON → 리트리버로
세 번 손을 바꾸고, 그 사이에서 한 번 조용히 망가진 적이 있다:

    outfit_context._serialize_measurement 가 ``value or None`` 으로 빈 문자열을
    None으로 바꿨고 → daily_look이 ``str(...)`` 로 감싸 문자열 "None"이 되었고
    → 리트리버의 ``GENDER_TO_PRESENTATION.get("none")`` 이 None을 돌려주어
    **성별 필터가 통째로 사라졌다.** 예외도 로그도 남지 않았다.

그래서 해석을 이 모듈 하나로 모으고, 어떤 쓰레기가 들어와도 "male"|"female"|""
셋 중 하나만 나가게 한다. 모르는 값은 "그냥 통과"가 아니라 ""로 떨어지고,
호출부가 ""를 어떻게 다룰지 명시적으로 정한다.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: 골든셋 payload의 성별 표현 그룹. ml/golden_set/manifest.py의 표준 값과 같아야
#: 한다. golden_set은 Django 없이 도는 패키지라 import할 수 없어 값을 복제한다.
PRESENTATION_MEN = "men"
PRESENTATION_WOMEN = "women"
PRESENTATION_UNISEX = "unisex"

GENDER_TO_PRESENTATION = {"male": PRESENTATION_MEN, "female": PRESENTATION_WOMEN}

#: 표기 흔들림을 흡수한다. BodyMeasurement는 male/female만 저장하지만, 이 값은
#: JSON 스냅샷과 외부 입력을 거쳐 오기도 한다.
_ALIASES = {
    "male": "male", "m": "male", "man": "male", "men": "male", "mens": "male",
    "남": "male", "남성": "male", "남자": "male",
    "female": "female", "f": "female", "woman": "female", "women": "female",
    "womens": "female", "여": "female", "여성": "female", "여자": "female",
}

#: "값 없음"을 뜻하는 표기들. "none"이 여기 있는 게 핵심이다 — str(None)이
#: 실제로 여기까지 흘러온 적이 있다.
_BLANKS = {"", "none", "null", "nan", "unknown", "unspecified", "미지정", "-"}


def normalize_gender(raw: Any) -> str:
    """어떤 표기로 들어와도 "male" | "female" | "" 만 돌려준다."""
    if raw is None:
        return ""
    text = str(raw).strip().lower()
    if text in _BLANKS:
        return ""
    resolved = _ALIASES.get(text, "")
    if not resolved:
        # 조용히 "성별 없음"으로 떨어지면 하드 필터가 사라진다. 사라지더라도
        # 흔적은 남긴다.
        logger.warning("해석할 수 없는 성별 표기라 성별 필터를 걸지 못합니다: %r", raw)
    return resolved


def allowed_presentation_groups(raw: Any) -> tuple[str, ...]:
    """그 성별에게 내보내도 되는 presentation_group 집합.

    빈 튜플은 "제한 없음"이 아니라 "성별을 모른다"는 뜻이다. 호출부가 그 상황을
    어떻게 처리할지 스스로 정해야 한다 — 오늘의 룩은 추천을 만들지 않는다.
    """
    presentation = GENDER_TO_PRESENTATION.get(normalize_gender(raw))
    if not presentation:
        return ()
    # 라벨이 없는 코디(presentation_group="")는 여기 없으므로 함께 빠진다.
    # 미분류를 unisex로 취급하면 여성 코디가 그대로 남성에게 나간다.
    return (presentation, PRESENTATION_UNISEX)
