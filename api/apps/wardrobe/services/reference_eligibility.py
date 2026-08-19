"""공유 옷의 채팅 레퍼런스 선택 가능 여부를 판정한다.

Qdrant는 파생 저장소이며, 옷장 벡터 적재가 성공한 경우에만
``WardrobeItem.embedding_version``이 유지된다. 공유 옷 목록을 조회할 때마다
Qdrant를 다시 조회하지 않고 이 서버 관리 상태를 사용해 모바일 계약을 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.wardrobe.models import SharedWardrobeItem

REFERENCE_UNAVAILABLE_PRIVATE = "PRIVATE"
REFERENCE_UNAVAILABLE_NOT_CONFIRMED = "NOT_CONFIRMED"
REFERENCE_UNAVAILABLE_VECTOR_NOT_READY = "VECTOR_NOT_READY"

REFERENCE_UNAVAILABLE_REASON_CHOICES = (
    REFERENCE_UNAVAILABLE_PRIVATE,
    REFERENCE_UNAVAILABLE_NOT_CONFIRMED,
    REFERENCE_UNAVAILABLE_VECTOR_NOT_READY,
)


@dataclass(frozen=True, slots=True)
class ReferenceEligibility:
    eligible: bool
    unavailable_reason: str | None = None


def evaluate_reference_eligibility(
    shared_item: SharedWardrobeItem,
) -> ReferenceEligibility:
    """공유 상태와 원본 옷 처리 상태를 기준으로 선택 가능 여부를 반환한다."""

    if shared_item.status == SharedWardrobeItem.Status.PRIVATE:
        return ReferenceEligibility(
            eligible=False,
            unavailable_reason=REFERENCE_UNAVAILABLE_PRIVATE,
        )

    item = shared_item.wardrobe_item
    if not item.confirmed:
        return ReferenceEligibility(
            eligible=False,
            unavailable_reason=REFERENCE_UNAVAILABLE_NOT_CONFIRMED,
        )

    if not item.s3_key or not item.embedding_version:
        return ReferenceEligibility(
            eligible=False,
            unavailable_reason=REFERENCE_UNAVAILABLE_VECTOR_NOT_READY,
        )

    # BORROWED는 대여 상태일 뿐, 친구 옷을 참고하는 채팅 입력에서는 허용한다.
    return ReferenceEligibility(eligible=True)
