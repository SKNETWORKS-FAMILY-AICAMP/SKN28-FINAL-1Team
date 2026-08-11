"""추천 카드 조회와 피드백 변경을 위한 소유권 경계 서비스."""

from __future__ import annotations

import uuid

from django.db import transaction
from django.db.models import Prefetch, QuerySet

from apps.chat.models import ChatIdentity
from apps.recommend.models import (
    OutfitComposition,
    RecommendationFeedback,
    RecommendationResult,
)


def _public_compositions() -> QuerySet[OutfitComposition]:
    """검증을 통과해 사용자에게 노출 가능한 카드만 반환한다."""
    return (
        OutfitComposition.objects.filter(status=OutfitComposition.Status.VALIDATED)
        .select_related("feedback")
        .prefetch_related("items")
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
