import * as AppleAuthentication from 'expo-apple-authentication';
import * as AuthSession from 'expo-auth-session';
import { Platform } from 'react-native';

import {
  AuthEndpoints,
  GOOGLE_CLIENT_ID,
  KAKAO_REST_API_KEY,
  NAVER_CLIENT_ID,
  type SocialProvider,
} from '@/constants/config';
import { api } from '@/lib/apiClient';
import { authStore, type AuthUser } from '@/state/auth';

/**
 * 소셜 로그인 (패턴 A).
 * 프론트는 인가정보(code / apple identity_token)만 받아 백엔드로 넘기고,
 * 실제 토큰 교환·JWT 발급은 백엔드가 한다.
 *
 * 백엔드 계약: POST /api/v1/auth/{provider}/login/  (api/apps/users/views.py)
 */

/** 백엔드 SocialLoginView 응답 형식 */
type SocialLoginResponse = {
  access: string;
  refresh: string;
  user: AuthUser;
  is_new_user: boolean;
};

/** 로그인 결과: 사용자가 취소하면 null, 성공하면 신규 유저 여부 */
export type SocialLoginResult = { isNewUser: boolean } | null;

type ProviderConfig = {
  clientId: string;
  authorizationEndpoint: string;
  scopes: string[];
};

// promptAsync 는 authorizationEndpoint 만 있으면 된다 (토큰 교환은 백엔드 몫).
const PROVIDERS: Record<SocialProvider, ProviderConfig> = {
  kakao: {
    clientId: KAKAO_REST_API_KEY,
    authorizationEndpoint: 'https://kauth.kakao.com/oauth/authorize',
    scopes: ['profile_nickname', 'account_email'],
  },
  naver: {
    clientId: NAVER_CLIENT_ID,
    authorizationEndpoint: 'https://nid.naver.com/oauth2.0/authorize',
    scopes: [],
  },
  google: {
    clientId: GOOGLE_CLIENT_ID,
    authorizationEndpoint: 'https://accounts.google.com/o/oauth2/v2/auth',
    scopes: ['openid', 'profile', 'email'],
  },
};

/** 인가정보를 백엔드에 넘겨 우리 JWT 를 받고 세션을 시작한다. */
async function finishLogin(
  path: string,
  body: Record<string, string>,
): Promise<SocialLoginResult> {
  // 아직 우리 JWT 가 없으므로 auth: false (Authorization 헤더 생략)
  const data = await api.post<SocialLoginResponse>(path, body, { auth: false });
  await authStore.signIn(
    { access: data.access, refresh: data.refresh },
    data.user,
  );
  return { isNewUser: data.is_new_user };
}

/**
 * 코드 방식 소셜 로그인 (kakao / naver / google).
 * - kakao / google: 백엔드가 redirect_uri 필요
 * - naver: 백엔드가 state 필요 (CSRF 검증)
 */
export async function loginWith(
  provider: SocialProvider,
): Promise<SocialLoginResult> {
  const cfg = PROVIDERS[provider];
  if (!cfg.clientId) {
    throw new Error(`${provider} client id 가 설정되지 않았습니다. (.env 확인)`);
  }

  // 커스텀 스킴 딥링크. 이 값과 "정확히 동일하게" 각 제공자 콘솔에 등록돼 있어야 하고,
  // 백엔드 토큰 교환에도 같은 값이 쓰이므로 로그인 요청에 함께 보낸다.
  const redirectUri = AuthSession.makeRedirectUri({
    scheme: 'mobile',
    path: `oauth/${provider}`,
  });

  const request = new AuthSession.AuthRequest({
    clientId: cfg.clientId,
    redirectUri,
    responseType: AuthSession.ResponseType.Code,
    scopes: cfg.scopes,
    usePKCE: false, // 백엔드가 redirect_uri/state 기반으로 교환 (PKCE 미사용)
  });

  const result = await request.promptAsync({
    authorizationEndpoint: cfg.authorizationEndpoint,
  });

  if (result.type === 'error') {
    throw new Error(result.error?.message ?? `${provider} 인증에 실패했습니다.`);
  }
  if (result.type !== 'success') {
    return null; // cancel / dismiss → 조용히 종료
  }

  const code = result.params.code;
  if (!code) {
    throw new Error(`${provider} 인가 코드를 받지 못했습니다.`);
  }

  // 백엔드 계약: naver 는 state, kakao/google 은 redirect_uri.
  const body: Record<string, string> =
    provider === 'naver'
      ? { code, state: request.state, redirect_uri: redirectUri }
      : { code, redirect_uri: redirectUri };

  return finishLogin(AuthEndpoints.socialLogin(provider), body);
}

/**
 * 애플 로그인 — iOS 네이티브(expo-apple-authentication).
 * code 대신 identity_token 을 백엔드로 넘긴다. 이름/이메일은 "최초 1회"만 오므로 그때 함께 전달.
 * ⚠️ 백엔드에 애플 엔드포인트(/api/v1/auth/apple/login/)가 아직 없음 → 추가되면 동작한다.
 */
export async function loginWithApple(): Promise<SocialLoginResult> {
  if (Platform.OS !== 'ios') {
    throw new Error('애플 로그인은 iOS에서만 지원됩니다.');
  }

  let credential: AppleAuthentication.AppleAuthenticationCredential;
  try {
    credential = await AppleAuthentication.signInAsync({
      requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        AppleAuthentication.AppleAuthenticationScope.EMAIL,
      ],
    });
  } catch (e) {
    // 사용자가 취소하면 ERR_REQUEST_CANCELED
    if ((e as { code?: string })?.code === 'ERR_REQUEST_CANCELED') return null;
    throw e;
  }

  if (!credential.identityToken) {
    throw new Error('애플 인증 토큰을 받지 못했습니다.');
  }

  // 이름은 최초 1회만 옴 → 이때 백엔드가 저장해야 한다.
  const fullName = credential.fullName
    ? [credential.fullName.familyName, credential.fullName.givenName]
        .filter(Boolean)
        .join(' ')
    : '';

  const body: Record<string, string> = {
    identity_token: credential.identityToken,
    ...(credential.authorizationCode
      ? { authorization_code: credential.authorizationCode }
      : {}),
    ...(fullName ? { full_name: fullName } : {}),
  };

  // TODO(backend): 애플 엔드포인트 경로/필드는 백엔드 구현 확정 시 맞춘다.
  return finishLogin('/api/v1/auth/apple/login/', body);
}
