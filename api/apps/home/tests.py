"""홈 API의 오늘의 룩 선반영 훅 테스트.

트리거를 로그인에서 홈으로 옮겼다. 홈 요청에는 위경도가 실려 오므로 그날 첫
추천이 사용자 위치의 날씨를 탈 수 있고, 사용자는 로그인 직후 홈으로 오니
선반영 효과는 그대로다. 여기서 지키는 계약은 두 가지다.

- 홈 조회가 ensure_today_look을 좌표와 함께 부른다 (선반영이 실제로 걸린다)
- 선반영이 죽어도 홈은 200이다 (홈 화면이 추천보다 훨씬 중요하다)
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()

WEATHER = {"region": "서울", "temperature": 25, "sky_state": "맑음"}


class HomeDailyLookTriggerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="home1")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse("home:home")

    @patch("apps.recommend.services.daily_look.ensure_today_look")
    @patch("apps.home.views.get_current_weather", return_value=WEATHER)
    def test_home_call_kicks_off_daily_look_with_coordinates(self, _weather, ensure):
        response = self.client.get(self.url, {"lat": "37.5665", "lon": "126.9780"})
        self.assertEqual(response.status_code, 200)
        ensure.assert_called_once()
        args, kwargs = ensure.call_args
        self.assertEqual(args[0], self.user)
        # 홈이 검증한 좌표가 그대로 넘어가야 그날 추천이 사용자 위치 날씨를 탄다
        self.assertEqual(kwargs["lat"], 37.5665)
        self.assertEqual(kwargs["lon"], 126.978)

    @patch(
        "apps.recommend.services.daily_look.ensure_today_look",
        side_effect=RuntimeError("db down"),
    )
    @patch("apps.home.views.get_current_weather", return_value=WEATHER)
    def test_trigger_failure_does_not_break_home(self, _weather, _ensure):
        """선반영은 부가 기능이다. 죽어도 홈 응답은 성립해야 한다."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("weather", response.json())

    @patch("apps.recommend.services.daily_look.ensure_today_look")
    @patch("apps.home.views.get_current_weather", return_value=WEATHER)
    def test_anonymous_request_is_rejected_before_trigger(self, _weather, ensure):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, 401)
        ensure.assert_not_called()
