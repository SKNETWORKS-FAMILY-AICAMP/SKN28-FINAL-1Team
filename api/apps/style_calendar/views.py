"""스타일 캘린더 조회 API."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.style_calendar.serializers import (
    CalendarDateQuerySerializer,
    CalendarEntrySerializer,
    CalendarMetadataUpdateSerializer,
    CalendarPeriodQuerySerializer,
    CalendarWardrobeCreateSerializer,
)
from apps.style_calendar.services import calendar_service


class CalendarWardrobeCreateView(APIView):
    """POST /api/v1/calendars/wardrobe/ — 옷장 아이템 직접 선택 등록."""

    def post(self, request):
        serializer = CalendarWardrobeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            entry = calendar_service.create_from_wardrobe(
                user=request.user,
                entry_date=data["date"],
                wardrobe_item_ids=data["wardrobe_item_ids"],
                schedule=data["schedule"],
                tpo=data["tpo"],
                hashtags=data["hashtags"],
            )
        except calendar_service.WardrobeItemsNotFoundError:
            return Response(
                {
                    "wardrobe_item_ids": [
                        "존재하지 않거나 사용자 소유가 아닌 옷장 아이템이 포함되어 있습니다."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except calendar_service.CalendarDateConflictError:
            return Response(
                {"date": ["해당 날짜의 캘린더가 이미 존재합니다."]},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            CalendarEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )


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
    """내 캘린더 상세 조회와 메타데이터 수정."""

    @staticmethod
    def _get_entry(*, user, calendar_id):
        return get_object_or_404(
            calendar_service.entries_for_user(user=user),
            pk=calendar_id,
        )

    def get(self, request, calendar_id):
        entry = self._get_entry(user=request.user, calendar_id=calendar_id)
        return Response(CalendarEntrySerializer(entry).data)

    def patch(self, request, calendar_id):
        """PATCH /api/v1/calendars/{calendar_id}/ — 일정·TPO·해시태그 수정."""

        entry = self._get_entry(user=request.user, calendar_id=calendar_id)
        serializer = CalendarMetadataUpdateSerializer(
            entry,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        return Response(CalendarEntrySerializer(entry).data)
