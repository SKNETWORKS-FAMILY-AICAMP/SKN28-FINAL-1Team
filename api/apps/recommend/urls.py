from django.urls import path

from .views import OutfitAnalysisView

app_name = "recommend"

urlpatterns = [
    path("outfits/analyze/", OutfitAnalysisView.as_view(), name="outfit-analysis"),
]
