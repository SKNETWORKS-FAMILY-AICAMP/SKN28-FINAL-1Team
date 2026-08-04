"""스타일 캘린더 조회 API."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.style_calendar.serializers import (
    CalendarDateQuerySerializer,
    CalendarEntrySerializer,
    CalendarPeriodQuerySerializer,
)
from apps.style_calendar.services import calendar_service


class CalendarEntryListView(APIView):
    """GET /api/v1/calendars/?start_date=&end_date= — 기간별 내 캘린더."""

    def get(self, request):
        query = CalendarPeriodQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        entries = calendar_service.entries_in_period(
            user=request.user,
            start_date=query.validated_data["start_date"],
            end_date=query.validated_data["end_date"],
        )
        return Response(CalendarEntrySerializer(entries, many=True).data)


class CalendarEntryByDateView(APIView):
    """GET /api/v1/calendars/by-date/?date= — 특정 날짜의 내 캘린더."""

    def get(self, request):
        query = CalendarDateQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        entry = get_object_or_404(
            calendar_service.entries_for_user(user=request.user),
            date=query.validated_data["date"],
        )
        return Response(CalendarEntrySerializer(entry).data)


class CalendarEntryDetailView(APIView):
    """GET /api/v1/calendars/{calendar_id}/ — 내 캘린더 상세."""

    def get(self, request, calendar_id):
        entry = get_object_or_404(
            calendar_service.entries_for_user(user=request.user),
            pk=calendar_id,
        )
        return Response(CalendarEntrySerializer(entry).data)
