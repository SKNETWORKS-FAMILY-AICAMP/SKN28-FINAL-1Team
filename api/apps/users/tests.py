"""users 앱 테스트.

OAuth 제공사 호출은 mock 처리한다 (외부 네트워크 의존 금지).
실행: python manage.py test apps.users
"""

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import (
    BodyMeasurement,
    BodyPhotoTransaction,
    SocialAccount,
    User,
)
from apps.users.services import body_inference
from apps.users.services.oauth import SocialProfile


def make_profile(provider: str = "kakao", uid: str = "12345") -> SocialProfile:
    return SocialProfile(
        provider=provider,
        provider_user_id=uid,
        email="test@example.com",
        nickname="테스터",
        profile_image="https://example.com/p.jpg",
        raw={"id": uid},
    )


class SocialLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    REDIRECT_URI = "http://localhost:3000/oauth/callback"

    @patch("apps.users.views.oauth.authenticate")
    def test_first_login_creates_user_and_returns_jwt(self, mock_auth):
        mock_auth.return_value = make_profile()
        url = reverse("users:social-login", kwargs={"provider": "kakao"})

        response = self.client.post(
            url, {"code": "dummy-code", "redirect_uri": self.REDIRECT_URI}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(response.data["is_new_user"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.count(), 1)

    @patch("apps.users.views.oauth.authenticate")
    def test_second_login_reuses_user(self, mock_auth):
        mock_auth.return_value = make_profile()
        url = reverse("users:social-login", kwargs={"provider": "kakao"})

        body = {"code": "c1", "redirect_uri": self.REDIRECT_URI}
        self.client.post(url, body, format="json")
        response = self.client.post(url, {**body, "code": "c2"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_new_user"])
        self.assertEqual(User.objects.count(), 1)

    def test_unknown_provider_returns_400(self):
        url = reverse("users:social-login", kwargs={"provider": "github"})
        response = self.client.post(url, {"code": "x"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_kakao_without_redirect_uri_returns_400(self):
        url = reverse("users:social-login", kwargs={"provider": "kakao"})
        response = self.client.post(url, {"code": "x"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_naver_without_state_returns_400(self):
        url = reverse("users:social-login", kwargs={"provider": "naver"})
        response = self.client.post(url, {"code": "x"}, format="json")
        self.assertEqual(response.status_code, 400)


class KakaoTokenLoginTests(TestCase):
    """token 방식 로그인 (카카오 네이티브 앱 SDK 전용)."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("users:social-login", kwargs={"provider": "kakao"})

    @patch("apps.users.views.oauth.authenticate_with_token")
    def test_access_token_login_creates_user(self, mock_auth):
        mock_auth.return_value = make_profile()

        response = self.client.post(
            self.url, {"access_token": "kakao-sdk-token"}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data)
        self.assertTrue(response.data["is_new_user"])
        mock_auth.assert_called_once_with(
            provider="kakao", access_token="kakao-sdk-token"
        )

    @patch("apps.users.views.oauth.authenticate_with_token")
    def test_invalid_token_returns_401(self, mock_auth):
        from apps.users.services.oauth import OAuthError  # noqa: PLC0415

        mock_auth.side_effect = OAuthError("app_id 불일치")
        response = self.client.post(self.url, {"access_token": "stolen"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_missing_code_and_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("apps.users.views.oauth.authenticate_with_token")
    def test_token_login_not_supported_provider_returns_401(self, mock_auth):
        """apple 등 token 방식 미지원 제공사는 서비스 계층에서 OAuthError."""
        from apps.users.services.oauth import OAuthError  # noqa: PLC0415

        mock_auth.side_effect = OAuthError("미지원")
        url = reverse("users:social-login", kwargs={"provider": "apple"})
        response = self.client.post(url, {"access_token": "t"}, format="json")
        self.assertEqual(response.status_code, 401)


class KakaoTokenVerifyTests(TestCase):
    """oauth.authenticate_with_token의 app_id 검증 로직."""

    @patch("apps.users.services.oauth.fetch_profile")
    @patch("apps.users.services.oauth._get_profile")
    def test_app_id_mismatch_raises(self, mock_info, mock_fetch):
        from django.test import override_settings

        from apps.users.services import oauth

        mock_info.return_value = {"app_id": 999, "id": 12345}
        providers = {
            "kakao": {
                "client_id": "k",
                "app_id": "123",
                "token_info_url": "https://kapi.kakao.com/v1/user/access_token_info",
                "profile_url": "https://kapi.kakao.com/v2/user/me",
            }
        }
        with override_settings(OAUTH_PROVIDERS=providers):
            with self.assertRaises(oauth.OAuthError):
                oauth.authenticate_with_token("kakao", "token")
        mock_fetch.assert_not_called()

    @patch("apps.users.services.oauth.fetch_profile")
    @patch("apps.users.services.oauth._get_profile")
    def test_app_id_match_fetches_profile(self, mock_info, mock_fetch):
        from django.test import override_settings

        from apps.users.services import oauth

        mock_info.return_value = {"app_id": 123, "id": 12345}
        mock_fetch.return_value = make_profile()
        providers = {
            "kakao": {
                "client_id": "k",
                "app_id": "123",
                "token_info_url": "https://kapi.kakao.com/v1/user/access_token_info",
                "profile_url": "https://kapi.kakao.com/v2/user/me",
            }
        }
        with override_settings(OAUTH_PROVIDERS=providers):
            profile = oauth.authenticate_with_token("kakao", "token")
        self.assertEqual(profile.provider, "kakao")
        mock_fetch.assert_called_once()

    def test_unsupported_provider_raises(self):
        """apple은 token 방식을 지원하지 않는다."""
        from apps.users.services import oauth

        with self.assertRaises(oauth.OAuthError):
            oauth.authenticate_with_token("apple", "token")


class NaverTokenLoginTests(TestCase):
    """네이버 token 방식: 발급 앱 검증 없이 /v1/nid/me로 사용자 식별만 수행."""

    NAVER_PROVIDERS = {
        "naver": {
            "client_id": "naver-client-id",
            "client_secret": "naver-secret",
            "token_url": "https://nid.naver.com/oauth2.0/token",
            "profile_url": "https://openapi.naver.com/v1/nid/me",
        }
    }

    @patch("apps.users.services.oauth._get_profile")
    def test_valid_token_identifies_user(self, mock_get):
        """유효 토큰이면 앱 검증 없이 프로필 조회로 사용자를 식별한다."""
        from django.test import override_settings

        from apps.users.services import oauth

        mock_get.return_value = {
            "resultcode": "00",
            "message": "success",
            "response": {"id": "naver-uid-1", "email": "u@naver.com", "nickname": "유저"},
        }
        with override_settings(OAUTH_PROVIDERS=self.NAVER_PROVIDERS):
            profile = oauth.authenticate_with_token("naver", "sdk-token")

        self.assertEqual(profile.provider, "naver")
        self.assertEqual(profile.provider_user_id, "naver-uid-1")
        # 검증 단계가 별도 호출을 만들지 않는다 (프로필 조회 1회뿐).
        mock_get.assert_called_once()

    @patch("apps.users.services.oauth._get_profile")
    def test_invalid_token_raises(self, mock_get):
        """무효 토큰은 /v1/nid/me 단계에서 OAuthError."""
        from django.test import override_settings

        from apps.users.services import oauth

        mock_get.side_effect = oauth.OAuthError("제공사 응답 오류: status=401")
        with override_settings(OAUTH_PROVIDERS=self.NAVER_PROVIDERS):
            with self.assertRaises(oauth.OAuthError):
                oauth.authenticate_with_token("naver", "bad-token")


class GoogleTokenVerifyTests(TestCase):
    """oauth.authenticate_with_token의 구글 aud 검증 로직."""

    GOOGLE_PROVIDERS = {
        "google": {
            "client_id": "our-client-id.apps.googleusercontent.com",
            "client_secret": "secret",
            "token_info_url": "https://www.googleapis.com/oauth2/v3/tokeninfo",
            "profile_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        }
    }

    def _mock_tokeninfo(self, mock_get, payload, status_code=200):
        response = mock_get.return_value
        response.status_code = status_code
        response.json.return_value = payload

    @patch("apps.users.services.oauth.fetch_profile")
    @patch("apps.users.services.oauth.requests.get")
    def test_aud_mismatch_raises(self, mock_get, mock_fetch):
        from django.test import override_settings

        from apps.users.services import oauth

        self._mock_tokeninfo(
            mock_get, {"aud": "other-app.apps.googleusercontent.com", "sub": "1"}
        )
        with override_settings(OAUTH_PROVIDERS=self.GOOGLE_PROVIDERS):
            with self.assertRaises(oauth.OAuthError):
                oauth.authenticate_with_token("google", "token")
        mock_fetch.assert_not_called()

    @patch("apps.users.services.oauth.fetch_profile")
    @patch("apps.users.services.oauth.requests.get")
    def test_aud_match_fetches_profile(self, mock_get, mock_fetch):
        from django.test import override_settings

        from apps.users.services import oauth

        self._mock_tokeninfo(
            mock_get,
            {"aud": "our-client-id.apps.googleusercontent.com", "sub": "1"},
        )
        mock_fetch.return_value = make_profile(provider="google", uid="1")
        with override_settings(OAUTH_PROVIDERS=self.GOOGLE_PROVIDERS):
            profile = oauth.authenticate_with_token("google", "token")
        self.assertEqual(profile.provider, "google")
        mock_fetch.assert_called_once()

    @patch("apps.users.services.oauth.fetch_profile")
    @patch("apps.users.services.oauth.requests.get")
    def test_invalid_token_raises(self, mock_get, mock_fetch):
        """만료/무효 토큰은 tokeninfo가 400을 반환한다."""
        from django.test import override_settings

        from apps.users.services import oauth

        self._mock_tokeninfo(mock_get, {"error": "invalid_token"}, status_code=400)
        mock_get.return_value.text = '{"error": "invalid_token"}'
        with override_settings(OAUTH_PROVIDERS=self.GOOGLE_PROVIDERS):
            with self.assertRaises(oauth.OAuthError):
                oauth.authenticate_with_token("google", "token")
        mock_fetch.assert_not_called()


class MeViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="kakao_1", nickname="테스터")

    def test_me_requires_auth(self):
        response = self.client.get(reverse("users:me"))
        self.assertEqual(response.status_code, 401)

    def test_me_returns_profile(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("users:me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["nickname"], "테스터")

    def test_me_patch_updates_nickname(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            reverse("users:me"), {"nickname": "새닉네임"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "새닉네임")


def make_image_file(name: str = "photo.jpg") -> "SimpleUploadedFile":
    """ImageField 검증을 통과하는 최소 크기 JPEG 파일."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (10, 10), "white").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class BodyMeasurementTests(TestCase):
    """설정 페이지 — 신체치수 입력 3종 + 조회."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="kakao_1", nickname="테스터")
        self.client.force_authenticate(self.user)

    # ---- 인증 ----

    def test_requires_auth(self):
        client = APIClient()
        for method, url_name in [
            ("get", "users:body"),
            ("put", "users:body-basic"),
            ("patch", "users:body-detail"),
            ("post", "users:body-photos"),
        ]:
            response = getattr(client, method)(reverse(url_name))
            self.assertEqual(response.status_code, 401, url_name)

    # ---- 조회 ----

    def test_get_before_input_returns_nulls(self):
        response = self.client.get(reverse("users:body"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["height"])
        self.assertIsNone(response.data["chest"])

    # ---- 기본 수치 ----

    def test_basic_put_saves_height_and_weight(self):
        response = self.client.put(
            reverse("users:body-basic"),
            {"height": "175.5", "weight": "70.0"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        measurement = BodyMeasurement.objects.get(user=self.user)
        self.assertEqual(str(measurement.height), "175.5")
        self.assertEqual(str(measurement.weight), "70.0")

    def test_basic_put_requires_both_fields(self):
        response = self.client.put(
            reverse("users:body-basic"), {"height": "175.5"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_basic_put_keeps_detail_values(self):
        BodyMeasurement.objects.create(user=self.user, chest=95)
        self.client.put(
            reverse("users:body-basic"),
            {"height": "175.5", "weight": "70.0"},
            format="json",
        )
        measurement = BodyMeasurement.objects.get(user=self.user)
        self.assertEqual(str(measurement.chest), "95.0")

    # ---- 상세 수치 ----

    def test_detail_patch_updates_only_sent_fields(self):
        BodyMeasurement.objects.create(user=self.user, chest=95, waist=80)
        response = self.client.patch(
            reverse("users:body-detail"), {"waist": "82.5"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        measurement = BodyMeasurement.objects.get(user=self.user)
        self.assertEqual(str(measurement.chest), "95.0")
        self.assertEqual(str(measurement.waist), "82.5")

    def test_detail_patch_null_clears_value(self):
        BodyMeasurement.objects.create(user=self.user, chest=95)
        response = self.client.patch(
            reverse("users:body-detail"), {"chest": None}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        measurement = BodyMeasurement.objects.get(user=self.user)
        self.assertIsNone(measurement.chest)

    def test_detail_patch_accepts_empty_body(self):
        """전부 선택 입력이므로 빈 바디도 허용된다."""
        response = self.client.patch(reverse("users:body-detail"), {}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_detail_patch_rejects_out_of_range(self):
        response = self.client.patch(
            reverse("users:body-detail"), {"chest": "0.5"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    # ---- 사진 접수 ----

    def _upload_photos(self):
        return self.client.post(
            reverse("users:body-photos"),
            {"front_image": make_image_file("front.jpg"), "side_image": make_image_file("side.jpg")},
            format="multipart",
        )

    @patch("apps.users.views.body_inference.start_measurement")
    def test_photo_upload_starts_transaction(self, mock_start):
        response = self._upload_photos()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["received"]["front_image"]["name"], "front.jpg")
        self.assertEqual(
            response.data["received"]["side_image"]["content_type"], "image/jpeg"
        )
        # 트랜잭션이 '진행중'으로 생성되고 응답에 id가 포함된다.
        tx = BodyPhotoTransaction.objects.get(user=self.user)
        self.assertEqual(tx.status, BodyPhotoTransaction.Status.IN_PROGRESS)
        self.assertEqual(response.data["transaction_id"], str(tx.pk))
        self.assertEqual(response.data["status"], "in_progress")
        mock_start.assert_called_once_with(tx.pk)

    @patch("apps.users.views.body_inference.start_measurement")
    def test_photo_upload_rejected_while_in_progress(self, mock_start):
        BodyPhotoTransaction.objects.create(user=self.user)

        response = self._upload_photos()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(BodyPhotoTransaction.objects.count(), 1)
        mock_start.assert_not_called()

    @patch("apps.users.views.body_inference.start_measurement")
    def test_photo_upload_allowed_after_finished_transaction(self, mock_start):
        BodyPhotoTransaction.objects.create(
            user=self.user, status=BodyPhotoTransaction.Status.SUCCEEDED
        )

        response = self._upload_photos()

        self.assertEqual(response.status_code, 202)
        self.assertEqual(BodyPhotoTransaction.objects.count(), 2)

    def test_photo_upload_requires_both_images(self):
        response = self.client.post(
            reverse("users:body-photos"),
            {"front_image": make_image_file("front.jpg")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        # 검증 실패 시 트랜잭션이 생성되지 않는다.
        self.assertEqual(BodyPhotoTransaction.objects.count(), 0)

    def test_photo_upload_rejects_non_image(self):
        fake = SimpleUploadedFile("front.txt", b"not-an-image", content_type="text/plain")
        response = self.client.post(
            reverse("users:body-photos"),
            {"front_image": fake, "side_image": make_image_file("side.jpg")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)


class BodyPhotoTransactionTests(TestCase):
    """사진 측정 트랜잭션 — 상태 조회 API + mock 완료 처리."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="kakao_1", nickname="테스터")
        self.client.force_authenticate(self.user)

    def _tx_url(self, tx_id) -> str:
        return reverse("users:body-photo-transaction", kwargs={"transaction_id": tx_id})

    # ---- 상태 조회 ----

    def test_status_requires_auth(self):
        tx = BodyPhotoTransaction.objects.create(user=self.user)
        response = APIClient().get(self._tx_url(tx.pk))
        self.assertEqual(response.status_code, 401)

    def test_status_returns_transaction(self):
        tx = BodyPhotoTransaction.objects.create(user=self.user)
        response = self.client.get(self._tx_url(tx.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["transaction_id"], str(tx.pk))
        self.assertEqual(response.data["status"], "in_progress")

    def test_status_unknown_id_returns_404(self):
        import uuid  # noqa: PLC0415

        response = self.client.get(self._tx_url(uuid.uuid4()))
        self.assertEqual(response.status_code, 404)

    def test_status_other_users_transaction_returns_404(self):
        other = User.objects.create(username="kakao_2")
        tx = BodyPhotoTransaction.objects.create(user=other)
        response = self.client.get(self._tx_url(tx.pk))
        self.assertEqual(response.status_code, 404)

    # ---- mock 완료 처리 (10초 지연 없이 완료 로직만 직접 검증) ----

    def test_complete_updates_details_but_not_height_weight(self):
        BodyMeasurement.objects.create(
            user=self.user, height="175.5", weight="70.0", chest="90.0"
        )
        tx = BodyPhotoTransaction.objects.create(user=self.user)

        body_inference.complete_measurement(tx.pk)

        tx.refresh_from_db()
        self.assertEqual(tx.status, BodyPhotoTransaction.Status.SUCCEEDED)
        measurement = BodyMeasurement.objects.get(user=self.user)
        # 키·몸무게는 절대 변경되지 않는다.
        self.assertEqual(str(measurement.height), "175.5")
        self.assertEqual(str(measurement.weight), "70.0")
        # 상세 수치는 하드코딩 mock 값으로 갱신된다.
        for field, value in body_inference.FAKE_DETAIL_MEASUREMENTS.items():
            self.assertEqual(getattr(measurement, field), value, field)

    def test_complete_creates_measurement_if_missing(self):
        """치수 입력 전 사용자도 mock 완료 시 상세 수치가 생성된다 (키·몸무게는 null 유지)."""
        tx = BodyPhotoTransaction.objects.create(user=self.user)

        body_inference.complete_measurement(tx.pk)

        measurement = BodyMeasurement.objects.get(user=self.user)
        self.assertIsNone(measurement.height)
        self.assertIsNone(measurement.weight)
        self.assertEqual(
            measurement.chest, body_inference.FAKE_DETAIL_MEASUREMENTS["chest"]
        )

    def test_complete_skips_already_finished_transaction(self):
        tx = BodyPhotoTransaction.objects.create(
            user=self.user, status=BodyPhotoTransaction.Status.FAILED
        )

        body_inference.complete_measurement(tx.pk)

        tx.refresh_from_db()
        self.assertEqual(tx.status, BodyPhotoTransaction.Status.FAILED)
        self.assertFalse(BodyMeasurement.objects.filter(user=self.user).exists())

    # 커넥션 정리 함수 2종은 테스트 트랜잭션의 커넥션을 닫아버리므로 mock 처리한다.
    @patch("apps.users.services.body_inference.connections")
    @patch("apps.users.services.body_inference.close_old_connections")
    @patch("apps.users.services.body_inference.time.sleep")
    @patch("apps.users.services.body_inference.complete_measurement")
    def test_run_marks_failed_on_error(
        self, mock_complete, mock_sleep, _mock_close_old, _mock_conns
    ):
        """완료 처리 중 예외가 나면 트랜잭션이 '실패'로 바뀐다."""
        mock_complete.side_effect = RuntimeError("boom")
        tx = BodyPhotoTransaction.objects.create(user=self.user)

        body_inference._run_fake_measurement(tx.pk)

        mock_sleep.assert_called_once_with(body_inference.FAKE_DELAY_SECONDS)
        tx.refresh_from_db()
        self.assertEqual(tx.status, BodyPhotoTransaction.Status.FAILED)
