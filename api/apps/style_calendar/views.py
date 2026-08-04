"""스타일 캘린더 조회 API."""

from __future__ import annotations

import logging

import redis as redis_lib
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.style_calendar.serializers import (
    CalendarCallbackSerializer,
    CalendarDateQuerySerializer,
    CalendarEntrySerializer,
    CalendarMetadataUpdateSerializer,
    CalendarPeriodQuerySerializer,
    CalendarPhotoCreateSerializer,
    CalendarWardrobeCreateSerializer,
)
from apps.style_calendar.services import calendar_service
from apps.style_calendar.services import callback as calendar_callback
from apps.style_calendar.services import queue as calendar_queue
from apps.wardrobe.permissions import HasInternalToken

logger = logging.getLogger(__name__)


class CalendarCallbackView(APIView):
    """POST /api/v1/internal/calendars/{calendar_id}/callback/."""

    authentication_classes = ()
    permission_classes = (HasInternalToken,)

    def post(self, request, calendar_id):
        serializer = CalendarCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["calendar_id"] != calendar_id:
            return Response(
                {"calendar_id": ["URL의 calendar_id와 요청 본문이 일치하지 않습니다."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = calendar_callback.apply_callback(
                calendar_id=calendar_id,
                data=data,
            )
        except calendar_callback.CalendarCallbackNotFoundError:
            return Response(
                {"detail": "캘린더를 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except calendar_callback.CalendarCallbackConflictError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except calendar_callback.CalendarCallbackStorageKeyError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            "calendar_id": str(result.entry.pk),
            "status": result.entry.status,
            "num_items": result.created_items,
            "duplicate": result.duplicate,
        }
        return Response(response_data)


class CalendarPhotoCreateView(APIView):
    """POST /api/v1/calendars/photo/ — 사용자 사진 캘린더 선등록."""

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = CalendarPhotoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            entry = calendar_service.create_from_photo(
                user=request.user,
                image=data["image"],
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
        except calendar_service.CalendarStorageError:
            return Response(
                {"detail": "캘린더 이미지 저장에 실패했습니다. 잠시 후 다시 시도해주세요."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            calendar_queue.enqueue(entry)
        except (redis_lib.RedisError, calendar_queue.CalendarQueueConfigurationError):
            logger.exception("캘린더 Queue 적재 실패: calendar_id=%s", entry.pk)
            calendar_service.mark_queue_enqueue_failed(entry)
            return Response(
                {
                    "detail": "처리 대기열 등록에 실패했습니다. 잠시 후 다시 시도해주세요.",
                    "id": str(entry.pk),
                    "status": entry.status,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            CalendarEntrySerializer(entry).data,
            status=status.HTTP_202_ACCEPTED,
        )


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
        except calendar_service.CalendarStorageError:
            return Response(
                {"detail": "캘린더 이미지 저장에 실패했습니다. 잠시 후 다시 시도해주세요."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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
