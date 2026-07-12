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
