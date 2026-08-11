from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.wardrobe.views import (
    WardrobeBatchDetailView,
    WardrobeBatchView,
    WardrobeCallbackView,
    WardrobeItemDetailView,
    WardrobeItemListView,
    WardrobeUploadJobView,
    WardrobeUploadView,
    SharedWardrobeViewSet,
)

app_name = "wardrobe"

router = DefaultRouter()
router.register(r"shared-wardrobes", SharedWardrobeViewSet, basename="shared-wardrobes")

urlpatterns = [
    path("wardrobe/batches/", WardrobeBatchView.as_view(), name="batch-list-create"),
    path("wardrobe/batches/<uuid:batch_id>/", WardrobeBatchDetailView.as_view(), name="batch-detail"),
    # 옷장 아이템 등록 (비동기)
    path("wardrobe/uploads/", WardrobeUploadView.as_view(), name="upload"),
    path("wardrobe/uploads/<uuid:job_id>/", WardrobeUploadJobView.as_view(), name="upload-job"),
    # 이미지 프로세서 콜백 (내부 토큰 인증)
    path("internal/wardrobe/callback/", WardrobeCallbackView.as_view(), name="callback"),
    # 옷장 아이템 조회·수정·삭제
    path("wardrobe/items/", WardrobeItemListView.as_view(), name="items"),
    path("wardrobe/items/<uuid:item_id>/", WardrobeItemDetailView.as_view(), name="item-detail"),
    
    # ── 공유 옷장 (Shared Wardrobe) ──
    path("", include(router.urls)),
]
