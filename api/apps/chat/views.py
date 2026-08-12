from __future__ import annotations

import logging
import re

import redis
from django.conf import settings
from django.db import close_old_connections
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import ChatMessage, ChatRun, ChatSession
from apps.chat.renderers import ServerSentEventRenderer
from apps.chat.serializers import (
    ChatAttachmentSerializer,
    ChatAttachmentUploadResponseSerializer,
    ChatAttachmentUploadSerializer,
    ChatMessageCreateSerializer,
    ChatMessagePageQuerySerializer,
    ChatMessagePageResponseSerializer,
    ChatMessageSerializer,
    ChatMoodAnalysisResponseSerializer,
    ChatMoodDecisionResponseSerializer,
    ChatMoodDecisionSerializer,
    ChatRunSerializer,
    ChatSessionCreateSerializer,
    ChatSessionDeriveSerializer,
    ChatSessionSearchItemSerializer,
    ChatSessionSearchQuerySerializer,
    ChatSessionSearchResponseSerializer,
    ChatSessionSerializer,
    ChatSessionUpdateSerializer,
    GuestClaimSerializer,
)
from apps.chat.services import attachments as attachment_service
from apps.chat.services import history as history_service
from apps.chat.services import identity as identity_service
from apps.chat.services import mood_analysis
from apps.chat.services import queue as chat_queue
from apps.chat.services import sessions as session_service
from apps.chat.services.events import ChatEvent, ChatEventStore, encode_sse, heartbeat
from apps.chat.services.orchestrator import create_run, mark_enqueue_failed

logger = logging.getLogger(__name__)

_REDIS_STREAM_ID = re.compile(r"^\d+-\d+$")


def _guest_token(request) -> str:
    return request.COOKIES.get(settings.CHAT_GUEST_COOKIE_NAME, "")


def _identity(request):
    try:
        identity = identity_service.resolve_identity(
            user=request.user,
            guest_token=_guest_token(request),
        )
        if identity.identity_type == identity.IdentityType.GUEST:
            django_request = getattr(request, "_request", request)
            django_request.chat_guest_cookie_refresh_token = _guest_token(request)
        return identity
    except identity_service.ChatIdentityError as exc:
        raise NotAuthenticated(
            {"code": exc.code, "detail": "유효한 채팅 identity가 필요합니다."}
        ) from exc


def _set_guest_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.CHAT_GUEST_COOKIE_NAME,
        token,
        max_age=int(identity_service.guest_ttl().total_seconds()),
        httponly=True,
        secure=settings.CHAT_GUEST_COOKIE_SECURE,
        samesite=settings.CHAT_GUEST_COOKIE_SAMESITE,
        path="/api/v1/",
    )


def _delete_guest_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.CHAT_GUEST_COOKIE_NAME,
        path="/api/v1/",
        samesite=settings.CHAT_GUEST_COOKIE_SAMESITE,
    )


class GuestIdentityView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        raw_token = _guest_token(request)
        if raw_token:
            try:
                identity = identity_service.get_guest_identity(raw_token, touch=True)
                response = Response(
                    {"identity_id": identity.id, "expires_at": identity.expires_at}
                )
                _set_guest_cookie(response, raw_token)
                return response
            except identity_service.ChatIdentityError:
                pass

        credential = identity_service.issue_guest_identity()
        response = Response(
            {
                "identity_id": credential.identity.id,
                "expires_at": credential.identity.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )
        _set_guest_cookie(response, credential.token)
        return response


class GuestClaimView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GuestClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = _guest_token(request)
        try:
            summary = identity_service.claim_guest_identity(request.user, raw_token)
        except identity_service.ChatIdentityError as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        response = Response(summary.__dict__)
        _delete_guest_cookie(response)
        return response


class ChatSessionListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        identity = _identity(request)
        sessions = ChatSession.objects.filter(
            identity=identity,
            deleted_at__isnull=True,
        )
        return Response(ChatSessionSerializer(sessions, many=True).data)

    def post(self, request):
        identity = _identity(request)
        serializer = ChatSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = session_service.create_session(
            identity=identity,
            **serializer.validated_data,
        )
        return Response(
            ChatSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class ChatSessionSearchView(APIView):
    """세션 제목과 메시지 본문을 소유자 범위에서 검색한다."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="chat_session_search",
        tags=["Chat"],
        summary="대화 내용 검색",
        description=(
            "세션 제목과 저장된 메시지 본문을 부분 일치로 검색합니다. "
            "결과는 최근 수정 순이며 search_match에 일치 메시지 미리보기가 포함됩니다."
        ),
        parameters=[ChatSessionSearchQuerySerializer],
        responses={
            200: ChatSessionSearchResponseSerializer,
            400: OpenApiResponse(description="검색어·limit·cursor 검증 실패"),
        },
    )
    def get(self, request):
        identity = _identity(request)
        serializer = ChatSessionSearchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            page = history_service.search_sessions(
                identity=identity,
                query=values["query"],
                limit=values["limit"],
                cursor=values["cursor"],
            )
        except history_service.ChatHistoryCursorInvalid as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized_query = " ".join(values["query"].split())
        return Response(
            {
                "query": normalized_query,
                "items": ChatSessionSearchItemSerializer(page.items, many=True).data,
                "total_count": page.total_count,
                "next_cursor": page.next_cursor,
                "has_more": page.has_more,
            }
        )


class ChatSessionDetailView(APIView):
    permission_classes = [AllowAny]

    def _session(self, request, session_id):
        identity = _identity(request)
        return get_object_or_404(
            ChatSession,
            pk=session_id,
            identity=identity,
            deleted_at__isnull=True,
        )

    def get(self, request, session_id):
        return Response(ChatSessionSerializer(self._session(request, session_id)).data)

    def patch(self, request, session_id):
        session = self._session(request, session_id)
        serializer = ChatSessionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session.title = serializer.validated_data["title"].strip()
        session.save(update_fields=["title", "updated_at"])
        return Response(ChatSessionSerializer(session).data)

    def delete(self, request, session_id):
        session = self._session(request, session_id)
        session.deleted_at = timezone.now()
        session.save(update_fields=["deleted_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatSessionDeriveView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        identity = _identity(request)
        serializer = ChatSessionDeriveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            derived = session_service.derive_session(
                identity=identity,
                source_session_id=session_id,
                **serializer.validated_data,
            )
        except session_service.ChatSessionError as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            ChatSessionSerializer(derived).data,
            status=status.HTTP_201_CREATED,
        )


class ChatSessionMessageListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        identity = _identity(request)
        session = get_object_or_404(
            ChatSession,
            pk=session_id,
            identity=identity,
            deleted_at__isnull=True,
        )
        return Response(ChatMessageSerializer(session.messages.all(), many=True).data)

    def post(self, request, session_id):
        identity = _identity(request)
        serializer = ChatMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message, _created = session_service.append_message(
            identity=identity,
            session_id=session_id,
            role=ChatMessage.Role.USER,
            content=serializer.validated_data["content"],
            status=ChatMessage.Status.PENDING,
            client_message_id=serializer.validated_data["client_message_id"],
            metadata=serializer.validated_data.get("metadata", {}),
        )
        run, _run_created = create_run(
            identity=identity,
            session_id=session_id,
            request_message_id=message.id,
        )

        if run.status == ChatRun.Status.PENDING:
            try:
                # 같은 client_message_id 재전송이 중복 배달을 만들 수 있지만 ChatRun
                # 상태 전이가 한 번만 성공하므로 워커에서 안전하게 ack된다. 대신 API가
                # enqueue 직전에 죽어 PENDING만 남는 유실 구간을 없앤다.
                chat_queue.enqueue(run)
                enqueued_at = timezone.now()
                ChatRun.objects.filter(
                    pk=run.pk,
                    status=ChatRun.Status.PENDING,
                ).update(enqueued_at=enqueued_at, updated_at=enqueued_at)
                run.enqueued_at = enqueued_at
            except redis.RedisError:
                logger.exception("채팅 실행 큐 적재 실패: run=%s", run.pk)
                run = mark_enqueue_failed(run.pk) or run
                message.refresh_from_db()
                return Response(
                    {
                        "code": "CHAT_QUEUE_UNAVAILABLE",
                        "detail": run.error_message,
                        "message": ChatMessageSerializer(message).data,
                        "run": ChatRunSerializer(run).data,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            try:
                ChatEventStore().publish(
                    run.pk,
                    "queued",
                    {"run_id": str(run.pk), "status": ChatRun.Status.PENDING},
                )
            except redis.RedisError:
                # 실행 작업은 이미 reliable queue에 들어갔다. SSE 시작 이벤트만
                # 놓쳐도 상태 조회와 DB fallback이 있으므로 접수를 실패시키지 않는다.
                logger.warning(
                    "채팅 queued SSE 이벤트 기록 실패: run=%s",
                    run.pk,
                    exc_info=True,
                )

        response_status = (
            status.HTTP_202_ACCEPTED
            if run.status in {ChatRun.Status.PENDING, ChatRun.Status.RUNNING}
            else status.HTTP_200_OK
        )
        return Response(
            {
                "message": ChatMessageSerializer(message).data,
                "run": ChatRunSerializer(run).data,
                "events_url": request.build_absolute_uri(
                    reverse("chat:run-events", kwargs={"run_id": run.pk})
                ),
            },
            status=response_status,
        )


class ChatSessionMessagePageView(APIView):
    """최신 메시지 묶음부터 커서로 과거 메시지를 추가 조회한다."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="chat_session_message_page",
        tags=["Chat"],
        summary="대화 메시지 페이지 조회",
        description=(
            "첫 요청은 가장 최근 메시지를 반환합니다. next_cursor를 다음 요청에 "
            "전달하면 더 오래된 메시지를 조회하며, 각 응답의 items는 시간순입니다."
        ),
        parameters=[ChatMessagePageQuerySerializer],
        responses={
            200: ChatMessagePageResponseSerializer,
            400: OpenApiResponse(description="limit·cursor 검증 실패"),
            404: OpenApiResponse(description="세션이 없거나 요청 identity의 소유가 아님"),
        },
    )
    def get(self, request, session_id):
        identity = _identity(request)
        serializer = ChatMessagePageQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            page = history_service.page_messages(
                identity=identity,
                session_id=session_id,
                limit=values["limit"],
                cursor=values["cursor"],
            )
        except history_service.ChatHistorySessionNotFound as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except history_service.ChatHistoryCursorInvalid as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "items": ChatMessageSerializer(page.items, many=True).data,
                "total_count": page.total_count,
                "next_cursor": page.next_cursor,
                "has_more": page.has_more,
            }
        )


class ChatSessionAttachmentUploadView(APIView):
    """채팅 사진을 저장하고 첨부 전용 사용자 메시지에 연결한다."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        operation_id="chat_session_attachment_create",
        tags=["Chat"],
        summary="채팅 사진 업로드",
        description=(
            "사진을 비공개 S3에 저장하고 채팅 메시지에 연결합니다. "
            "무드 분석은 시작하지 않으며 analysis_status는 NOT_REQUESTED입니다."
        ),
        request=ChatAttachmentUploadSerializer,
        responses={
            200: ChatAttachmentUploadResponseSerializer,
            201: ChatAttachmentUploadResponseSerializer,
            400: OpenApiResponse(description="이미지·요청값 검증 실패"),
            404: OpenApiResponse(description="세션이 없거나 요청 identity의 소유가 아님"),
            409: OpenApiResponse(description="client_message_id가 다른 메시지와 충돌"),
            503: OpenApiResponse(description="채팅 이미지 저장소를 사용할 수 없음"),
        },
    )
    def post(self, request, session_id):
        identity = _identity(request)
        serializer = ChatAttachmentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = attachment_service.upload_photo(
                identity=identity,
                session_id=session_id,
                **serializer.validated_data,
            )
        except attachment_service.ChatAttachmentSessionNotFound as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except attachment_service.ChatAttachmentClientIdConflict as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except attachment_service.ChatAttachmentStorageUnavailable as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": ChatMessageSerializer(result.message).data,
                "attachment": ChatAttachmentSerializer(result.attachment).data,
                "created": result.created,
            },
            status=(
                status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
            ),
        )


class ChatAttachmentMoodAnalysisView(APIView):
    """업로드된 사진의 비동기 무드 분석을 접수한다."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="chat_attachment_mood_analysis_create",
        tags=["Chat"],
        summary="채팅 사진 무드 분석 요청",
        description=(
            "기존 ChatRun/Redis 워커에 사진 무드 분석을 접수합니다. "
            "완료 결과는 run SSE의 response_message.metadata.mood_analysis와 "
            "attachment.analysis_result에서 확인할 수 있습니다."
        ),
        request=None,
        responses={
            200: ChatMoodAnalysisResponseSerializer,
            202: ChatMoodAnalysisResponseSerializer,
            404: OpenApiResponse(
                description="사진이 없거나 요청 identity의 소유가 아님"
            ),
            409: OpenApiResponse(description="현재 상태에서는 분석할 수 없음"),
            503: OpenApiResponse(description="채팅 실행 큐를 사용할 수 없음"),
        },
    )
    def post(self, request, session_id, attachment_id):
        identity = _identity(request)
        try:
            prepared = mood_analysis.prepare_analysis(
                identity=identity,
                session_id=session_id,
                attachment_id=attachment_id,
            )
        except mood_analysis.ChatMoodNotFound as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except mood_analysis.ChatMoodError as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        attachment = prepared.attachment
        run = prepared.run
        if run.status == ChatRun.Status.PENDING:
            try:
                chat_queue.enqueue(run)
                enqueued_at = timezone.now()
                ChatRun.objects.filter(
                    pk=run.pk,
                    status=ChatRun.Status.PENDING,
                ).update(enqueued_at=enqueued_at, updated_at=enqueued_at)
                run.enqueued_at = enqueued_at
            except redis.RedisError:
                logger.exception("사진 무드 분석 큐 적재 실패: run=%s", run.pk)
                run = mark_enqueue_failed(run.pk) or run
                attachment.refresh_from_db()
                return Response(
                    {
                        "code": "CHAT_QUEUE_UNAVAILABLE",
                        "detail": run.error_message,
                        "attachment": ChatAttachmentSerializer(attachment).data,
                        "run": ChatRunSerializer(run).data,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            try:
                ChatEventStore().publish(
                    run.pk,
                    "queued",
                    {"run_id": str(run.pk), "status": ChatRun.Status.PENDING},
                )
            except redis.RedisError:
                logger.warning(
                    "사진 무드 queued SSE 이벤트 기록 실패: run=%s",
                    run.pk,
                    exc_info=True,
                )

        attachment.refresh_from_db()
        response_status = (
            status.HTTP_202_ACCEPTED
            if run.status in {ChatRun.Status.PENDING, ChatRun.Status.RUNNING}
            else status.HTTP_200_OK
        )
        return Response(
            {
                "attachment": ChatAttachmentSerializer(attachment).data,
                "run": ChatRunSerializer(run).data,
                "events_url": request.build_absolute_uri(
                    reverse("chat:run-events", kwargs={"run_id": run.pk})
                ),
            },
            status=response_status,
        )


class ChatAttachmentMoodDecisionView(APIView):
    """분석된 사진 무드의 추천 조건 반영 여부를 한 번 확정한다."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="chat_attachment_mood_decision_create",
        tags=["Chat"],
        summary="사진 무드 승인 또는 거절",
        description=(
            "APPROVE는 분석된 표준 스타일·색상·핏을 현재 세션 추천 조건에 "
            "반영하고, REJECT는 분석 기록만 보존한 채 추천 조건에는 반영하지 않습니다."
        ),
        request=ChatMoodDecisionSerializer,
        responses={
            200: ChatMoodDecisionResponseSerializer,
            400: OpenApiResponse(description="decision 값 검증 실패"),
            404: OpenApiResponse(
                description="사진이 없거나 요청 identity의 소유가 아님"
            ),
            409: OpenApiResponse(
                description="분석 미완료 또는 이미 반대 결정으로 확정됨"
            ),
        },
    )
    def post(self, request, session_id, attachment_id):
        identity = _identity(request)
        serializer = ChatMoodDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = mood_analysis.decide_mood(
                identity=identity,
                session_id=session_id,
                attachment_id=attachment_id,
                decision=serializer.validated_data["decision"],
            )
        except mood_analysis.ChatMoodNotFound as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except mood_analysis.ChatMoodError as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {
                "attachment": ChatAttachmentSerializer(result.attachment).data,
                "changed": result.changed,
                "applied": result.applied,
                "context_state": result.session.context_state,
            }
        )


def _owned_run(request, run_id) -> ChatRun:
    identity = _identity(request)
    return get_object_or_404(
        ChatRun.objects.select_related("response_message"),
        pk=run_id,
        session__identity=identity,
        session__deleted_at__isnull=True,
    )


def _terminal_event(run: ChatRun) -> ChatEvent | None:
    event_type = {
        ChatRun.Status.SUCCEEDED: "completed",
        ChatRun.Status.NEEDS_CLARIFICATION: "needs_clarification",
        ChatRun.Status.FAILED: "failed",
    }.get(run.status)
    if event_type is None:
        return None
    data = {
        "run_id": str(run.pk),
        "status": run.status,
        "response_message": (
            ChatMessageSerializer(run.response_message).data
            if run.response_message_id
            else None
        ),
        "error": (
            {"code": run.error_code, "message": run.error_message}
            if run.status == ChatRun.Status.FAILED
            else None
        ),
    }
    return ChatEvent(id="", event=event_type, data=data)


class ChatRunDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, run_id):
        return Response(ChatRunSerializer(_owned_run(request, run_id)).data)


class ChatRunEventStreamView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [ServerSentEventRenderer]

    def get(self, request, run_id):
        run = _owned_run(request, run_id)
        requested_cursor = request.headers.get(
            "Last-Event-ID"
        ) or request.query_params.get("last_event_id", "")
        cursor = (
            requested_cursor if _REDIS_STREAM_ID.fullmatch(requested_cursor) else "0-0"
        )
        store = ChatEventStore()

        def stream():
            nonlocal cursor
            yield f"retry: {settings.CHAT_SSE_RETRY_MILLISECONDS}\n\n"
            try:
                replay = store.read(
                    run.pk,
                    last_event_id=cursor,
                    block_milliseconds=0,
                )
            except redis.RedisError:
                logger.warning("채팅 SSE 재생 실패: run=%s", run.pk, exc_info=True)
                terminal = _terminal_event(run)
                if terminal is not None:
                    yield encode_sse(terminal)
                else:
                    yield 'event: stream_error\ndata: {"retryable":true}\n\n'
                return

            for event in replay:
                cursor = event.id
                yield encode_sse(event)
                if event.terminal:
                    return

            terminal = _terminal_event(run)
            if terminal is not None:
                yield encode_sse(terminal)
                return

            while True:
                try:
                    events = store.read(run.pk, last_event_id=cursor)
                except redis.RedisError:
                    logger.warning("채팅 SSE 읽기 실패: run=%s", run.pk, exc_info=True)
                    yield 'event: stream_error\ndata: {"retryable":true}\n\n'
                    return
                if events:
                    for event in events:
                        cursor = event.id
                        yield encode_sse(event)
                        if event.terminal:
                            return
                    continue

                # 이벤트 publish만 실패한 경우에도 PostgreSQL의 최종 상태로 스트림을
                # 끝낼 수 있다. 블로킹 동안 장시간 열린 DB 연결은 정리한다.
                close_old_connections()
                current = ChatRun.objects.select_related("response_message").get(
                    pk=run.pk
                )
                terminal = _terminal_event(current)
                if terminal is not None:
                    yield encode_sse(terminal)
                    return
                yield heartbeat()

        response = StreamingHttpResponse(stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response
