from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import (
    BodyBasicView,
    BodyDetailView,
    BodyMeasurementView,
    BodyPhotoTransactionView,
    BodyPhotoView,
    MeView,
    PreferenceOptionsView,
    PursuitView,
    SocialLoginView,
)

app_name = "users"

urlpatterns = [
    # 소셜 로그인: naver | kakao | google
    path("auth/<str:provider>/login/", SocialLoginView.as_view(), name="social-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("users/me/", MeView.as_view(), name="me"),
    # 설정 페이지 — 신체치수
    path("users/me/body/", BodyMeasurementView.as_view(), name="body"),
    path("users/me/body/basic/", BodyBasicView.as_view(), name="body-basic"),
    path("users/me/body/detail/", BodyDetailView.as_view(), name="body-detail"),
    path("users/me/body/photos/", BodyPhotoView.as_view(), name="body-photos"),
    path(
        "users/me/body/photos/<uuid:transaction_id>/",
        BodyPhotoTransactionView.as_view(),
        name="body-photo-transaction",
    ),
    # 추구미: 옵션 마스터 (11개 카테고리, 계절/스타일/색상/...) | 사용자 선택(preferred/avoided 2단 nested payloa)
    path("preference-options/", PreferenceOptionsView.as_view(), name="preference-options"),
    path("users/me/pursuit/", PursuitView.as_view(), name="pursuit"),
]
