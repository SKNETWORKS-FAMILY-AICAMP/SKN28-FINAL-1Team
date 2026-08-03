import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.recommend.services import gemini
from apps.recommend.services.outfit_context import build_analysis_context


EVALUATION = {
    "overall_score": 88,
    "summary": "색상 조화가 안정적이고 세련된 코디입니다.",
    "strengths": ["색상 조화가 좋습니다.", "실루엣이 깔끔합니다."],
    "weather_comment": "현재 기온에 잘 어울립니다.",
    "personalization_comment": "개인 정보 없이도 조화로운 인상입니다.",
    "styling_tips": ["현재 장점을 살려 액세서리를 더해보세요."],
}
WEATHER = {
    "region": "서울특별시 종로구",
    "temperature": 24.0,
    "sky_state": "맑음",
    "is_stale": False,
    "observed_at": None,
}
CONTEXT = {
    "weather": WEATHER,
    "pursuit": None,
    "body": None,
    "personalized": False,
}


def make_image_file(name: str = "outfit.jpg") -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class OutfitAnalysisViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("recommend:outfit-analysis")

    @patch("apps.recommend.views.gemini.evaluate_outfit", return_value=EVALUATION)
    @patch("apps.recommend.views.build_analysis_context", return_value=CONTEXT)
    def test_evaluates_image_without_authentication(
        self,
        mock_context: Mock,
        mock_evaluate: Mock,
    ) -> None:
        response = self.client.post(
            self.url,
            {"image": make_image_file(), "lat": 37.5, "lon": 127.0},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["evaluation"]["overall_score"], 88)
        self.assertFalse(response.data["context"]["personalized"])
        self.assertFalse(response.data["context"]["used_pursuit"])
        self.assertNotIn("body", response.data["context"])
        mock_context.assert_called_once()
        mock_evaluate.assert_called_once()

    def test_rejects_request_without_image(self) -> None:
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)

    def test_rejects_only_one_coordinate(self) -> None:
        response = self.client.post(
            self.url,
            {"image": make_image_file(), "lat": 37.5},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.data)

    def test_rejects_non_image_file(self) -> None:
        response = self.client.post(
            self.url,
            {
                "image": SimpleUploadedFile(
                    "outfit.txt", b"not an image", content_type="text/plain"
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)

    def test_rejects_json_request(self) -> None:
        response = self.client.post(self.url, {"image": "value"}, format="json")
        self.assertEqual(response.status_code, 415)

    @patch(
        "apps.recommend.views.gemini.evaluate_outfit",
        side_effect=gemini.GeminiServiceError,
    )
    @patch("apps.recommend.views.build_analysis_context", return_value=CONTEXT)
    def test_returns_503_when_gemini_fails(
        self,
        _mock_context: Mock,
        _mock_evaluate: Mock,
    ) -> None:
        response = self.client.post(
            self.url, {"image": make_image_file()}, format="multipart"
        )
        self.assertEqual(response.status_code, 503)


@override_settings(
    GEMINI_API_KEY="test-api-key",
    GEMINI_MODEL="gemini-3.5-flash",
    GEMINI_API_BASE_URL="https://example.test",
    GEMINI_TIMEOUT_SECONDS=10,
)
class GeminiServiceTests(SimpleTestCase):
    @patch("apps.recommend.services.gemini.requests.post")
    def test_sends_image_context_and_structured_schema(self, mock_post: Mock) -> None:
        api_response = Mock()
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(EVALUATION)}]}}
            ]
        }
        mock_post.return_value = api_response

        result = gemini.evaluate_outfit(make_image_file(), context=CONTEXT)

        self.assertEqual(result, EVALUATION)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-api-key")
        self.assertEqual(kwargs["timeout"], 10)
        parts = kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/jpeg")
        self.assertTrue(parts[1]["inlineData"]["data"])
        self.assertIn("weather", parts[0]["text"])
        response_format = kwargs["json"]["generationConfig"]["responseFormat"]
        self.assertEqual(response_format["text"]["mimeType"], "application/json")

    @override_settings(GEMINI_API_KEY="")
    def test_requires_api_key(self) -> None:
        with self.assertRaises(gemini.GeminiConfigurationError):
            gemini.evaluate_outfit(make_image_file(), context=CONTEXT)


class OutfitContextTests(SimpleTestCase):
    @patch(
        "apps.recommend.services.outfit_context.get_current_weather",
        return_value=WEATHER,
    )
    def test_anonymous_context_omits_personal_data(self, mock_weather: Mock) -> None:
        context = build_analysis_context(AnonymousUser(), lat=None, lon=None)

        self.assertEqual(context["weather"], WEATHER)
        self.assertIsNone(context["pursuit"])
        self.assertIsNone(context["body"])
        self.assertFalse(context["personalized"])
        mock_weather.assert_called_once()

    @patch("apps.recommend.services.outfit_context.get_pursuit")
    @patch("apps.recommend.services.outfit_context.BodyMeasurement.objects.filter")
    @patch(
        "apps.recommend.services.outfit_context.get_current_weather",
        return_value=WEATHER,
    )
    def test_authenticated_context_includes_pursuit_and_body(
        self,
        _mock_weather: Mock,
        mock_filter: Mock,
        mock_pursuit: Mock,
    ) -> None:
        user = SimpleNamespace(is_authenticated=True)
        mock_pursuit.return_value = {"preferred": {"styles": ["minimal"]}}
        mock_filter.return_value.first.return_value = SimpleNamespace(
            gender="female",
            height=None,
            weight=None,
            chest=None,
            waist=None,
            hip=None,
            thigh=None,
            calf=None,
            arm=None,
            shoulder=None,
        )

        context = build_analysis_context(user, lat=37.5, lon=127.0)

        self.assertTrue(context["personalized"])
        self.assertEqual(context["body"]["gender"], "female")
        self.assertEqual(context["pursuit"]["preferred"]["styles"], ["minimal"])
