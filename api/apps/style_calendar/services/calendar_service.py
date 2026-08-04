"""캘린더 생성·조회·수정·삭제 비즈니스 로직."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, QuerySet

from apps.style_calendar.contracts import CalendarSourceType, CalendarStatus
from apps.style_calendar.models import (
    CalendarEntry,
    CalendarItem,
    CalendarWardrobeItem,
)
from apps.wardrobe.models import WardrobeItem

if TYPE_CHECKING:
    from apps.users.models import User


class WardrobeItemsNotFoundError(Exception):
    """요청 사용자가 소유하지 않은 옷장 아이템이 포함된 경우."""


class CalendarDateConflictError(Exception):
    """사용자의 해당 날짜 캘린더가 이미 존재하는 경우."""


def entries_for_user(*, user) -> QuerySet[CalendarEntry]:
    """사용자 소유 캘린더와 조회 응답에 필요한 하위 데이터를 반환한다."""

    return CalendarEntry.objects.filter(user=user).prefetch_related(
        Prefetch(
            "wardrobe_links",
            queryset=CalendarWardrobeItem.objects.order_by("sort_order", "created_at"),
        ),
        Prefetch(
            "items",
            queryset=CalendarItem.objects.order_by("sort_order", "created_at"),
        ),
    )


def entries_in_period(
    *,
    user,
    start_date: date,
    end_date: date,
) -> QuerySet[CalendarEntry]:
    """시작일과 종료일을 모두 포함하는 사용자 캘린더 목록을 반환한다."""

    return entries_for_user(user=user).filter(
        date__gte=start_date,
        date__lte=end_date,
    )


def _wardrobe_snapshot(item: WardrobeItem) -> dict[str, object]:
    """옷장 데이터 변경과 무관하게 캘린더에 남길 연결 시점 정보."""

    return {
        "id": str(item.pk),
        "s3_key": item.s3_key,
        "item_name": item.item_name,
        "category_large": item.category_large,
        "category_small": item.category_small,
        "tags": {
            "season": list(item.season),
            "style": list(item.style),
            "color": item.color,
            "pattern": item.pattern,
            "fit": item.fit,
            "material": item.material,
            "sleeve": item.sleeve,
            "length": item.length,
            "usage": list(item.usage),
            "layer_role": item.layer_role,
            "layer_order": item.layer_order,
        },
    }


def create_from_wardrobe(
    *,
    user: User,
    entry_date: date,
    wardrobe_item_ids: Sequence[UUID],
    schedule: str,
    tpo: list[str],
    hashtags: list[str],
) -> CalendarEntry:
    """사용자 소유 옷장 아이템을 직접 선택해 완료 상태 캘린더를 만든다."""

    owned_items = WardrobeItem.objects.filter(
        user=user,
        pk__in=wardrobe_item_ids,
    )
    item_by_id = {item.pk: item for item in owned_items}
    if len(item_by_id) != len(wardrobe_item_ids):
        raise WardrobeItemsNotFoundError

    ordered_items = [item_by_id[item_id] for item_id in wardrobe_item_ids]

    try:
        with transaction.atomic():
            entry = CalendarEntry.objects.create(
                user=user,
                date=entry_date,
                source_type=CalendarSourceType.WARDROBE_SELECTED.value,
                image_s3_key=ordered_items[0].s3_key,
                schedule=schedule,
                tpo=tpo,
                hashtags=hashtags,
                status=CalendarStatus.COMPLETED.value,
            )
            CalendarWardrobeItem.objects.bulk_create(
                [
                    CalendarWardrobeItem(
                        calendar=entry,
                        wardrobe_item=item,
                        sort_order=sort_order,
                        snapshot=_wardrobe_snapshot(item),
                    )
                    for sort_order, item in enumerate(ordered_items)
                ]
            )
    except IntegrityError as exc:
        cause = getattr(exc, "__cause__", None)
        diag = getattr(cause, "diag", None)
        if getattr(diag, "constraint_name", None) == "uq_calendar_user_date":
            raise CalendarDateConflictError from exc
        raise

    return entries_for_user(user=user).get(pk=entry.pk)
