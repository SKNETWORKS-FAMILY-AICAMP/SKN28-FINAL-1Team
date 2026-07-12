"""
소셜 로그인 OAuth 서비스 (naver / kakao / google 직접 구현).

흐름 (Authorization Code Grant):
  1. 프론트가 제공사 로그인 페이지에서 authorization code를 받는다.
  2. 프론트가 백엔드로 code(+ redirect_uri, state)를 전달한다.
  3. 백엔드가 code를 제공사 토큰 엔드포인트에서 access_token으로 교환한다.
  4. access_token으로 제공사 프로필 API를 호출해 사용자 정보를 얻는다.
  5. SocialAccount를 조회/생성하고 서비스 자체 JWT를 발급한다 (views에서 처리).

엔드포인트/파라미터 출처:
- 네이버: https://developers.naver.com/docs/login/api/
- 카카오: https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
- 구글:   https://developers.google.com/identity/protocols/oauth2/web-server
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from django.conf import settings


class OAuthError(Exception):
    """제공사 통신/응답 오류. 뷰에서 401/502로 변환한다."""


@dataclass(frozen=True)
class SocialProfile:
    provider: str
    provider_user_id: str
    email: str
    nickname: str
    profile_image: str
    raw: Dict[str, Any]


# client_secret이 필수인 제공사 (카카오는 콘솔에서 활성화한 경우만 선택 사용)
_SECRET_REQUIRED = {"naver", "google"}


def _provider_config(provider: str) -> Dict[str, str]:
    config = settings.OAUTH_PROVIDERS.get(provider)
    if not config:
        raise OAuthError(f"지원하지 않는 provider: {provider}")
    if not config.get("client_id"):
        raise OAuthError(f"{provider} OAuth client_id가 설정되지 않았습니다 (.env 확인).")
    if provider in _SECRET_REQUIRED and not config.get("client_secret"):
        raise OAuthError(f"{provider} OAuth client_secret이 설정되지 않았습니다 (.env 확인).")
    return config


def _post_token(url: str, data: Dict[str, str]) -> Dict[str, Any]:
    try:
        response = requests.post(
            url,
            data=data,
            headers={"Accept": "application/json"},
            timeout=settings.OAUTH_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise OAuthError(f"토큰 엔드포인트 요청 실패: {exc}") from exc
    payload = _json_or_error(response)
    if "error" in payload or "access_token" not in payload:
        raise OAuthError(f"토큰 교환 실패: {payload.get('error_description') or payload}")
    return payload


def _get_profile(url: str, access_token: str) -> Dict[str, Any]:
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=settings.OAUTH_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise OAuthError(f"프로필 요청 실패: {exc}") from exc
    return _json_or_error(response)


def _json_or_error(response: requests.Response) -> Dict[str, Any]:
    if response.status_code >= 400:
        raise OAuthError(f"제공사 응답 오류: status={response.status_code}, body={response.text[:300]}")
    try:
        return response.json()
    except ValueError as exc:
        raise OAuthError(f"JSON 파싱 실패: {response.text[:300]}") from exc


# ------------------------------------------------------------
# 토큰 교환
# ------------------------------------------------------------


def exchange_code(
    provider: str,
    code: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
) -> str:
    """authorization code → access_token."""
    config = _provider_config(provider)
    data = {
        "grant_type": "authorization_code",
        "client_id": config["client_id"],
        "code": code,
    }
    if provider == "naver":
        # 네이버는 redirect_uri 대신 state 검증을 사용한다.
        data["client_secret"] = config["client_secret"]
        if state:
            data["state"] = state
    elif provider == "kakao":
        # 카카오는 client_secret이 선택(콘솔에서 활성화한 경우만).
        if redirect_uri:
            data["redirect_uri"] = redirect_uri
        if config.get("client_secret"):
            data["client_secret"] = config["client_secret"]
    elif provider == "google":
        data["client_secret"] = config["client_secret"]
        if redirect_uri:
            data["redirect_uri"] = redirect_uri

    payload = _post_token(config["token_url"], data)
    return payload["access_token"]


# ------------------------------------------------------------
# 프로필 조회 → 공통 스키마 정규화
# ------------------------------------------------------------


def fetch_profile(provider: str, access_token: str) -> SocialProfile:
    config = _provider_config(provider)
    raw = _get_profile(config["profile_url"], access_token)

    if provider == "naver":
        # {"resultcode": "00", "response": {"id", "email", "nickname", "profile_image", ...}}
        body = raw.get("response") or {}
        if raw.get("resultcode") != "00" or not body.get("id"):
            raise OAuthError(f"네이버 프로필 응답 오류: {raw}")
        return SocialProfile(
            provider=provider,
            provider_user_id=str(body["id"]),
            email=body.get("email") or "",
            nickname=body.get("nickname") or "",
            profile_image=body.get("profile_image") or "",
            raw=raw,
        )

    if provider == "kakao":
        # {"id": 123, "kakao_account": {"email", "profile": {"nickname", "profile_image_url"}}}
        if not raw.get("id"):
            raise OAuthError(f"카카오 프로필 응답 오류: {raw}")
        account = raw.get("kakao_account") or {}
        profile = account.get("profile") or {}
        return SocialProfile(
            provider=provider,
            provider_user_id=str(raw["id"]),
            email=account.get("email") or "",
            nickname=profile.get("nickname") or "",
            profile_image=profile.get("profile_image_url") or "",
            raw=raw,
        )

    if provider == "google":
        # OIDC userinfo: {"sub", "email", "name", "picture"}
        if not raw.get("sub"):
            raise OAuthError(f"구글 프로필 응답 오류: {raw}")
        return SocialProfile(
            provider=provider,
            provider_user_id=str(raw["sub"]),
            email=raw.get("email") or "",
            nickname=raw.get("name") or "",
            profile_image=raw.get("picture") or "",
            raw=raw,
        )

    raise OAuthError(f"지원하지 않는 provider: {provider}")


def authenticate(
    provider: str,
    code: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
) -> SocialProfile:
    """code 교환 + 프로필 조회를 한 번에."""
    access_token = exchange_code(provider, code, redirect_uri, state)
    return fetch_profile(provider, access_token)
