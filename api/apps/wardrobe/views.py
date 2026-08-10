"""옷장 아이템 등록 API.

플로우 (설계 문서 2-1):
  ① 업로드(multipart) → ② S3 선업로드 → ③ job 생성(PENDING)
  → ④ 큐 enqueue → ⑤ 202(job_id) ... ⑨ 콜백(멱등) → ⑩ 저장+벡터 upsert
  → ⑫ 사용자 확인·수정 후 확정
"""
from __future__ import annotations

import logging

import redis as redis_lib
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.lookbook.services import lookbook_service
from apps.style_calendar.services import calendar_service

from .models import WardrobeItem, WardrobeUploadJob
from .permissions import HasInternalToken
from .serializers import (
    CallbackSerializer,
    WardrobeItemSerializer,
    WardrobeItemUpdateSerializer,
    WardrobeJobSerializer,
    WardrobeUploadSerializer,
)
from .services import jobs, storage, vectors

logger = logging.getLogger(__name__)


class WardrobeUploadView(APIView):
    """POST /api/v1/wardrobe/uploads/ — 사진 접수 → 비동기 처리 시작.

    이미지 바이너리는 여기서 S3에 선업로드하고, 큐에는 참조(S3 키)만 넣는다.
    202와 job_id를 반환하며 프론트는 GET /wardrobe/uploads/{job_id}/ 로 폴링한다.
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = WardrobeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]

        job = WardrobeUploadJob(user=request.user)
        key = storage.original_key(request.user.pk, job.pk, image.name)
        try:
            storage.upload_fileobj(image, key, image.content_type)
        except Exception:  # noqa: BLE001
            logger.exception("원본 S3 업로드 실패: user=%s", request.user.pk)
            return Response(
                {"detail": "이미지 저장소 업로드에 실패했습니다. 잠시 후 다시 시도해주세요."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        job.source_s3_key = key
        job.save()

        try:
            jobs.enqueue(job)
        except redis_lib.RedisError:
            # 큐 장애 — 원본은 S3에 남아 있으므로 job을 FAILED로 마킹하고 안내
            logger.exception("job enqueue 실패: job=%s", job.pk)
            job.status = WardrobeUploadJob.Status.FAILED
            job.error_message = "처리 큐 적재 실패"
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error_message", "finished_at"])
            return Response(
                {"detail": "처리 대기열 등록에 실패했습니다. 잠시 후 다시 시도해주세요."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"job_id": str(job.pk), "status": job.status},
            status=status.HTTP_202_ACCEPTED,
        )


class WardrobeUploadJobView(APIView):
    """GET /api/v1/wardrobe/uploads/{job_id}/ — job 상태·결과 조회 (프론트 폴링)."""

    def get(self, request, job_id):
        job = get_object_or_404(
            WardrobeUploadJob.objects.prefetch_related("items"),
            pk=job_id, user=request.user,
        )
        return Response(WardrobeJobSerializer(job).data)


class WardrobeCallbackView(APIView):
    """POST /api/v1/internal/wardrobe/callback/ — 이미지 프로세서 처리 결과 수신.

    - 인증: X-Internal-Token (사용자 JWT 아님)
    - 멱등: 이미 DONE/FAILED인 job은 재처리 없이 200 (프로세서 재시도 안전)
    - 벡터는 DB 커밋 후 Qdrant에 best-effort upsert (실패해도 콜백은 성공)
    """

    authentication_classes: list = []
    permission_classes = [HasInternalToken]

    def post(self, request):
        serializer = CallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            job = (
                WardrobeUploadJob.objects.select_for_update()
                .filter(pk=data["job_id"])
                .first()
            )
            if job is None:
                return Response(
                    {"detail": "job을 찾을 수 없습니다."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if job.status in (
                WardrobeUploadJob.Status.DONE,
                WardrobeUploadJob.Status.FAILED,
            ):
                # 멱등: 중복 콜백은 무시
                return Response({"detail": "이미 처리된 job입니다.", "job_id": str(job.pk)})

            if data["status"] == "failed":
                job.status = WardrobeUploadJob.Status.FAILED
                job.error_message = data.get("error", "")
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "error_message", "finished_at"])
                # 한 job이 캘린더와 룩북 양쪽에 걸려 있을 수 있다 (룩북에서
                # '캘린더에도 기록'을 켠 경우 같은 사진을 두 번 처리하지 않으려고
                # job을 공유한다). 걸린 쪽이 없으면 각 함수가 조용히 반환한다.
                calendar_service.apply_wardrobe_job_failure(job=job)
                lookbook_service.apply_wardrobe_job_failure(job=job)
                return Response({"job_id": str(job.pk), "status": job.status})

            created: list[tuple[WardrobeItem, list, list]] = []
            for it in data["items"]:
                image_vec = it.pop("image_vector", [])
                text_vec = it.pop("text_vector", [])
                item = WardrobeItem.objects.create(
                    user_id=job.user_id,
                    job=job,
                    embedding_version=vectors.EMBEDDING_VERSION if image_vec else "",
                    **it,
                )
                created.append((item, image_vec, text_vec))

            job.status = WardrobeUploadJob.Status.DONE
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "finished_at"])
            created_wardrobe_items = [item for item, _, _ in created]
            calendar_service.apply_wardrobe_job_success(
                job=job,
                created_items=created_wardrobe_items,
            )
            lookbook_service.apply_wardrobe_job_success(
                job=job,
                created_items=created_wardrobe_items,
            )

        # DB 커밋 후 파생 저장소 반영 (실패해도 embedding_version으로 재색인 가능)
        for item, image_vec, text_vec in created:
            ok = vectors.upsert_item(item, image_vec, text_vec)
            if not ok and item.embedding_version:
                item.embedding_version = ""
                item.save(update_fields=["embedding_version"])

        return Response(
            {"job_id": str(job.pk), "status": job.status, "num_items": len(created)},
            status=status.HTTP_201_CREATED,
        )


class WardrobeItemListView(APIView):
    """GET /api/v1/wardrobe/items/ — 내 옷장 아이템 목록.

    쿼리 파라미터: category_large, confirmed(true|false)
    """

    def get(self, request):
        qs = WardrobeItem.objects.filter(user=request.user)
        category = request.query_params.get("category_large")
        if category:
            qs = qs.filter(category_large=category)
        confirmed = request.query_params.get("confirmed")
        if confirmed is not None:
            qs = qs.filter(confirmed=confirmed.lower() == "true")
        return Response(WardrobeItemSerializer(qs, many=True).data)


class WardrobeItemDetailView(APIView):
    """PATCH /api/v1/wardrobe/items/{id}/ — 태깅 수정 + 확정 (플로우 ⑫).
    DELETE — 아이템 삭제 (벡터도 함께 제거).
    """

    def patch(self, request, item_id):
        item = get_object_or_404(WardrobeItem, pk=item_id, user=request.user)
        serializer = WardrobeItemUpdateSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        vectors.update_payload(item)  # Qdrant payload 동기화 (best-effort)
        return Response(WardrobeItemSerializer(item).data)

    def delete(self, request, item_id):
        item = get_object_or_404(WardrobeItem, pk=item_id, user=request.user)
        item_pk = item.pk
        item.delete()
        vectors.delete_item(item_pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── 공유 옷장 (Shared Wardrobe) 뷰셋 ─────────────────────
from rest_framework import viewsets
from rest_framework.decorators import action
from .models import SharedWardrobeRoom, SharedWardrobeMember, SharedWardrobeItem
from .serializers import (
    SharedWardrobeRoomSerializer,
    SharedWardrobeMemberSerializer,
    SharedWardrobeItemSerializer,
    SharedWardrobeJoinSerializer,
    SharedWardrobeLeaveSerializer,
    SharedWardrobeItemRegisterSerializer,
)
from .services import shared_wardrobe as shared_service

class SharedWardrobeViewSet(viewsets.ModelViewSet):
    queryset = SharedWardrobeRoom.objects.all()
    serializer_class = SharedWardrobeRoomSerializer

    def get_queryset(self):
        # 내가 참여하고 있는 공유 옷장 방 목록만 필터링하여 조회
        return SharedWardrobeRoom.objects.filter(members__user=self.request.user)

    def create(self, request, *args, **kwargs):
        # 방 개설 API
        title = request.data.get("title")
        if not title:
            return Response({"detail": "방 이름을 입력해 주세요."}, status=status.HTTP_400_BAD_REQUEST)
        
        room = shared_service.create_shared_room(request.user, title)
        serializer = self.get_serializer(room)
        # 방장이므로 역할을 포함하여 응답
        data = serializer.data
        data["role"] = "owner"
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="join")
    def join_room(self, request):
        # 초대코드로 방 참여 API
        serializer = SharedWardrobeJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["invite_code"]
        
        try:
            room = shared_service.join_shared_room(request.user, code)
            return Response({
                "room_id": str(room.pk),
                "title": room.title,
                "status": "joined"
            }, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="refresh-code")
    def refresh_code(self, request, pk=None):
        # 초대코드 24시간 재발급 API
        try:
            room = shared_service.refresh_invite_code(request.user, pk)
            return Response({
                "room_id": str(room.pk),
                "invite_code": room.invite_code,
                "code_expires_at": room.code_expires_at.isoformat()
            }, status=status.HTTP_200_OK)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post", "delete"], url_path="leave")
    def leave_room(self, request, pk=None):
        # 방 탈퇴 API (delete_my_items 파라미터 분기 지원)
        serializer = SharedWardrobeLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delete_my_items = serializer.validated_data["delete_my_items"]
        
        try:
            shared_service.leave_shared_room(request.user, pk, delete_my_items=delete_my_items)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get", "post"], url_path="items")
    def manage_items(self, request, pk=None):
        room = get_object_or_404(SharedWardrobeRoom, pk=pk, members__user=request.user)
        
        if request.method == "GET":
            # 이 공유방의 등록된 옷 목록 조회 API
            items = SharedWardrobeItem.objects.filter(room=room).select_related("wardrobe_item", "registered_by")
            return Response(SharedWardrobeItemSerializer(items, many=True).data)
            
        elif request.method == "POST":
            # 내 개인 옷장의 옷을 이 공유방으로 공유 등록 API
            serializer = SharedWardrobeItemRegisterSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            item_id = serializer.validated_data["wardrobe_item_id"]
            item_status = serializer.validated_data["status"]
            
            try:
                shared_item = shared_service.register_item_to_shared_room(
                    request.user, pk, str(item_id), item_status
                )
                return Response(SharedWardrobeItemSerializer(shared_item).data, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="members")
    def list_members(self, request, pk=None):
        # 이 공유방에 소속된 팀원 목록 조회 API
        room = get_object_or_404(SharedWardrobeRoom, pk=pk, members__user=request.user)
        members = SharedWardrobeMember.objects.filter(room=room).select_related("user")
        return Response(SharedWardrobeMemberSerializer(members, many=True).data)
