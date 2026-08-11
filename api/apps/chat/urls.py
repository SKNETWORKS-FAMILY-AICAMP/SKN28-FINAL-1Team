from django.urls import path

from apps.chat.views import (
    ChatRunDetailView,
    ChatRunEventStreamView,
    ChatSessionDeriveView,
    ChatSessionDetailView,
    ChatSessionListCreateView,
    ChatSessionMessageListView,
    GuestClaimView,
    GuestIdentityView,
)

app_name = "chat"

urlpatterns = [
    path("chat/guest/", GuestIdentityView.as_view(), name="guest-identity"),
    path("chat/guest/claim/", GuestClaimView.as_view(), name="guest-claim"),
    path("chat/sessions/", ChatSessionListCreateView.as_view(), name="session-list"),
    path(
        "chat/sessions/<uuid:session_id>/",
        ChatSessionDetailView.as_view(),
        name="session-detail",
    ),
    path(
        "chat/sessions/<uuid:session_id>/derive/",
        ChatSessionDeriveView.as_view(),
        name="session-derive",
    ),
    path(
        "chat/sessions/<uuid:session_id>/messages/",
        ChatSessionMessageListView.as_view(),
        name="session-messages",
    ),
    path(
        "chat/runs/<uuid:run_id>/",
        ChatRunDetailView.as_view(),
        name="run-detail",
    ),
    path(
        "chat/runs/<uuid:run_id>/events/",
        ChatRunEventStreamView.as_view(),
        name="run-events",
    ),
]
