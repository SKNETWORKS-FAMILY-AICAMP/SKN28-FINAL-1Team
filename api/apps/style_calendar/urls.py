from django.urls import URLPattern, URLResolver

app_name = "style_calendar"

# 모델과 API 구현 전에도 프로젝트 URL 구성이 유효하도록 빈 URLConf를 연결한다.
urlpatterns: list[URLPattern | URLResolver] = []
