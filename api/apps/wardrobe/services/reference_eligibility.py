"""공유 옷의 채팅 레퍼런스 선택 가능 여부를 판정한다.

Qdrant는 파생 저장소이며, 옷장 벡터 적재가 성공한 경우에만
``WardrobeItem.embedding_version``이 유지된다. 기본 판정은 이 서버 관리 상태를
사용하고, 공유 옷 목록 응답은 실제 Qdrant 포인트도 배치 검증한다.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from apps.wardrobe.models import SharedWardrobeItem
from apps.wardrobe.services.vector_reconciliation import (
    WardrobeVectorReconciler,
    WardrobeVectorStoreUnavailable,
)

logger = logging.getLogger(__name__)

REFERENCE_UNAVAILABLE_NOT_CONFIRMED = "NOT_CONFIRMED"
REFERENCE_UNAVAILABLE_VECTOR_NOT_READY = "VECTOR_NOT_READY"

REFERENCE_UNAVAILABLE_REASON_CHOICES = (
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
    """원본 옷의 처리 상태를 기준으로 선택 가능 여부를 반환한다.

    공유 상태(available/borrowed/private)는 더 이상 판정에 쓰지 않는다 —
    방에 등록된 옷은 멤버 전원이 항상 참고할 수 있다.
    """

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

    return ReferenceEligibility(eligible=True)


def resolve_reference_eligibilities(
    shared_items: Iterable[SharedWardrobeItem],
    *,
    reconciler: WardrobeVectorReconciler | None = None,
) -> dict[str, ReferenceEligibility]:
    """공유 옷 목록의 실제 벡터 준비 상태를 Qdrant 한 번에 확인한다.

    비공개·미확정·DB 플래그 미설정 아이템은 기존 판정만 사용한다. DB 기준으로
    선택 가능한 후보만 Qdrant에서 검증하며, 저장소 장애 시에는 거짓 양성보다
    안전한 선택 불가 상태로 닫는다. 이 함수는 DB와 Qdrant를 수정하지 않는다.
    """

    items = list(shared_items)
    resolved = {
        str(shared_item.pk): evaluate_reference_eligibility(shared_item)
        for shared_item in items
    }
    candidates = [
        shared_item
        for shared_item in items
        if resolved[str(shared_item.pk)].eligible
    ]
    if not candidates:
        return resolved

    wardrobe_items_by_id = {
        str(shared_item.wardrobe_item_id): shared_item.wardrobe_item
        for shared_item in candidates
    }
    try:
        audits = (reconciler or WardrobeVectorReconciler()).audit(
            list(wardrobe_items_by_id.values())
        )
    except WardrobeVectorStoreUnavailable:
        logger.warning("공유 옷 참고 가능 여부를 위한 Qdrant 조회 실패")
        for shared_item in candidates:
            resolved[str(shared_item.pk)] = ReferenceEligibility(
                eligible=False,
                unavailable_reason=REFERENCE_UNAVAILABLE_VECTOR_NOT_READY,
            )
        return resolved

    readiness_by_item_id = {
        audit.item_id: audit.vector_ready for audit in audits
    }
    for shared_item in candidates:
        if readiness_by_item_id.get(str(shared_item.wardrobe_item_id)) is not True:
            resolved[str(shared_item.pk)] = ReferenceEligibility(
                eligible=False,
                unavailable_reason=REFERENCE_UNAVAILABLE_VECTOR_NOT_READY,
            )
    return resolved
