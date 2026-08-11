from django.urls import path

from .views import (
    DailyLookTodayView,
    OutfitAnalysisClaimView,
    OutfitAnalysisDetailView,
    OutfitAnalysisHistoryView,
    OutfitAnalysisView,
    OutfitRenderEventStreamView,
    RecommendationCardDetailView,
    RecommendationCardRenderView,
    RecommendationFeedbackView,
    RecommendationHistoryView,
    RecommendationResultDetailView,
)

app_name = "recommend"

urlpatterns = [
    path("looks/today/", DailyLookTodayView.as_view(), name="daily-look-today"),
    path(
        "recommendations/",
        RecommendationHistoryView.as_view(),
        name="recommendation-list",
    ),
    path(
        "recommendations/<uuid:result_id>/",
        RecommendationResultDetailView.as_view(),
        name="recommendation-detail",
    ),
    path(
        "recommendations/<uuid:result_id>/cards/<uuid:card_id>/",
        RecommendationCardDetailView.as_view(),
        name="recommendation-card-detail",
    ),
    path(
        "recommendations/<uuid:result_id>/cards/<uuid:card_id>/feedback/",
        RecommendationFeedbackView.as_view(),
        name="recommendation-feedback",
    ),
    path(
        "recommendations/<uuid:result_id>/cards/<uuid:card_id>/render/",
        RecommendationCardRenderView.as_view(),
        name="recommendation-card-render",
    ),
    path(
        "recommendations/render-jobs/<uuid:job_id>/events/",
        OutfitRenderEventStreamView.as_view(),
        name="outfit-render-events",
    ),
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
