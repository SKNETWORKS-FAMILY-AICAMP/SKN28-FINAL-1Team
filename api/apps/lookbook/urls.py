from django.urls import path

from apps.lookbook.views import (
    LookbookDetailView,
    LookbookListView,
    LookbookPhotoCreateView,
    LookbookProcessingStatusView,
    LookbookWardrobeCreateView,
)

app_name = "lookbook"

urlpatterns = [
    path(
        "lookbooks/photo/",
        LookbookPhotoCreateView.as_view(),
        name="lookbook-photo-create",
    ),
    path(
        "lookbooks/wardrobe/",
        LookbookWardrobeCreateView.as_view(),
        name="lookbook-wardrobe-create",
    ),
    path("lookbooks/", LookbookListView.as_view(), name="lookbook-list"),
    path(
        "lookbooks/<uuid:lookbook_id>/",
        LookbookDetailView.as_view(),
        name="lookbook-detail",
    ),
    path(
        "lookbooks/<uuid:lookbook_id>/processing-status/",
        LookbookProcessingStatusView.as_view(),
        name="lookbook-processing-status",
    ),
]
