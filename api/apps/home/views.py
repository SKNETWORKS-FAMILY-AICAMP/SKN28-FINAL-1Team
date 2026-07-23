from rest_framework.response import Response
from rest_framework.views import APIView

from apps.home.services import (
    MOCK_CLOSET_COUNT,
    MOCK_SAVED_LOOK_COUNT,
    QUICK_RECOMMENDS,
    build_today_look,
)
from apps.weather.services import get_current_weather, resolve_coordinates


class HomeView(APIView):
    """GET /api/v1/home/?lat=&lon= — 홈 화면 통합 응답 (로그인 필요)."""

    def get(self, request):
        lat, lon = resolve_coordinates(
            request.query_params.get("lat"), request.query_params.get("lon")
        )
        weather = get_current_weather(lat, lon)

        return Response(
            {
                "nickname": request.user.nickname or request.user.username,
                "weather": weather,
                "today_look": build_today_look(weather["temperature"]),
                "quick_recommends": QUICK_RECOMMENDS,
                "closet_count": MOCK_CLOSET_COUNT,
                "saved_look_count": MOCK_SAVED_LOOK_COUNT,
            }
        )
