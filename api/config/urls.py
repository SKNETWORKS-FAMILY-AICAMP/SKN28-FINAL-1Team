"""프로젝트 URL 설정."""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

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

if settings.DEBUG or hasattr(settings, 'AUTO_LOGIN_ENABLED'):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
