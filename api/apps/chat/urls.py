from django.urls import path

from apps.chat.views import (
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
]
