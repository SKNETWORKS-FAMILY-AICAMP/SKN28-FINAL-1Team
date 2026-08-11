from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import ChatSession
from apps.chat.serializers import (
    ChatMessageSerializer,
    ChatSessionCreateSerializer,
    ChatSessionDeriveSerializer,
    ChatSessionSerializer,
    ChatSessionUpdateSerializer,
    GuestClaimSerializer,
)
from apps.chat.services import identity as identity_service
from apps.chat.services import sessions as session_service


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
