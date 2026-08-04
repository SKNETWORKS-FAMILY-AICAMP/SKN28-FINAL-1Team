"""캘린더 생성·조회·수정·삭제 비즈니스 로직."""

from __future__ import annotations

from datetime import date

from django.db.models import Prefetch, QuerySet

from apps.style_calendar.models import (
    CalendarEntry,
    CalendarItem,
    CalendarWardrobeItem,
)


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
