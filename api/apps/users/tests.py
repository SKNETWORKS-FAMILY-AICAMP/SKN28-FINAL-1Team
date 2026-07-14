"""users 앱 테스트.

OAuth 제공사 호출은 mock 처리한다 (외부 네트워크 의존 금지).
실행: python manage.py test apps.users
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import SocialAccount, User
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
        """google 등 token 방식 미지원 제공사는 서비스 계층에서 OAuthError."""
        from apps.users.services.oauth import OAuthError  # noqa: PLC0415

        mock_auth.side_effect = OAuthError("미지원")
        url = reverse("users:social-login", kwargs={"provider": "google"})
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
        from apps.users.services import oauth

        with self.assertRaises(oauth.OAuthError):
            oauth.authenticate_with_token("google", "token")


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
