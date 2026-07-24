from django.urls import path

from apps.wardrobe.views import (
    WardrobeCallbackView,
    WardrobeItemDetailView,
    WardrobeItemListView,
    WardrobeUploadJobView,
    WardrobeUploadView,
)

app_name = "wardrobe"

urlpatterns = [
    # 옷장 아이템 등록 (비동기)
    path("wardrobe/uploads/", WardrobeUploadView.as_view(), name="upload"),
    path("wardrobe/uploads/<uuid:job_id>/", WardrobeUploadJobView.as_view(), name="upload-job"),
    # 이미지 프로세서 콜백 (내부 토큰 인증)
    path("internal/wardrobe/callback/", WardrobeCallbackView.as_view(), name="callback"),
    # 옷장 아이템 조회·수정·삭제
    path("wardrobe/items/", WardrobeItemListView.as_view(), name="items"),
    path("wardrobe/items/<uuid:item_id>/", WardrobeItemDetailView.as_view(), name="item-detail"),
]
