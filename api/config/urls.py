"""프로젝트 URL 설정."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.home.urls")),
    path("api/v1/", include("apps.wardrobe.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.style_calendar.urls")),
    path("api/v1/", include("apps.lookbook.urls")),
    path("api/v1/", include("apps.recommend.urls")),
]
