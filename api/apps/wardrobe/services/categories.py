"""개인 옷장 사용자 카테고리 조회·변경 서비스."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q

from apps.wardrobe import taxonomy as T
from apps.wardrobe.models import WardrobeCategory, WardrobeItem

User = get_user_model()
VIRTUAL_CATEGORY_NAMES = {"전체", "미분류"}
RESERVED_NORMALIZED_NAMES = {
    WardrobeCategory.normalize_name(name)[1]
    for name in [*T.CATEGORY_LARGE, *VIRTUAL_CATEGORY_NAMES]
}


@dataclass(frozen=True)
class CategoryServiceError(Exception):
    code: str
    detail: str

    def __str__(self) -> str:
        return self.detail


def normalize_and_validate_name(value: str) -> tuple[str, str]:
    display_name, normalized_name = WardrobeCategory.normalize_name(value)
    if not display_name:
        raise CategoryServiceError(
            "CATEGORY_NAME_REQUIRED",
            "카테고리 이름을 입력해 주세요.",
        )
    if len(display_name) > 30:
        raise CategoryServiceError(
            "CATEGORY_NAME_TOO_LONG",
            "카테고리 이름은 30자 이하여야 합니다.",
        )
    if normalized_name in RESERVED_NORMALIZED_NAMES:
        raise CategoryServiceError(
            "CATEGORY_NAME_RESERVED",
            "기본 카테고리와 전체·미분류 이름은 사용할 수 없습니다.",
        )
    return display_name, normalized_name


def category_payloads(user) -> dict[str, list]:
    """기본 카테고리와 사용자의 사용자 카테고리를 개수와 함께 반환한다."""

    closet_filter = Q(added_to_closet_at__isnull=False)
    system_counts = {
        row["category_large"]: row["item_count"]
        for row in WardrobeItem.objects.filter(user=user)
        .filter(closet_filter)
        .values("category_large")
        .annotate(item_count=Count("id"))
    }
    system_categories = [
        {
            "id": f"system:{name}",
            "type": "SYSTEM",
            "name": name,
            "position": position,
            "item_count": system_counts.get(name, 0),
            "mutable": False,
        }
        for position, name in enumerate(T.CATEGORY_LARGE)
    ]

    custom_categories = list(
        WardrobeCategory.objects.filter(user=user).annotate(
            item_count=Count(
                "item_links",
                filter=Q(
                    item_links__wardrobe_item__user=user,
                    item_links__wardrobe_item__added_to_closet_at__isnull=False,
                ),
                distinct=True,
            )
        )
    )
    return {
        "system_categories": system_categories,
        "custom_categories": custom_categories,
    }


@transaction.atomic
def create_category(*, user, name: str) -> WardrobeCategory:
    display_name, normalized_name = normalize_and_validate_name(name)
    # position 최댓값 조회와 생성을 직렬화해 동시 요청에도 순서가 겹치지 않게 한다.
    User.objects.select_for_update().only("pk").get(pk=user.pk)
    if WardrobeCategory.objects.filter(
        user=user,
        normalized_name=normalized_name,
    ).exists():
        raise CategoryServiceError(
            "CATEGORY_NAME_DUPLICATE",
            "이미 존재하는 카테고리입니다.",
        )
    max_position = WardrobeCategory.objects.filter(user=user).aggregate(
        value=Max("position")
    )["value"]
    try:
        return WardrobeCategory.objects.create(
            user=user,
            name=display_name,
            position=0 if max_position is None else max_position + 1,
        )
    except IntegrityError as exc:
        raise CategoryServiceError(
            "CATEGORY_NAME_DUPLICATE",
            "이미 존재하는 카테고리입니다.",
        ) from exc


@transaction.atomic
def rename_category(*, category: WardrobeCategory, name: str) -> WardrobeCategory:
    display_name, normalized_name = normalize_and_validate_name(name)
    if (
        WardrobeCategory.objects.filter(
            user_id=category.user_id,
            normalized_name=normalized_name,
        )
        .exclude(pk=category.pk)
        .exists()
    ):
        raise CategoryServiceError(
            "CATEGORY_NAME_DUPLICATE",
            "이미 존재하는 카테고리입니다.",
        )
    category.name = display_name
    try:
        category.save(update_fields=["name", "normalized_name", "updated_at"])
    except IntegrityError as exc:
        raise CategoryServiceError(
            "CATEGORY_NAME_DUPLICATE",
            "이미 존재하는 카테고리입니다.",
        ) from exc
    return category
