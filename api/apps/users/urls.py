from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.views import MeView, SocialLoginView

app_name = "users"

urlpatterns = [
    # 소셜 로그인: naver | kakao | google
    path("auth/<str:provider>/login/", SocialLoginView.as_view(), name="social-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("users/me/", MeView.as_view(), name="me"),
]
