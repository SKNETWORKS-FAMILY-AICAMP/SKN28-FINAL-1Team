from django.urls import path

from .views import (
    OutfitAnalysisClaimView,
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
    # <uuid:...> 컨버터가 "claim"과 겹치지는 않지만, 읽는 순서를 위해 먼저 둔다
    path(
        "outfits/analyses/claim/",
        OutfitAnalysisClaimView.as_view(),
        name="outfit-analysis-claim",
    ),
    path(
        "outfits/analyses/<uuid:analysis_id>/",
        OutfitAnalysisDetailView.as_view(),
        name="outfit-analysis-detail",
    ),
]
