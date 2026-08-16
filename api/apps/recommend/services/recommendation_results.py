"""추천 카드 조회와 피드백 변경을 위한 소유권 경계 서비스."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from apps.chat.models import ChatIdentity
from apps.recommend.models import (
    OutfitComposition,
    OutfitCompositionItem,
    ProductClickEvent,
    RecommendationFeedback,
    RecommendationResult,
    SavedOutfit,
)

PRODUCT_CLICK_DEDUPLICATION_WINDOW = timedelta(minutes=5)


def _public_compositions() -> QuerySet[OutfitComposition]:
    """검증을 통과해 사용자에게 노출 가능한 카드만 반환한다."""
    return (
        OutfitComposition.objects.filter(status=OutfitComposition.Status.VALIDATED)
        .select_related("feedback")
        .prefetch_related("items", "saved_records")
        .order_by("rank", "created_at")
    )


def owned_results(identity: ChatIdentity) -> QuerySet[RecommendationResult]:
    return (
        RecommendationResult.objects.filter(identity=identity)
        .select_related("session", "run")
        .prefetch_related(
            Prefetch(
                "compositions",
                queryset=_public_compositions(),
                to_attr="public_compositions",
            )
        )
        .order_by("-created_at")
    )


def owned_result(
    *,
    identity: ChatIdentity,
    result_id: uuid.UUID,
) -> RecommendationResult | None:
    return owned_results(identity).filter(pk=result_id).first()


def owned_card(
    *,
    identity: ChatIdentity,
    result_id: uuid.UUID,
    card_id: uuid.UUID,
) -> OutfitComposition | None:
    return (
        _public_compositions()
        .filter(
            pk=card_id,
            result_id=result_id,
            result__identity=identity,
        )
        .first()
    )


@transaction.atomic
def put_feedback(
    *,
    identity: ChatIdentity,
    result_id: uuid.UUID,
    card_id: uuid.UUID,
    reaction: str,
    reason_codes: list[str],
    comment: str,
) -> tuple[RecommendationFeedback | None, bool]:
    """소유 카드의 피드백을 생성하거나 전체 교체한다."""
    composition = (
        OutfitComposition.objects.select_for_update()
        .filter(
            pk=card_id,
            result_id=result_id,
            result__identity=identity,
            status=OutfitComposition.Status.VALIDATED,
        )
        .first()
    )
    if composition is None:
        return None, False
    feedback, created = RecommendationFeedback.objects.update_or_create(
        composition=composition,
        defaults={
            "reaction": reaction,
            "reason_codes": reason_codes,
            "comment": comment,
        },
    )
    return feedback, created


@transaction.atomic
def delete_feedback(
    *,
    identity: ChatIdentity,
    result_id: uuid.UUID,
    card_id: uuid.UUID,
) -> bool:
    deleted, _ = RecommendationFeedback.objects.filter(
        composition_id=card_id,
        composition__result_id=result_id,
        composition__result__identity=identity,
        composition__status=OutfitComposition.Status.VALIDATED,
    ).delete()
    return deleted > 0


@transaction.atomic
def save_outfit(
    *,
    identity: ChatIdentity,
    result_id: uuid.UUID,
    card_id: uuid.UUID,
) -> tuple[SavedOutfit | None, bool]:
    """회원이 소유한 검증 완료 코디를 멱등 저장한다."""

    if identity.user_id is None:
        return None, False
    composition = (
        OutfitComposition.objects.select_for_update()
        .select_related("result__identity")
        .filter(
            pk=card_id,
            result_id=result_id,
            result__identity=identity,
            status=OutfitComposition.Status.VALIDATED,
        )
        .first()
    )
    if composition is None:
        return None, False
    saved_outfit, created = SavedOutfit.objects.get_or_create(
        user_id=identity.user_id,
        composition=composition,
    )
    return saved_outfit, created


@transaction.atomic
def delete_saved_outfit(
    *,
    identity: ChatIdentity,
    result_id: uuid.UUID,
    card_id: uuid.UUID,
) -> bool:
    """소유 카드가 존재하면 저장 여부와 관계없이 멱등 해제한다."""

    if identity.user_id is None:
        return False
    composition_exists = OutfitComposition.objects.filter(
        pk=card_id,
        result_id=result_id,
        result__identity=identity,
        status=OutfitComposition.Status.VALIDATED,
    ).exists()
    if not composition_exists:
        return False
    SavedOutfit.objects.filter(
        user_id=identity.user_id,
        composition_id=card_id,
    ).delete()
    return True


@transaction.atomic
def record_product_click(
    *,
    identity: ChatIdentity,
    result_id: uuid.UUID,
    card_id: uuid.UUID,
    item_id: uuid.UUID,
) -> tuple[ProductClickEvent | None, bool]:
    """소유 추천의 판매 상품 클릭을 5분 중복 제거 구간으로 수집한다."""

    if identity.user_id is None:
        return None, False
    item = (
        OutfitCompositionItem.objects.select_for_update()
        .select_related("composition__result__identity")
        .filter(
            pk=item_id,
            composition_id=card_id,
            composition__result_id=result_id,
            composition__result__identity=identity,
            composition__status=OutfitComposition.Status.VALIDATED,
            source_type=OutfitCompositionItem.SourceType.PRODUCT,
        )
        .first()
    )
    if item is None:
        return None, False

    cutoff = timezone.now() - PRODUCT_CLICK_DEDUPLICATION_WINDOW
    existing = (
        ProductClickEvent.objects.filter(
            user_id=identity.user_id,
            item=item,
            created_at__gte=cutoff,
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return existing, False

    result = item.composition.result
    event = ProductClickEvent.objects.create(
        user_id=identity.user_id,
        item=item,
        result_id_snapshot=result.id,
        composition_id_snapshot=item.composition_id,
        persona_id=result.persona_id,
        source_collection=item.source_collection,
        source_id=item.source_id,
    )
    return event, True
