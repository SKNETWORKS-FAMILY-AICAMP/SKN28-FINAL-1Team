from django.urls import path

from .views import (
    OutfitAnalysisDetailView,
    OutfitAnalysisHistoryView,
    OutfitAnalysisView,
)

app_name = "recommend"

urlpatterns = [
    path("outfits/analyze/", OutfitAnalysisView.as_view(), name="outfit-analysis"),
    path(
        "outfits/analyses/",
        OutfitAnalysisHistoryView.as_view(),
        name="outfit-analysis-list",
    ),
    path(
        "outfits/analyses/<uuid:analysis_id>/",
        OutfitAnalysisDetailView.as_view(),
        name="outfit-analysis-detail",
    ),
]
