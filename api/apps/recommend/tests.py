import json
from datetime import datetime, timezone as dt_timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.recommend.models import OutfitAnalysis
from apps.recommend.services import gemini, imaging
from apps.recommend.services.outfit_context import build_analysis_context


EVALUATION = {
    "overall_score": 88,
    "summary": "색상 조화가 안정적이고 세련된 코디입니다.",
    "strengths": ["색상 조화가 좋습니다.", "실루엣이 깔끔합니다."],
    "weather_comment": "현재 기온에 잘 어울립니다.",
    "personalization_comment": "개인 정보 없이도 조화로운 인상입니다.",
    "styling_tips": ["현재 장점을 살려 액세서리를 더해보세요."],
}
RAW_RESPONSE = {
    "candidates": [{"content": {"parts": [{"text": json.dumps(EVALUATION)}]}}],
    "usageMetadata": {"totalTokenCount": 1234},
}
GEMINI_RESULT = gemini.GeminiResult(
    evaluation=EVALUATION,
    response_payload=RAW_RESPONSE,
    model="gemini-3.5-flash",
    latency_ms=321,
)
OBSERVED_AT = datetime(2026, 7, 15, 14, 0, tzinfo=dt_timezone.utc)
# weather-collector가 도는 서버에서는 observed_at이 datetime으로 채워진다.
# 실황이 없는 로컬(None)만 검증하면 JSON 직렬화 회귀를 놓친다.
RAW_WEATHER = {
    "region": "서울특별시 종로구",
    "temperature": 24.0,
    "sky_state": "맑음",
    "is_stale": False,
    "observed_at": OBSERVED_AT,
}
WEATHER = {**RAW_WEATHER, "observed_at": OBSERVED_AT.isoformat()}
CONTEXT = {
    "weather": WEATHER,
    "pursuit": None,
    "body": None,
    "personalized": False,
}


# 단색 이미지는 JPEG가 극단적으로 잘 압축해 축소 효과를 관찰할 수 없다.
# Image.effect_noise는 호출마다 결과가 달라져 크기 비교가 불안정하므로,
# 결정적인 노이즈 타일을 만들어 채운다.
_NOISE_TILE_PX = 64
_NOISE_TILE = Image.frombytes(
    "RGB",
    (_NOISE_TILE_PX, _NOISE_TILE_PX),
    bytes(
        (x * 37 + y * 97 + channel * 53) % 256
        for y in range(_NOISE_TILE_PX)
        for x in range(_NOISE_TILE_PX)
        for channel in range(3)
    ),
)


def make_image(size: tuple[int, int] = (2, 2)) -> Image.Image:
    image = Image.new("RGB", size)
    for top in range(0, size[1], _NOISE_TILE_PX):
        for left in range(0, size[0], _NOISE_TILE_PX):
            image.paste(_NOISE_TILE, (left, top))
    return image


def make_image_bytes(size: tuple[int, int] = (2, 2)) -> bytes:
    buffer = BytesIO()
    make_image(size).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def make_image_file(
    name: str = "outfit.jpg", size: tuple[int, int] = (2, 2)
) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, make_image_bytes(size), content_type="image/jpeg")


class OutfitAnalysisViewTests(TestCase):
    """평가 요청 → 응답 + DB 기록.

    기록이 생기므로 SimpleTestCase가 아니라 DB를 쓰는 TestCase다.
    S3는 버킷 미설정 상태(기본)라 업로드를 건너뛴다 — 별도 테스트에서 검증.
    """

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("recommend:outfit-analysis")

    @patch(
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        return_value=GEMINI_RESULT,
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
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

    @patch(
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        return_value=GEMINI_RESULT,
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    def test_persists_context_and_llm_payloads(
        self,
        _mock_context: Mock,
        _mock_evaluate: Mock,
    ) -> None:
        response = self.client.post(
            self.url,
            {"image": make_image_file(), "lat": 37.5, "lon": 127.0},
            format="multipart",
        )

        analysis = OutfitAnalysis.objects.get()
        self.assertEqual(analysis.pk, response.data["analysis_id"])
        self.assertEqual(analysis.status, OutfitAnalysis.Status.SUCCEEDED)
        self.assertIsNone(analysis.user)  # 익명 요청
        # 질의 구성 정보 스냅샷
        self.assertEqual(analysis.weather, WEATHER)
        self.assertIsNone(analysis.body)
        self.assertIsNone(analysis.pursuit)
        self.assertFalse(analysis.personalized)
        self.assertEqual(analysis.requested_lat, 37.5)
        self.assertEqual(analysis.resolved_lat, 37.5)
        # LLM 요청·응답 원본
        self.assertEqual(analysis.evaluation, EVALUATION)
        self.assertEqual(analysis.response_payload, RAW_RESPONSE)
        self.assertEqual(analysis.llm_model, "gemini-3.5-flash")
        self.assertEqual(analysis.latency_ms, 321)
        self.assertIn("systemInstruction", analysis.request_payload)
        self.assertIsNotNone(analysis.finished_at)

    @patch(
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        return_value=GEMINI_RESULT,
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    def test_request_payload_does_not_store_image_base64(
        self,
        _mock_context: Mock,
        _mock_evaluate: Mock,
    ) -> None:
        self.client.post(self.url, {"image": make_image_file()}, format="multipart")

        analysis = OutfitAnalysis.objects.get()
        image_part = analysis.request_payload["contents"][0]["parts"][1]["inlineData"]
        # 원본은 S3에 있으므로 행에는 자리표시자만 남는다 (행 크기 폭증 방지)
        self.assertTrue(image_part["data"].startswith("<image omitted"))
        # image_bytes는 원본 크기, 자리표시자는 실제 전송 크기
        self.assertEqual(analysis.image_bytes, len(make_image_bytes()))
        self.assertGreater(image_part_size(analysis), 0)

    @patch(
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        return_value=GEMINI_RESULT,
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    def test_records_logged_in_user(
        self,
        _mock_context: Mock,
        _mock_evaluate: Mock,
    ) -> None:
        user = get_user_model().objects.create(username="naver_1")
        self.client.force_authenticate(user=user)

        self.client.post(self.url, {"image": make_image_file()}, format="multipart")

        self.assertEqual(OutfitAnalysis.objects.get().user, user)

    def test_rejects_request_without_image(self) -> None:
        response = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)
        self.assertEqual(OutfitAnalysis.objects.count(), 0)

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
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        side_effect=gemini.GeminiServiceError(
            "Gemini 코디 평가에 실패했습니다.",
            response_payload={"error": {"code": 400}},
        ),
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    def test_returns_503_and_records_failure_when_gemini_fails(
        self,
        _mock_context: Mock,
        _mock_evaluate: Mock,
    ) -> None:
        response = self.client.post(
            self.url, {"image": make_image_file()}, format="multipart"
        )

        self.assertEqual(response.status_code, 503)
        analysis = OutfitAnalysis.objects.get()
        self.assertEqual(analysis.status, OutfitAnalysis.Status.FAILED)
        self.assertIn("실패", analysis.error_message)
        self.assertEqual(analysis.response_payload, {"error": {"code": 400}})
        self.assertIsNone(analysis.evaluation)
        # 실패해도 질의에 쓴 정보는 남아야 재현이 가능하다
        self.assertEqual(analysis.weather, WEATHER)
        self.assertIn("systemInstruction", analysis.request_payload)
        self.assertIsNotNone(analysis.finished_at)

    @patch(
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        return_value=GEMINI_RESULT,
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    @patch("apps.recommend.services.analysis.storage.is_configured", return_value=True)
    @patch("apps.recommend.services.analysis.storage.upload_fileobj")
    def test_uploads_original_image_to_s3(
        self,
        mock_upload: Mock,
        _mock_configured: Mock,
        _mock_context: Mock,
        _mock_evaluate: Mock,
    ) -> None:
        self.client.post(self.url, {"image": make_image_file()}, format="multipart")

        analysis = OutfitAnalysis.objects.get()
        mock_upload.assert_called_once()
        self.assertEqual(
            analysis.image_s3_key,
            f"outfits/anonymous/{analysis.pk}/original.jpg",
        )

    @patch(
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        return_value=GEMINI_RESULT,
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    def test_sends_shrunk_image_but_records_original_size(
        self,
        _mock_context: Mock,
        mock_evaluate: Mock,
    ) -> None:
        """큰 사진은 전송 전에 축소한다 (원본 그대로 보내면 Gemini가 타임아웃)."""
        original = make_image_bytes((2000, 1500))
        self.client.post(
            self.url,
            {
                "image": SimpleUploadedFile(
                    "big.jpg", original, content_type="image/jpeg"
                )
            },
            format="multipart",
        )

        sent_data = mock_evaluate.call_args.args[0]
        self.assertLess(len(sent_data), len(original))
        with Image.open(BytesIO(sent_data)) as sent_image:
            self.assertLessEqual(max(sent_image.size), imaging.MAX_EDGE_PX)

        analysis = OutfitAnalysis.objects.get()
        # DB의 image_bytes는 S3에 올린 원본 기준
        self.assertEqual(analysis.image_bytes, len(original))
        self.assertEqual(image_part_size(analysis), len(sent_data))

    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    @patch("apps.recommend.services.analysis.storage.is_configured", return_value=True)
    @patch(
        "apps.recommend.services.analysis.storage.upload_fileobj",
        side_effect=lambda fileobj, key, content_type=None: fileobj.close(),
    )
    @patch("apps.recommend.services.gemini.requests.post")
    def test_s3_upload_closing_stream_does_not_break_llm_call(
        self,
        mock_post: Mock,
        _mock_upload: Mock,
        _mock_configured: Mock,
        _mock_context: Mock,
    ) -> None:
        """회귀: boto3 upload_fileobj가 넘겨받은 파일을 닫아 Gemini 읽기가 죽었다.

        업로드와 LLM 호출이 같은 업로드 파일을 차례로 쓰던 구조라
        두 번째 읽기가 ValueError("I/O operation on closed file")로 500을 냈다.
        """
        api_response = Mock()
        api_response.status_code = 200
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = RAW_RESPONSE
        mock_post.return_value = api_response

        with override_settings(
            GEMINI_API_KEY="test-api-key",
            GEMINI_MODEL="gemini-3.5-flash",
            GEMINI_API_BASE_URL="https://example.test",
            GEMINI_TIMEOUT_SECONDS=10,
        ):
            response = self.client.post(
                self.url, {"image": make_image_file()}, format="multipart"
            )

        self.assertEqual(response.status_code, 200)
        analysis = OutfitAnalysis.objects.get()
        self.assertEqual(analysis.status, OutfitAnalysis.Status.SUCCEEDED)
        self.assertTrue(analysis.image_s3_key)
        # 실제로 이미지 base64가 실려 나갔는지 확인 (빈 바이트로 조용히 성공하면 안 된다)
        sent_parts = mock_post.call_args.kwargs["json"]["contents"][0]["parts"]
        self.assertTrue(len(sent_parts[1]["inlineData"]["data"]) > 100)

    @patch(
        "apps.recommend.services.analysis.gemini.evaluate_outfit",
        return_value=GEMINI_RESULT,
    )
    @patch(
        "apps.recommend.services.analysis.build_analysis_context",
        return_value=CONTEXT,
    )
    @patch("apps.recommend.services.analysis.storage.is_configured", return_value=True)
    @patch(
        "apps.recommend.services.analysis.storage.upload_fileobj",
        side_effect=RuntimeError("S3 down"),
    )
    def test_s3_failure_does_not_break_evaluation(
        self,
        _mock_upload: Mock,
        _mock_configured: Mock,
        _mock_context: Mock,
        _mock_evaluate: Mock,
    ) -> None:
        response = self.client.post(
            self.url, {"image": make_image_file()}, format="multipart"
        )

        self.assertEqual(response.status_code, 200)
        analysis = OutfitAnalysis.objects.get()
        self.assertEqual(analysis.status, OutfitAnalysis.Status.SUCCEEDED)
        self.assertEqual(analysis.image_s3_key, "")


def image_part_size(analysis: OutfitAnalysis) -> int:
    """자리표시자에 박아 둔 바이트 수를 되읽어 image_bytes와 대조한다."""
    data = analysis.request_payload["contents"][0]["parts"][1]["inlineData"]["data"]
    return int(data.split(":")[1].strip().split(" ")[0])


class OutfitAnalysisHistoryTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = get_user_model().objects.create(username="naver_1")
        self.other = get_user_model().objects.create(username="kakao_2")
        self.mine = OutfitAnalysis.objects.create(
            user=self.user,
            status=OutfitAnalysis.Status.SUCCEEDED,
            weather=WEATHER,
            evaluation=EVALUATION,
            personalized=True,
        )
        self.theirs = OutfitAnalysis.objects.create(
            user=self.other, status=OutfitAnalysis.Status.SUCCEEDED
        )
        self.anonymous = OutfitAnalysis.objects.create(
            user=None, status=OutfitAnalysis.Status.SUCCEEDED
        )

    def test_list_requires_authentication(self) -> None:
        response = self.client.get(reverse("recommend:outfit-analysis-list"))
        self.assertEqual(response.status_code, 401)

    def test_list_returns_only_my_analyses(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("recommend:outfit-analysis-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(str(item["id"]), str(self.mine.pk))
        self.assertEqual(item["overall_score"], 88)
        self.assertEqual(item["summary"], EVALUATION["summary"])

    def test_list_filters_by_status(self) -> None:
        OutfitAnalysis.objects.create(
            user=self.user, status=OutfitAnalysis.Status.FAILED
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("recommend:outfit-analysis-list"), {"status": "failed"}
        )

        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "FAILED")

    def test_detail_returns_stored_context_and_payloads(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("recommend:outfit-analysis-detail", args=[self.mine.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["weather"], WEATHER)
        self.assertEqual(response.data["evaluation"], EVALUATION)
        self.assertIn("request_payload", response.data)
        self.assertIn("response_payload", response.data)
        self.assertIsNone(response.data["image_url"])  # 버킷 미설정

    def test_detail_hides_other_users_analysis(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("recommend:outfit-analysis-detail", args=[self.theirs.pk])
        )

        self.assertEqual(response.status_code, 404)


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
        api_response.status_code = 200   # Mock 기본값은 int 비교가 안 된다
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = RAW_RESPONSE
        mock_post.return_value = api_response

        result = gemini.evaluate_outfit(
            make_image_bytes(), mime_type="image/jpeg", context=CONTEXT
        )

        self.assertEqual(result.evaluation, EVALUATION)
        self.assertEqual(result.response_payload, RAW_RESPONSE)
        self.assertEqual(result.model, "gemini-3.5-flash")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-api-key")
        self.assertEqual(kwargs["timeout"], 10)
        parts = kwargs["json"]["contents"][0]["parts"]
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/jpeg")
        self.assertTrue(parts[1]["inlineData"]["data"])
        self.assertIn("weather", parts[0]["text"])
        generation_config = kwargs["json"]["generationConfig"]
        self.assertEqual(generation_config["responseMimeType"], "application/json")
        self.assertEqual(
            generation_config["responseSchema"], gemini.EVALUATION_SCHEMA
        )
        # Gemini Schema는 OpenAPI 서브셋이라 additionalProperties를 모른다 (400 유발)
        self.assertNotIn("additionalProperties", gemini.EVALUATION_SCHEMA)

    @patch("apps.recommend.services.gemini.requests.post")
    def test_http_error_carries_response_body(self, mock_post: Mock) -> None:
        import requests

        api_response = Mock()
        api_response.status_code = 400
        api_response.text = '{"error": "bad"}'
        api_response.json.return_value = {"error": "bad"}
        api_response.raise_for_status.side_effect = requests.HTTPError("400")
        mock_post.return_value = api_response

        with self.assertRaises(gemini.GeminiServiceError) as ctx:
            gemini.evaluate_outfit(
            make_image_bytes(), mime_type="image/jpeg", context=CONTEXT
        )

        self.assertEqual(ctx.exception.response_payload, {"error": "bad"})

    def test_build_request_payload_matches_real_body_without_base64(self) -> None:
        payload = gemini.build_request_payload(
            CONTEXT, mime_type="image/jpeg", image_bytes=1234
        )

        parts = payload["contents"][0]["parts"]
        self.assertIn("weather", parts[0]["text"])
        self.assertIn("1234", parts[1]["inlineData"]["data"])
        self.assertEqual(
            payload["generationConfig"]["responseSchema"], gemini.EVALUATION_SCHEMA
        )

    @override_settings(GEMINI_API_KEY="")
    def test_requires_api_key(self) -> None:
        with self.assertRaises(gemini.GeminiConfigurationError):
            gemini.evaluate_outfit(
            make_image_bytes(), mime_type="image/jpeg", context=CONTEXT
        )


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

    @patch(
        "apps.recommend.services.outfit_context.get_current_weather",
        return_value=dict(RAW_WEATHER),
    )
    def test_weather_datetime_is_json_serializable(self, _mock_weather: Mock) -> None:
        context = build_analysis_context(AnonymousUser(), lat=None, lon=None)

        self.assertEqual(
            context["weather"]["observed_at"], OBSERVED_AT.isoformat()
        )
        json.dumps(context)  # 응답 직렬화(JSONField)와 같은 조건

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


class ImagingTests(SimpleTestCase):
    def test_shrinks_large_image_to_max_edge(self) -> None:
        original = make_image_bytes((2400, 1200))

        shrunk, mime = imaging.shrink_for_llm(original, mime_type="image/jpeg")

        self.assertEqual(mime, "image/jpeg")
        self.assertLess(len(shrunk), len(original))
        with Image.open(BytesIO(shrunk)) as image:
            self.assertEqual(max(image.size), imaging.MAX_EDGE_PX)
            self.assertEqual(image.size[0] / image.size[1], 2)  # 비율 유지

    def test_uses_resized_version_even_if_bytes_grow(self) -> None:
        """잘 압축되는 큰 PNG도 해상도를 줄여 보낸다 (모델 처리 픽셀 수가 목적)."""
        buffer = BytesIO()
        make_image((1600, 1600)).save(buffer, format="PNG")

        shrunk, mime = imaging.shrink_for_llm(buffer.getvalue(), mime_type="image/png")

        self.assertEqual(mime, "image/jpeg")
        with Image.open(BytesIO(shrunk)) as image:
            self.assertEqual(max(image.size), imaging.MAX_EDGE_PX)

    def test_keeps_already_small_image(self) -> None:
        original = make_image_bytes((8, 8))

        shrunk, mime = imaging.shrink_for_llm(original, mime_type="image/jpeg")

        # 재압축이 손해면 원본을 그대로 쓴다
        self.assertLessEqual(len(shrunk), len(original))
        self.assertEqual(mime, "image/jpeg")

    def test_broken_image_falls_back_to_original(self) -> None:
        """축소는 최적화일 뿐이라 실패해도 평가를 막지 않는다."""
        shrunk, mime = imaging.shrink_for_llm(b"not an image", mime_type="image/jpeg")

        self.assertEqual(shrunk, b"not an image")
        self.assertEqual(mime, "image/jpeg")
