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
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import ChatRun, ChatSession
from apps.chat.openapi import (
    CHAT_IDENTITY_GUIDE,
    CHAT_SSE_GUIDE,
    CHAT_TAG,
    CHAT_UUID_GUIDE,
    cursor_parameter,
    path_uuid_parameter,
)
from apps.chat.renderers import ServerSentEventRenderer
from apps.chat.serializers import (
    ChatAttachmentSerializer,
    ChatAttachmentUploadResponseSerializer,
    ChatAttachmentUploadSerializer,
    ChatMessageCreateSerializer,
    ChatMessagePageQuerySerializer,
    ChatMessagePageResponseSerializer,
    ChatMessageSerializer,
    ChatMessageSubmitResponseSerializer,
    ChatMoodAnalysisResponseSerializer,
    ChatMoodDecisionResponseSerializer,
    ChatMoodDecisionSerializer,
    ChatRunSerializer,
    ChatSessionCreateSerializer,
    ChatSessionDeriveSerializer,
    ChatSessionResponseModeUpdateSerializer,
    ChatSessionSearchItemSerializer,
    ChatSessionSearchQuerySerializer,
    ChatSessionSearchResponseSerializer,
    ChatSessionSerializer,
    ChatSessionUpdateSerializer,
    GuestClaimResponseSerializer,
    GuestClaimSerializer,
    GuestIdentityResponseSerializer,
    StylistListResponseSerializer,
)
from apps.chat.services import attachments as attachment_service
from apps.chat.services import history as history_service
from apps.chat.services import identity as identity_service
from apps.chat.services import mood_analysis, response_modes, stylist_catalog
from apps.chat.services import queue as chat_queue
from apps.chat.services import sessions as session_service
from apps.chat.services.events import ChatEvent, ChatEventStore, encode_sse, heartbeat
from apps.chat.services.orchestrator import (
    mark_enqueue_failed,
    submit_message_and_create_run,
)

logger = logging.getLogger(__name__)

_REDIS_STREAM_ID = re.compile(r"^\d+-\d+$")

_SESSION_ID_PARAMETER = path_uuid_parameter(
    name="session_id",
    source="POST /api/v1/chat/sessions/ 응답의 id를 입력합니다.",
    example="11111111-1111-4111-8111-111111111111",
)
_ATTACHMENT_ID_PARAMETER = path_uuid_parameter(
    name="attachment_id",
    source="POST .../attachments/ 응답의 attachment.id를 입력합니다.",
    example="22222222-2222-4222-8222-222222222222",
)
_RUN_ID_PARAMETER = path_uuid_parameter(
    name="run_id",
    source="메시지 전송 또는 사진 무드 분석 응답의 run.id를 입력합니다.",
    example="33333333-3333-4333-8333-333333333333",
)

_SEARCH_QUERY_PARAMETER = OpenApiParameter(
    name="query",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=True,
    description="세션 제목과 저장된 메시지 본문에서 찾을 검색어 (1~100자)",
    examples=[OpenApiExample(name="면접 대화 검색", value="면접")],
)
_SEARCH_LIMIT_PARAMETER = OpenApiParameter(
    name="limit",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    required=False,
    description="한 페이지에서 조회할 세션 수 (1~50, 기본값 20)",
    default=20,
    examples=[OpenApiExample(name="20개 조회", value=20)],
)
_SEARCH_CURSOR_PARAMETER = cursor_parameter(
    description="다음 검색 페이지는 직전 응답의 next_cursor를 그대로 입력합니다. 첫 요청은 비웁니다."
)
_MESSAGE_LIMIT_PARAMETER = OpenApiParameter(
    name="limit",
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    required=False,
    description="한 페이지에서 조회할 메시지 수 (1~100, 기본값 50)",
    default=50,
    examples=[OpenApiExample(name="최근 20개 조회", value=20)],
)
_MESSAGE_CURSOR_PARAMETER = cursor_parameter(
    description="더 오래된 메시지는 직전 응답의 next_cursor를 그대로 입력합니다. 첫 요청은 비웁니다."
)

_SESSION_CREATE_EXAMPLES = [
    OpenApiExample(
        name="옷장 아이템만 사용하는 추천 대화",
        value={"mode": "WARDROBE_BASED", "title": "내 옷장 출근 코디"},
        request_only=True,
    ),
    OpenApiExample(
        name="새 상품을 포함하는 추천 대화",
        value={"mode": "NEW_ITEM", "title": "새로운 데이트 룩"},
        request_only=True,
    ),
]
_MESSAGE_CREATE_EXAMPLE = OpenApiExample(
    name="첫 질문 전송",
    description=(
        "client_message_id는 같은 요청의 중복 저장을 막는 클라이언트 고유값입니다. "
        "재시도할 때는 같은 값을 사용하고 새 질문에는 새 값을 사용합니다."
    ),
    value={
        "content": "이번 주 토요일 성수동 데이트에 입을 코디를 추천해줘",
        "client_message_id": "swagger-message-001",
        "metadata": {"source": "swagger"},
    },
    request_only=True,
)


@extend_schema_view(
    get=extend_schema(
        operation_id="chat_stylist_list",
        tags=[CHAT_TAG],
        summary="선택 가능한 스타일리스트 목록 조회",
        description=(
            "로그인 회원이 선택할 수 있는 스타일리스트를 고정 표시 순서로 "
            "조회합니다. 선택 제한과 최초 기본값, 회원의 마지막 선택값을 함께 "
            "반환하며 내부 전략 가중치와 프롬프트는 노출하지 않습니다."
        ),
        responses={
            200: StylistListResponseSerializer,
            401: OpenApiResponse(description="회원 JWT가 없거나 유효하지 않음"),
        },
    )
)
class StylistListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = stylist_catalog.get_member_stylist_catalog(request.user)
        return Response(StylistListResponseSerializer(payload).data)


class ChatSessionResponseModeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="chat_session_response_mode_update",
        tags=[CHAT_TAG],
        summary="채팅 세션 응답 모드 변경",
        description=(
            "같은 채팅방에서 기본 통합 응답과 스타일리스트별 응답을 전환합니다. "
            "STYLIST 전환은 선택값을 세션과 회원 마지막 선택에 함께 저장합니다. "
            "DEFAULT로 돌아가도 선택값은 삭제하지 않으며 추천 출처 모드인 "
            "WARDROBE_BASED/NEW_ITEM은 변경하지 않습니다."
        ),
        parameters=[_SESSION_ID_PARAMETER],
        request={"application/json": ChatSessionResponseModeUpdateSerializer},
        examples=[
            OpenApiExample(
                name="미니멀·실용형 활성화",
                value={
                    "response_mode": "STYLIST",
                    "selected_persona_ids": ["minimal", "practical"],
                },
                request_only=True,
            ),
            OpenApiExample(
                name="기본 응답으로 복귀",
                value={"response_mode": "DEFAULT"},
                request_only=True,
            ),
        ],
        responses={
            200: ChatSessionSerializer,
            400: OpenApiResponse(description="응답 모드 또는 스타일리스트 선택 검증 실패"),
            401: OpenApiResponse(description="회원 JWT가 없거나 유효하지 않음"),
            404: OpenApiResponse(description="세션이 없거나 현재 회원의 소유가 아님"),
        },
    )
    def patch(self, request, session_id):
        serializer = ChatSessionResponseModeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            session = response_modes.update_session_response_mode(
                user=request.user,
                identity=_identity(request),
                session_id=session_id,
                response_mode=values["response_mode"],
                selected_persona_ids=values.get("selected_persona_ids"),
            )
        except response_modes.ChatResponseModeSessionNotFound as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except response_modes.ChatResponseModeError as exc:
            return Response(
                {"code": exc.code, "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ChatSessionSerializer(session).data)


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


@extend_schema_view(
    post=extend_schema(
        operation_id="chat_guest_identity_create",
        tags=[CHAT_TAG],
        summary="비회원 채팅 시작 또는 게스트 쿠키 갱신",
        description=(
            "비회원이 채팅을 테스트하기 위한 identity를 만들고 HttpOnly 쿠키를 "
            "발급합니다. 같은 Swagger 브라우저에서 다시 호출하면 기존 게스트를 "
            "재사용하고 만료 시각을 갱신합니다. 요청 본문은 없습니다.\n\n"
            f"{CHAT_IDENTITY_GUIDE}"
        ),
        request=None,
        responses={
            200: GuestIdentityResponseSerializer,
            201: GuestIdentityResponseSerializer,
        },
    )
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


@extend_schema_view(
    post=extend_schema(
        operation_id="chat_guest_claim_create",
        tags=[CHAT_TAG],
        summary="게스트 대화와 추천 이력을 회원에게 이전",
        description=(
            "게스트로 대화한 뒤 로그인했을 때 호출합니다. **Authorize에 회원 access "
            "JWT가 있어야 하며**, 같은 브라우저에 게스트 쿠키가 남아 있어야 합니다. "
            "세션·메시지·첨부·추천 결과를 회원 identity로 이전한 뒤 게스트 쿠키를 "
            "삭제합니다."
        ),
        request={"application/json": GuestClaimSerializer},
        examples=[
            OpenApiExample(
                name="게스트 대화 이전 확인",
                value={"confirm": True},
                request_only=True,
            )
        ],
        responses={
            200: GuestClaimResponseSerializer,
            400: OpenApiResponse(description="confirm 값 검증 실패"),
            401: OpenApiResponse(description="회원 JWT 또는 게스트 쿠키가 없음"),
            409: OpenApiResponse(description="게스트가 만료·이전됐거나 쿠키가 유효하지 않음"),
        },
    )
)
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


@extend_schema_view(
    get=extend_schema(
        operation_id="chat_session_list",
        tags=[CHAT_TAG],
        summary="내 채팅 세션 목록 조회",
        description=(
            "현재 회원 또는 게스트 identity가 소유한 삭제되지 않은 대화를 최근 수정 "
            "순으로 조회합니다.\n\n"
            f"{CHAT_IDENTITY_GUIDE}"
        ),
        responses={
            200: ChatSessionSerializer(many=True),
            401: OpenApiResponse(description="유효한 회원 JWT 또는 게스트 쿠키가 없음"),
        },
    ),
    post=extend_schema(
        operation_id="chat_session_create",
        tags=[CHAT_TAG],
        summary="추천 모드를 선택해 채팅 세션 생성",
        description=(
            "`WARDROBE_BASED`는 옷장에 저장된 아이템만 사용하고, `NEW_ITEM`은 새 "
            "상품을 포함해 추천합니다. 모드는 생성 후 바꿀 수 없습니다. 생성 시 "
            "모드별 첫 인사가 메시지 1번으로 자동 저장됩니다. title을 비우면 첫 "
            "사용자 질문으로 제목이 자동 생성됩니다."
        ),
        request={"application/json": ChatSessionCreateSerializer},
        examples=_SESSION_CREATE_EXAMPLES,
        responses={
            201: ChatSessionSerializer,
            400: OpenApiResponse(description="추천 모드·제목·페르소나 검증 실패"),
            401: OpenApiResponse(description="유효한 회원 JWT 또는 게스트 쿠키가 없음"),
        },
    ),
)
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
        tags=[CHAT_TAG],
        summary="대화 내용 검색",
        description=(
            "세션 제목과 저장된 메시지 본문을 부분 일치로 검색합니다. "
            "결과는 최근 수정 순이며 `search_match`에 일치 메시지 미리보기가 "
            "포함됩니다. 다음 페이지는 응답의 `next_cursor`를 그대로 cursor에 "
            "복사해 조회합니다. 검색어가 바뀌면 cursor 없이 첫 페이지부터 다시 "
            "조회해야 합니다."
        ),
        parameters=[
            _SEARCH_QUERY_PARAMETER,
            _SEARCH_LIMIT_PARAMETER,
            _SEARCH_CURSOR_PARAMETER,
        ],
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


@extend_schema_view(
    get=extend_schema(
        operation_id="chat_session_retrieve",
        tags=[CHAT_TAG],
        summary="채팅 세션 상세 조회",
        description=f"세션 모드·제목·추천 조건·요약 상태를 조회합니다.\n\n{CHAT_UUID_GUIDE}",
        parameters=[_SESSION_ID_PARAMETER],
        responses={
            200: ChatSessionSerializer,
            404: OpenApiResponse(description="세션이 없거나 현재 identity의 소유가 아님"),
        },
    ),
    patch=extend_schema(
        operation_id="chat_session_title_update",
        tags=[CHAT_TAG],
        summary="채팅 세션 제목 수정",
        description="대화 목록에 표시할 제목만 수정합니다. 추천 모드는 변경되지 않습니다.",
        parameters=[_SESSION_ID_PARAMETER],
        request={"application/json": ChatSessionUpdateSerializer},
        examples=[
            OpenApiExample(
                name="대화 제목 변경",
                value={"title": "토요일 성수동 데이트 룩"},
                request_only=True,
            )
        ],
        responses={
            200: ChatSessionSerializer,
            400: OpenApiResponse(description="제목 검증 실패"),
            404: OpenApiResponse(description="세션이 없거나 현재 identity의 소유가 아님"),
        },
    ),
    delete=extend_schema(
        operation_id="chat_session_delete",
        tags=[CHAT_TAG],
        summary="채팅 세션 삭제",
        description="대화를 소프트 삭제합니다. 이후 목록·검색·메시지 조회에서 보이지 않습니다.",
        parameters=[_SESSION_ID_PARAMETER],
        responses={
            204: OpenApiResponse(description="삭제 완료"),
            404: OpenApiResponse(description="세션이 없거나 현재 identity의 소유가 아님"),
        },
    ),
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


@extend_schema_view(
    post=extend_schema(
        operation_id="chat_session_derive_create",
        tags=[CHAT_TAG],
        summary="현재 조건을 이어받아 반대 추천 모드 대화 생성",
        description=(
            "현재 대화의 추천 조건·요약·페르소나를 복사하되 추천 모드가 다른 새 "
            "세션을 만듭니다. 원본이 `WARDROBE_BASED`라면 `NEW_ITEM`을, 원본이 "
            "`NEW_ITEM`이라면 `WARDROBE_BASED`를 입력해야 합니다."
        ),
        parameters=[_SESSION_ID_PARAMETER],
        request={"application/json": ChatSessionDeriveSerializer},
        examples=[
            OpenApiExample(
                name="새 상품 포함 모드로 전환",
                value={"mode": "NEW_ITEM", "title": "비슷한 새 상품도 찾아보기"},
                request_only=True,
            ),
            OpenApiExample(
                name="옷장 아이템만 사용하는 모드로 전환",
                value={"mode": "WARDROBE_BASED", "title": "내 옷장으로 다시 추천"},
                request_only=True,
            ),
        ],
        responses={
            201: ChatSessionSerializer,
            400: OpenApiResponse(description="요청값 검증 실패"),
            409: OpenApiResponse(description="원본과 같은 모드이거나 세션 접근 불가"),
        },
    )
)
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


@extend_schema_view(
    get=extend_schema(
        operation_id="chat_message_list_all",
        tags=[CHAT_TAG],
        summary="채팅 세션의 전체 메시지 조회",
        description=(
            "세션에 저장된 첫 인사·사용자·AI 메시지를 sequence 오름차순으로 모두 "
            "반환합니다. 메시지가 많아진 대화는 `/messages/page/` 커서 조회 사용을 "
            "권장합니다."
        ),
        parameters=[_SESSION_ID_PARAMETER],
        responses={
            200: ChatMessageSerializer(many=True),
            404: OpenApiResponse(description="세션이 없거나 현재 identity의 소유가 아님"),
        },
    ),
    post=extend_schema(
        operation_id="chat_message_create",
        tags=[CHAT_TAG],
        summary="사용자 메시지 전송 및 AI 답변 실행 접수",
        description=(
            "사용자 질문을 저장하고 Redis 실행 큐에 AI 답변 작업을 접수합니다. "
            "응답의 `run.id`로 실행 상태를 조회합니다. 첫 사용자 질문이고 세션 제목이 "
            "`새 대화`이면 질문 앞부분으로 제목도 자동 저장됩니다.\n\n"
            "**로컬 테스트 전제:** Redis와 채팅 worker가 실행 중이어야 실제 AI 답변이 "
            "완료됩니다. OpenAI 키가 설정된 환경에서는 실제 API 비용이 발생할 수 "
            "있습니다. Swagger에서는 먼저 run 상태 조회를 반복하는 방식이 가장 "
            "간단합니다."
        ),
        parameters=[_SESSION_ID_PARAMETER],
        request={"application/json": ChatMessageCreateSerializer},
        examples=[_MESSAGE_CREATE_EXAMPLE],
        responses={
            200: ChatMessageSubmitResponseSerializer,
            202: ChatMessageSubmitResponseSerializer,
            400: OpenApiResponse(description="메시지·client_message_id 검증 실패"),
            404: OpenApiResponse(description="세션이 없거나 현재 identity의 소유가 아님"),
            503: OpenApiResponse(description="Redis 채팅 실행 큐를 사용할 수 없음"),
        },
    ),
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
        message, _message_created, run, _run_created = submit_message_and_create_run(
            identity=identity,
            session_id=session_id,
            content=serializer.validated_data["content"],
            client_message_id=serializer.validated_data["client_message_id"],
            metadata=serializer.validated_data.get("metadata", {}),
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
        tags=[CHAT_TAG],
        summary="대화 메시지 페이지 조회",
        description=(
            "첫 요청은 가장 최근 메시지를 반환합니다. next_cursor를 다음 요청에 "
            "전달하면 더 오래된 메시지를 조회하며, 각 응답의 `items`는 시간순입니다. "
            "예를 들어 limit=20으로 첫 페이지를 받은 뒤 반환된 next_cursor 전체를 "
            "cursor 칸에 복사하면 직전 20개를 조회합니다."
        ),
        parameters=[
            _SESSION_ID_PARAMETER,
            _MESSAGE_LIMIT_PARAMETER,
            _MESSAGE_CURSOR_PARAMETER,
        ],
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
        tags=[CHAT_TAG],
        summary="채팅 사진 업로드",
        description=(
            "사진을 비공개 S3에 저장하고 채팅 메시지에 연결합니다. "
            "무드 분석은 시작하지 않으며 `analysis_status`는 `NOT_REQUESTED`입니다. "
            "Swagger의 image 입력에서 로컬 jpeg/png/webp/heic 파일을 고릅니다. "
            "응답의 `attachment.id`는 다음 무드 분석 API에 사용합니다."
        ),
        parameters=[_SESSION_ID_PARAMETER],
        request={"multipart/form-data": ChatAttachmentUploadSerializer},
        examples=[
            OpenApiExample(
                name="채팅 사진과 설명 업로드",
                description="image에는 Swagger UI의 파일 선택 버튼으로 실제 사진을 넣습니다.",
                value={
                    "image": "(binary)",
                    "client_message_id": "swagger-photo-001",
                    "content": "이 사진 같은 차분한 무드로 추천해줘",
                    "metadata": {"source": "swagger"},
                },
                media_type="multipart/form-data",
                request_only=True,
            )
        ],
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
        tags=[CHAT_TAG],
        summary="채팅 사진 무드 분석 요청",
        description=(
            "기존 ChatRun/Redis 워커에 사진 무드 분석을 접수합니다. "
            "먼저 사진 업로드 API를 호출하고 그 응답의 `attachment.id`를 사용합니다. "
            "완료 결과는 run SSE의 `response_message.metadata.mood_analysis`와 "
            "메시지 조회의 `attachment.analysis_result`에서 확인할 수 있습니다. "
            "Swagger에서는 응답의 run.id로 실행 상태를 조회하세요."
        ),
        parameters=[_SESSION_ID_PARAMETER, _ATTACHMENT_ID_PARAMETER],
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
        tags=[CHAT_TAG],
        summary="사진 무드 승인 또는 거절",
        description=(
            "APPROVE는 분석된 표준 스타일·색상·핏을 현재 세션 추천 조건에 "
            "반영하고, REJECT는 분석 기록만 보존한 채 추천 조건에는 반영하지 않습니다. "
            "무드 분석 run이 `SUCCEEDED`가 된 뒤 호출해야 합니다."
        ),
        parameters=[_SESSION_ID_PARAMETER, _ATTACHMENT_ID_PARAMETER],
        request={"application/json": ChatMoodDecisionSerializer},
        examples=[
            OpenApiExample(
                name="분석 무드 승인",
                value={"decision": "APPROVE"},
                request_only=True,
            ),
            OpenApiExample(
                name="분석 무드 거절",
                value={"decision": "REJECT"},
                request_only=True,
            ),
        ],
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


@extend_schema_view(
    get=extend_schema(
        operation_id="chat_run_retrieve",
        tags=[CHAT_TAG],
        summary="AI 답변 또는 사진 분석 실행 상태 조회",
        description=(
            "메시지 전송·사진 무드 분석 응답에서 받은 run.id의 처리 상태를 "
            "조회합니다. `PENDING` → `RUNNING` → `SUCCEEDED`, "
            "`NEEDS_CLARIFICATION` 또는 `FAILED`로 변합니다. `SUCCEEDED`이면 "
            "response_message_id를 확인하고 메시지 조회 API에서 최종 답변을 읽습니다. "
            "Swagger에서 비동기 완료를 확인할 때 권장하는 API입니다."
        ),
        parameters=[_RUN_ID_PARAMETER],
        responses={
            200: ChatRunSerializer,
            404: OpenApiResponse(description="실행이 없거나 현재 identity의 소유가 아님"),
        },
    )
)
class ChatRunDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, run_id):
        return Response(ChatRunSerializer(_owned_run(request, run_id)).data)


@extend_schema_view(
    get=extend_schema(
        operation_id="chat_run_event_stream",
        tags=[CHAT_TAG],
        summary="AI 답변 또는 사진 분석 진행 이벤트 SSE",
        description=(
            "`queued`, `running`, `completed`, `needs_clarification`, `failed` 이벤트를 "
            "`text/event-stream`으로 전달합니다. 끊긴 뒤 재연결할 때 마지막 이벤트 "
            "ID를 `Last-Event-ID` 헤더 또는 `last_event_id` 쿼리에 넣습니다.\n\n"
            f"{CHAT_SSE_GUIDE}"
        ),
        parameters=[
            _RUN_ID_PARAMETER,
            OpenApiParameter(
                name="last_event_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="재연결 시 마지막으로 받은 Redis Stream 이벤트 ID",
                examples=[OpenApiExample(name="처음부터 수신", value="0-0")],
            ),
        ],
        responses={
            (200, "text/event-stream"): OpenApiResponse(
                response=OpenApiTypes.STR,
                description="종료 이벤트까지 유지되는 Server-Sent Events 스트림",
            ),
            404: OpenApiResponse(description="실행이 없거나 현재 identity의 소유가 아님"),
        },
    )
)
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
