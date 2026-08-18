"""개인 옷장 사용자 카테고리 조회·변경 서비스."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q

from apps.wardrobe import taxonomy as T
from apps.wardrobe.models import (
    WardrobeCategory,
    WardrobeItem,
    WardrobeItemCategory,
)

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
    status_code: int = 400

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


def _validate_closet_items(*, user, item_ids: set) -> None:
    """배정 대상이 현재 사용자의 실제 옷장 아이템인지 일괄 검증한다."""

    if not item_ids:
        return
    items = {
        item.pk: item
        for item in WardrobeItem.objects.filter(pk__in=item_ids).only(
            "id",
            "user_id",
            "added_to_closet_at",
        )
    }
    if set(items) != item_ids:
        raise CategoryServiceError(
            "WARDROBE_ITEM_NOT_FOUND",
            "옷장 아이템을 찾을 수 없습니다.",
            404,
        )
    if any(item.user_id != user.pk for item in items.values()):
        raise CategoryServiceError(
            "WARDROBE_ITEM_FORBIDDEN",
            "이 옷장 아이템에 접근할 수 없습니다.",
            403,
        )
    if any(item.added_to_closet_at is None for item in items.values()):
        raise CategoryServiceError(
            "WARDROBE_ITEM_NOT_FOUND",
            "옷장 아이템을 찾을 수 없습니다.",
            404,
        )


def _validate_categories(*, user, category_ids: set) -> None:
    """전체 교체 대상이 모두 현재 사용자의 사용자 카테고리인지 검증한다."""

    if not category_ids:
        return
    categories = {
        category.pk: category
        for category in WardrobeCategory.objects.filter(pk__in=category_ids).only(
            "id",
            "user_id",
        )
    }
    if set(categories) != category_ids:
        raise CategoryServiceError(
            "CATEGORY_NOT_FOUND",
            "카테고리를 찾을 수 없습니다.",
            404,
        )
    if any(category.user_id != user.pk for category in categories.values()):
        raise CategoryServiceError(
            "CATEGORY_FORBIDDEN",
            "이 카테고리에 접근할 수 없습니다.",
            403,
        )


@transaction.atomic
def update_category_items(
    *,
    user,
    category: WardrobeCategory,
    add_item_ids: list,
    remove_item_ids: list,
) -> dict:
    """한 사용자 카테고리의 아이템을 추가·제거하고 실제 변경분을 반환한다."""

    add_ids = set(add_item_ids)
    remove_ids = set(remove_item_ids)
    if add_ids & remove_ids:
        raise CategoryServiceError(
            "CATEGORY_ASSIGNMENT_CONFLICT",
            "같은 옷을 동시에 추가하고 제거할 수 없습니다.",
        )

    # 카테고리 삭제와 배정이 엇갈리지 않도록 대상 행을 잠근다.
    WardrobeCategory.objects.select_for_update().get(pk=category.pk)
    _validate_closet_items(user=user, item_ids=add_ids | remove_ids)

    existing_add_ids = set(
        WardrobeItemCategory.objects.filter(
            category=category,
            wardrobe_item_id__in=add_ids,
        ).values_list("wardrobe_item_id", flat=True)
    )
    actual_add_ids = add_ids - existing_add_ids
    WardrobeItemCategory.objects.bulk_create(
        [
            WardrobeItemCategory(
                wardrobe_item_id=item_id,
                category=category,
            )
            for item_id in actual_add_ids
        ],
        ignore_conflicts=True,
    )

    actual_remove_ids = set(
        WardrobeItemCategory.objects.filter(
            category=category,
            wardrobe_item_id__in=remove_ids,
        ).values_list("wardrobe_item_id", flat=True)
    )
    WardrobeItemCategory.objects.filter(
        category=category,
        wardrobe_item_id__in=actual_remove_ids,
    ).delete()

    item_count = WardrobeItemCategory.objects.filter(
        category=category,
        wardrobe_item__user=user,
        wardrobe_item__added_to_closet_at__isnull=False,
    ).count()
    return {
        "category_id": str(category.pk),
        "added_item_ids": sorted(str(item_id) for item_id in actual_add_ids),
        "removed_item_ids": sorted(str(item_id) for item_id in actual_remove_ids),
        "item_count": item_count,
    }


@transaction.atomic
def replace_item_categories(*, user, item_id, category_ids: list) -> tuple:
    """아이템의 사용자 카테고리 소속을 요청 목록 전체로 교체한다."""

    category_id_set = set(category_ids)
    if len(category_id_set) != len(category_ids):
        raise CategoryServiceError(
            "CATEGORY_IDS_DUPLICATE",
            "카테고리 UUID를 중복해서 보낼 수 없습니다.",
        )

    item = WardrobeItem.objects.filter(pk=item_id).only(
        "id",
        "user_id",
        "added_to_closet_at",
    ).first()
    if item is None:
        raise CategoryServiceError(
            "WARDROBE_ITEM_NOT_FOUND",
            "옷장 아이템을 찾을 수 없습니다.",
            404,
        )
    if item.user_id != user.pk:
        raise CategoryServiceError(
            "WARDROBE_ITEM_FORBIDDEN",
            "이 옷장 아이템에 접근할 수 없습니다.",
            403,
        )
    if item.added_to_closet_at is None:
        raise CategoryServiceError(
            "WARDROBE_ITEM_NOT_FOUND",
            "옷장 아이템을 찾을 수 없습니다.",
            404,
        )

    WardrobeItem.objects.select_for_update().only("id").get(pk=item.pk)
    _validate_categories(user=user, category_ids=category_id_set)

    existing_ids = set(
        WardrobeItemCategory.objects.filter(wardrobe_item=item).values_list(
            "category_id",
            flat=True,
        )
    )
    add_ids = category_id_set - existing_ids
    remove_ids = existing_ids - category_id_set
    WardrobeItemCategory.objects.bulk_create(
        [
            WardrobeItemCategory(
                wardrobe_item=item,
                category_id=category_id,
            )
            for category_id in add_ids
        ],
        ignore_conflicts=True,
    )
    WardrobeItemCategory.objects.filter(
        wardrobe_item=item,
        category_id__in=remove_ids,
    ).delete()

    categories = tuple(
        WardrobeCategory.objects.filter(pk__in=category_id_set).order_by(
            "position",
            "created_at",
            "id",
        )
    )
    return item, categories
