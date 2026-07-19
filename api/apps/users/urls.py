from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import (
    BodyBasicView,
    BodyDetailView,
    BodyMeasurementView,
    BodyPhotoView,
    MeView,
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
]
