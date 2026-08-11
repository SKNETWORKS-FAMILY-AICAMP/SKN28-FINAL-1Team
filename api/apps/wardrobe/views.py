"""옷장 아이템 등록 API.

플로우 (설계 문서 2-1):
  ① 업로드(multipart) → ② S3 선업로드 → ③ job 생성(PENDING)
  → ④ 큐 enqueue → ⑤ 202(job_id) ... ⑨ 콜백(멱등) → ⑩ 저장+벡터 upsert
  → ⑫ 사용자 확인·수정 후 확정
"""
from __future__ import annotations

import logging

import redis as redis_lib
from django.core.cache import caches
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

        # 로컬 개발 환경일 경우 비동기 AI 프로세서를 우회하여 완료 처리 및 Gemini AI 분석 등록
        if storage.IS_LOCAL:
            import os
            job.status = WardrobeUploadJob.Status.DONE
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "finished_at"])
            
            # 실제 저장된 로컬 파일 경로
            local_path = os.path.join(storage.LOCAL_MEDIA_DIR, key)
            
            # Gemini API를 사용하여 옷 분석
            from .services import gemini
            analysis = gemini.analyze_clothing_image(local_path)
            
            WardrobeItem.objects.create(
                user=request.user,
                job=job,
                item_name=analysis["item_name"],
                category_large=analysis["category_large"],
                category_small=analysis["category_small"],
                color=analysis["color"],
                s3_key=key,
                confirmed=False,
            )
            return Response(
                {"job_id": str(job.pk), "status": job.status},
                status=status.HTTP_202_ACCEPTED,
            )

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
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from .models import SharedWardrobeRoom, SharedWardrobeMember, SharedWardrobeItem
from .serializers import (
    SharedWardrobeRoomSerializer,
    SharedWardrobeMemberSerializer,
    SharedWardrobeItemSerializer,
    SharedWardrobeJoinSerializer,
    SharedWardrobeLeaveSerializer,
    SharedWardrobeItemRegisterSerializer,
    SharedWardrobePreviewSerializer,
    anon_member_label,
)
from .services import shared_wardrobe as shared_service

# @action에 스키마를 명시하지 않으면 drf-spectacular가 뷰셋의 serializer_class
# (SharedWardrobeRoomSerializer)로 폴백해서, Swagger에 엉뚱하게 {"title": "..."}
# 요청 바디가 그려진다. 아래 데코레이터들은 실제 뷰가 받는 직렬화기를 못박는다.


class InvitePreviewThrottle(AnonRateThrottle):
    """비로그인 미리보기 전용 요율 (settings의 invite_preview).

    - scope를 클래스에 박는다: @action의 initkwarg로 throttle_scope를 넘기면
      ViewSet.as_view()가 클래스에 없는 속성이라며 TypeError를 낸다.
    - 카운터는 'throttle' 캐시(Redis)에 저장한다: 기본 LocMemCache는 gunicorn
      워커마다 따로 세어서 실제 허용량이 워커 수만큼 부풀어 오른다.
    """

    scope = "invite_preview"
    cache = caches["throttle"]


@extend_schema(tags=["shared-wardrobe"])
class SharedWardrobeViewSet(viewsets.ModelViewSet):
    queryset = SharedWardrobeRoom.objects.all()
    serializer_class = SharedWardrobeRoomSerializer

    def get_queryset(self):
        # 내가 참여하고 있는 공유 옷장 방 목록만 필터링하여 조회
        return SharedWardrobeRoom.objects.filter(members__user=self.request.user)

    @extend_schema(
        summary="공유 옷장 개설 (개설자가 owner, 6자리 초대코드 동시 발급)",
        request=SharedWardrobeRoomSerializer,
        responses={
            201: OpenApiResponse(
                response=SharedWardrobeRoomSerializer,
                description='기본 필드 + "role": "owner"',
            ),
            400: OpenApiResponse(description="title 누락"),
        },
    )
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

    @extend_schema(
        summary="초대코드로 공유 옷장 참여",
        request=SharedWardrobeJoinSerializer,
        responses={
            200: OpenApiResponse(description='{"room_id", "title", "status": "joined"}'),
            400: OpenApiResponse(description="코드 무효 / 24시간 만료 / 정원(6명) 초과"),
        },
    )
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

    @extend_schema(
        summary="초대코드 24시간 재발급 (방장 전용)",
        request=None,  # 바디 없음 — 방장 여부는 인증 사용자로 판별한다
        responses={
            200: OpenApiResponse(description='{"room_id", "invite_code", "code_expires_at"}'),
            403: OpenApiResponse(description="방장이 아님"),
        },
    )
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

    @extend_schema(
        summary="공유 옷장 탈퇴",
        description=(
            "delete_my_items=true 이면 내가 이 방에 공유한 아이템을 함께 삭제하고, "
            "false 이면 아이템은 방에 남기고 registered_by만 NULL로 바꾼다(기부). "
            "방장이 나가면 joined_at이 가장 빠른 남은 멤버에게 owner가 자동 위임되고, "
            "남은 인원이 0명일 때만 방이 삭제된다."
        ),
        request=SharedWardrobeLeaveSerializer,
        responses={204: OpenApiResponse(description="탈퇴 완료")},
    )
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

    @extend_schema(
        methods=["GET"],
        summary="공유 옷장에 등록된 옷 목록",
        responses=SharedWardrobeItemSerializer(many=True),
    )
    @extend_schema(
        methods=["POST"],
        summary="내 옷을 공유 옷장에 등록",
        description="wardrobe_item_id는 GET /api/v1/wardrobe/items/ 응답의 id(원본 옷 UUID)다.",
        request=SharedWardrobeItemRegisterSerializer,
        responses={
            201: SharedWardrobeItemSerializer,
            400: OpenApiResponse(description="내 옷이 아니거나 이미 등록된 아이템"),
        },
    )
    @extend_schema(
        methods=["DELETE"],
        summary="공유 옷장에서 내 옷 공유 해제 (원본은 보존)",
        description="쿼리 파라미터 또는 JSON 바디로 wardrobe_item_id를 넘길 수 있다.",
        parameters=[
            OpenApiParameter(
                name="wardrobe_item_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
                description="공유를 끊을 원본 옷 UUID",
            )
        ],
        request=None,
        responses={
            204: OpenApiResponse(description="공유 해제 완료 (개인 옷장 원본은 그대로)"),
            400: OpenApiResponse(description="wardrobe_item_id 누락"),
        },
    )
    @action(detail=True, methods=["get", "post", "delete"], url_path="items")
    def items(self, request, pk=None):
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

        elif request.method == "DELETE":
            # 이 공유방에서 내 옷 공유 해제 API
            item_id = request.data.get("wardrobe_item_id") or request.query_params.get("wardrobe_item_id")
            if not item_id:
                return Response({"detail": "wardrobe_item_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
            SharedWardrobeItem.objects.filter(room=room, registered_by=request.user, wardrobe_item_id=item_id).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="초대코드로 공유 옷장 미리보기 (비로그인 열람)",
        description=(
            "초대 링크만 있으면 로그인 없이 방을 둘러볼 수 있는 열람 전용 엔드포인트다.\n\n"
            "- 서버에 아무 레코드도 남기지 않는다 (익명 User·멤버십 생성 안 함 → 정원 6명 카운트에 영향 없음)\n"
            "- 실명·이메일·방 UUID·옷 UUID를 내리지 않는다. 소유자는 가입 순서 기반 익명 라벨로만 표시\n"
            "- 만료된 코드는 200 + expired=true + 빈 items (내용을 노출하지 않는다)\n"
            "- 없는 코드는 404\n"
            "- 초대코드가 곧 열람 권한이 되므로 IP당 분당 20회로 제한한다"
        ),
        parameters=[
            OpenApiParameter(
                name="code",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description="6자리 초대코드",
            )
        ],
        responses={
            200: SharedWardrobePreviewSerializer,
            400: OpenApiResponse(description="code 누락"),
            404: OpenApiResponse(description="유효하지 않은 초대코드"),
        },
        auth=[],  # 인증 불필요 (Swagger에 자물쇠 표시 안 되게)
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="preview",
        permission_classes=[AllowAny],
        # 만료·무효 JWT가 헤더에 남아 있어도 401로 튕기지 않도록 인증을 아예 끈다.
        authentication_classes=[],
        throttle_classes=[InvitePreviewThrottle],
    )
    def preview(self, request):
        code = (request.query_params.get("code") or "").strip().upper()
        if not code:
            return Response({"detail": "code가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        room = SharedWardrobeRoom.objects.filter(invite_code=code).first()
        if not room:
            return Response(
                {"detail": "유효하지 않은 초대코드입니다."}, status=status.HTTP_404_NOT_FOUND
            )

        expired = bool(room.code_expires_at and room.code_expires_at < timezone.now())

        members = list(
            SharedWardrobeMember.objects.filter(room=room)
            .select_related("user")
            .order_by("joined_at")
        )
        # 실명 대신 가입 순서로 라벨을 매긴다. user_id → index 맵을 만들어
        # 아이템 소유자도 같은 인덱스(=같은 아바타 색)로 이어붙인다.
        index_by_user = {m.user_id: i for i, m in enumerate(members)}

        member_count = len(members)
        capacity = shared_service.MAX_MEMBERS

        items_payload = []
        if not expired:
            shared_items = (
                SharedWardrobeItem.objects.filter(room=room)
                .select_related("wardrobe_item")
                .order_by("-created_at")
            )
            for shared_item in shared_items:
                owner_index = index_by_user.get(shared_item.registered_by_id)
                item = shared_item.wardrobe_item
                items_payload.append(
                    {
                        "image_url": storage.presigned_get(item.s3_key),
                        "item_name": item.item_name,
                        "category_large": item.category_large,
                        "color": item.color,
                        "owner_index": owner_index,
                        # 탈퇴 후 기부된 옷은 registered_by가 NULL이라 소유자가 없다
                        "owner_label": anon_member_label(owner_index)
                        if owner_index is not None
                        else None,
                    }
                )

        return Response(
            {
                "title": room.title,
                "member_count": member_count,
                "capacity": capacity,
                "can_join": (not expired) and member_count < capacity,
                "expired": expired,
                "members": [
                    {"index": i, "label": anon_member_label(i), "role": m.role}
                    for i, m in enumerate(members)
                ],
                "items": items_payload,
            }
        )

    @extend_schema(
        summary="공유 옷장 멤버 목록",
        description="응답 배열 순서(joined_at)가 프론트 아바타 색상 매핑의 기준이다.",
        responses=SharedWardrobeMemberSerializer(many=True),
    )
    @action(detail=True, methods=["get"], url_path="members")
    def list_members(self, request, pk=None):
        # 이 공유방에 소속된 팀원 목록 조회 API
        room = get_object_or_404(SharedWardrobeRoom, pk=pk, members__user=request.user)
        members = SharedWardrobeMember.objects.filter(room=room).select_related("user")
        return Response(SharedWardrobeMemberSerializer(members, many=True).data)
