"""룩북 등록·조회 API.

플로우(사진 등록)는 캘린더와 같다.
  ① multipart 업로드 → ② 룩북 S3 선업로드 → ③ 옷장 job 생성(PENDING)
  → ④ 큐 enqueue(exclude_categories 포함) → ⑤ 202
  ... ⑨ 옷장 callback → ⑩ 룩북에 아이템 자동 연결(COMPLETED)

옷장 직접 선택 등록은 비동기 단계가 없어 곧바로 201 + COMPLETED다.
"""

from __future__ import annotations

import logging

import redis as redis_lib
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lookbook.serializers import (
    LookbookListQuerySerializer,
    LookbookMetadataUpdateSerializer,
    LookbookPhotoCreateSerializer,
    LookbookPostSerializer,
    LookbookProcessingStatusSerializer,
    LookbookWardrobeCreateSerializer,
)
from apps.lookbook.services import lookbook_service
from apps.wardrobe.services import jobs as wardrobe_jobs

logger = logging.getLogger(__name__)


def _creation_error_response(error: Exception) -> Response | None:
    """등록 계열 API가 공유하는 도메인 오류 → HTTP 응답 매핑."""

    if isinstance(error, lookbook_service.WardrobeItemsNotFoundError):
        return Response(
            {
                "wardrobe_item_ids": [
                    "존재하지 않거나 사용자 소유가 아닌 옷장 아이템이 포함되어 있습니다."
                ]
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(error, lookbook_service.CalendarDateConflictError):
        # 프론트는 여기서 '이 룩으로 그날 기록을 바꿀까요?'를 물은 뒤
        # overwrite_calendar=true로 같은 요청을 다시 보낸다.
        return Response(
            {
                "calendar_date": ["해당 날짜의 캘린더가 이미 존재합니다."],
                "code": "CALENDAR_DATE_CONFLICT",
                "date": error.entry_date.isoformat(),
            },
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(error, lookbook_service.CalendarBusyError):
        return Response(
            {
                "detail": "이미지 처리 중인 캘린더는 교체할 수 없습니다.",
                "code": "CALENDAR_BUSY",
                "status": error.current_status,
            },
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(error, lookbook_service.LookbookStorageError):
        return Response(
            {"detail": "룩북 이미지 저장에 실패했습니다. 잠시 후 다시 시도해주세요."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return None


class LookbookPhotoCreateView(APIView):
    """POST /api/v1/lookbooks/photo/ — 룩 사진 룩북 선등록."""

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = LookbookPhotoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            post = lookbook_service.create_from_photo(
                user=request.user,
                image=data["image"],
                wardrobe_item_ids=data["wardrobe_item_ids"],
                schedule=data["schedule"],
                tpo=data["tpo"],
                hashtags=data["hashtags"],
                calendar_date=data["calendar_date"],
                overwrite_calendar=data["overwrite_calendar"],
            )
        except Exception as error:
            response = _creation_error_response(error)
            if response is None:
                raise
            return response

        try:
            wardrobe_jobs.enqueue(
                post.wardrobe_upload_job,
                # 입은 옷으로 이미 지정한 부위는 사진에서 다시 뽑지 않는다.
                exclude_categories=post.skipped_categories,
            )
        except redis_lib.RedisError:
            logger.exception(
                "옷장 Queue 적재 실패: lookbook_id=%s job_id=%s",
                post.pk,
                post.wardrobe_upload_job_id,
            )
            lookbook_service.mark_queue_enqueue_failed(post)
            return Response(
                {
                    "detail": "처리 대기열 등록에 실패했습니다. 잠시 후 다시 시도해주세요.",
                    "id": str(post.pk),
                    "status": post.status,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            LookbookPostSerializer(post).data,
            status=status.HTTP_202_ACCEPTED,
        )


class LookbookWardrobeCreateView(APIView):
    """POST /api/v1/lookbooks/wardrobe/ — 옷장 아이템 직접 선택 등록."""

    def post(self, request):
        serializer = LookbookWardrobeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            post = lookbook_service.create_from_wardrobe(
                user=request.user,
                wardrobe_item_ids=data["wardrobe_item_ids"],
                schedule=data["schedule"],
                tpo=data["tpo"],
                hashtags=data["hashtags"],
                calendar_date=data["calendar_date"],
                overwrite_calendar=data["overwrite_calendar"],
            )
        except Exception as error:
            response = _creation_error_response(error)
            if response is None:
                raise
            return response

        return Response(
            LookbookPostSerializer(post).data,
            status=status.HTTP_201_CREATED,
        )


class LookbookListView(APIView):
    """GET /api/v1/lookbooks/?hashtag=&status=&limit=&offset= — 내 룩북 목록."""

    def get(self, request):
        query = LookbookListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        queryset = lookbook_service.posts_filtered(
            user=request.user,
            hashtag=params["hashtag"],
            status=params["status"],
        )
        # 피드는 계속 자란다. 전체를 내려 주면 앱이 스크롤 한 번에 수백 건을
        # 받아 presigned URL도 그만큼 만들게 되므로 항상 잘라서 준다.
        total = queryset.count()
        offset = params["offset"]
        limit = params["limit"]
        page = list(queryset[offset : offset + limit])
        next_offset = offset + limit if offset + limit < total else None

        return Response(
            {
                "count": total,
                "next_offset": next_offset,
                "results": LookbookPostSerializer(page, many=True).data,
            }
        )


class LookbookDetailView(APIView):
    """내 룩북 상세 조회·메타데이터 수정·삭제."""

    @staticmethod
    def _get_post(*, user, lookbook_id):
        return get_object_or_404(
            lookbook_service.posts_for_user(user=user),
            pk=lookbook_id,
        )

    def get(self, request, lookbook_id):
        post = self._get_post(user=request.user, lookbook_id=lookbook_id)
        return Response(LookbookPostSerializer(post).data)

    def patch(self, request, lookbook_id):
        """PATCH /api/v1/lookbooks/{lookbook_id}/ — 일정·TPO·해시태그 수정."""

        post = self._get_post(user=request.user, lookbook_id=lookbook_id)
        serializer = LookbookMetadataUpdateSerializer(
            post,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        post = serializer.save()
        return Response(LookbookPostSerializer(post).data)

    def delete(self, request, lookbook_id):
        """DELETE /api/v1/lookbooks/{lookbook_id}/ — 종료된 룩북 삭제."""

        try:
            lookbook_service.delete_post(
                user=request.user,
                lookbook_id=lookbook_id,
            )
        except lookbook_service.LookbookNotFoundError:
            return Response(
                {"detail": "룩북을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except lookbook_service.LookbookDeletionConflictError as exc:
            return Response(
                {"detail": str(exc), "status": exc.current_status},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LookbookProcessingStatusView(APIView):
    """GET /api/v1/lookbooks/{lookbook_id}/processing-status/ — 프론트 폴링용."""

    def get(self, request, lookbook_id):
        post = get_object_or_404(
            lookbook_service.processing_statuses_for_user(user=request.user),
            pk=lookbook_id,
        )
        return Response(LookbookProcessingStatusSerializer(post).data)
