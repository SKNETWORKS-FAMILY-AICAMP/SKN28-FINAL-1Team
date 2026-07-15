"""홈 화면용 고정/임시 데이터.

빠른추천과 옷장/저장한 룩 카운트는 실제 추천·옷장 기능이 붙기 전까지의
자리채움(mock)이다. 실제 로직으로 교체될 때 이 모듈만 갈아끼우면 되도록
응답 필드명(quick_recommends/closet_count/saved_look_count)은 최종 형태로 둔다.

오늘의 룩 멘트는 기온 구간별 고정 템플릿이다. 구간은 (하한, 상한, 문장, 태그)
순서로 위에서부터 검사하며, 상/하한 중 하나가 None이면 그쪽은 무제한이다.
"""

from __future__ import annotations

from typing import Optional

QUICK_RECOMMENDS = ["출근룩", "데이트룩", "면접룩", "주말룩"]

MOCK_CLOSET_COUNT = 42
MOCK_SAVED_LOOK_COUNT = 8

_TEMP_BANDS = [
    (28, None, "{t}도예요. 더우니까 린넨 소재로 시원하게 입어보세요.", ["민소매", "반바지", "린넨 원피스"]),
    (23, 27, "{t}도예요. 반팔이면 딱 좋은 날씨예요.", ["반팔 티셔츠", "얇은 셔츠", "면바지"]),
    (20, 22, "{t}도예요. 선선하니까 가벼운 가디건 하나 걸쳐보세요.", ["얇은 가디건", "블라우스", "슬랙스"]),
    (17, 19, "{t}도예요. 아침저녁 쌀쌀하니 니트나 바람막이 챙기세요.", ["얇은 니트", "후드티", "바람막이"]),
    (12, 16, "{t}도예요. 재킷 하나면 든든한 날씨예요.", ["재킷", "가디건", "니트"]),
    (9, 11, "{t}도예요. 쌀쌀하니 트렌치코트나 점퍼 어때요.", ["트렌치코트", "점퍼", "니트"]),
    (5, 8, "{t}도예요. 쌀쌀하니 기모 이너에 코트 챙기세요.", ["코트", "가죽 재킷", "기모 이너"]),
    (None, 4, "{t}도예요. 많이 추우니 패딩에 목도리, 장갑까지 챙기세요.", ["패딩", "목도리", "장갑"]),
]


def build_today_look(temperature: Optional[int]) -> dict:
    if temperature is None:
        return {"comment": "", "tags": []}

    for low, high, template, tags in _TEMP_BANDS:
        if (low is None or temperature >= low) and (high is None or temperature <= high):
            return {"comment": template.format(t=temperature), "tags": tags}

    return {"comment": "", "tags": []}
