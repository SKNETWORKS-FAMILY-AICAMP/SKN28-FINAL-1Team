import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.home.services import (
    MOCK_CLOSET_COUNT,
    MOCK_SAVED_LOOK_COUNT,
    QUICK_RECOMMENDS,
    build_today_look,
)
from apps.weather.services import get_current_weather, resolve_coordinates

logger = logging.getLogger(__name__)


class HomeView(APIView):
    """GET /api/v1/home/?lat=&lon= — 홈 화면 통합 응답 (로그인 필요)."""

    def get(self, request):
        lat, lon = resolve_coordinates(
            request.query_params.get("lat"), request.query_params.get("lon")
        )
        weather = get_current_weather(lat, lon)

        # 오늘의 룩 선반영. 예전에는 로그인 응답에서 걸었는데, 그 시점에는
        # 위치가 없어 항상 서울 날씨로 만들어졌다. 홈 요청에는 위경도가 실려
        # 오므로 여기서 걸면 그날 첫 추천이 사용자 위치의 날씨를 탄다.
        # 사용자는 로그인 직후 홈으로 오니 선반영 효과는 그대로다.
        _kick_off_daily_look(request.user, lat, lon)

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


def _kick_off_daily_look(user, lat, lon) -> None:
    """그날 첫 홈 진입이면 오늘의 룩 생성을 미리 걸어둔다.

    사용자가 추천 화면에 도착할 때쯤 이미 완성돼 있게 하려는 선반영이다.
    조회 엔드포인트(GET /api/v1/looks/today/)도 같은 함수를 부르므로 여기서
    실패해도 기능이 사라지지는 않는다 — 그래서 예외를 삼킨다. 홈 화면은
    추천보다 훨씬 중요하고, 추천 생성이 홈을 막아서는 안 된다.
    """
    try:
        from apps.recommend.services.daily_look import ensure_today_look

        ensure_today_look(user, lat=lat, lon=lon)
    except Exception:  # noqa: BLE001
        logger.exception("오늘의 룩 선반영 실패 (홈 응답은 계속 진행): user=%s", user.pk)
