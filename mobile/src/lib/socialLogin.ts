import { login as kakaoNativeLogin } from '@react-native-kakao/user';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as AuthSession from 'expo-auth-session';
import { Platform } from 'react-native';

import { AuthEndpoints, GOOGLE_CLIENT_ID, NAVER_CLIENT_ID } from '@/constants/config';
import { api } from '@/lib/apiClient';
import { authStore, type AuthUser } from '@/state/auth';

/**
 * 소셜 로그인.
 * 프론트는 인가정보(토큰/코드)만 받아 백엔드로 넘기고, JWT 발급은 백엔드가 한다.
 *
 * - 카카오: 네이티브 SDK(@react-native-kakao)로 access_token → 백엔드
 *   (카카오는 커스텀 스킴 redirect 를 허용하지 않아 code 방식 불가)
 * - 네이버/구글: expo-auth-session 으로 code → 백엔드
 * - 애플: iOS 네이티브(expo-apple-authentication)로 identity_token → 백엔드
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

function isCancel(e: unknown): boolean {
  const err = e as { code?: string; message?: string };
  return `${err?.code ?? ''} ${err?.message ?? ''}`.toLowerCase().includes('cancel');
}

/**
 * 카카오 로그인 — 네이티브 SDK.
 * SDK 초기화(initializeKakaoSDK)는 앱 시작 시 _layout 에서 1회 수행된다.
 * ⚠️ 백엔드 필드명은 팀 백엔드와 맞춘다 (현재 access_token 으로 가정).
 */
export async function loginWithKakao(): Promise<SocialLoginResult> {
  try {
    const token = await kakaoNativeLogin();
    return finishLogin(AuthEndpoints.socialLogin('kakao'), {
      access_token: token.accessToken,
    });
  } catch (e) {
    if (isCancel(e)) return null; // 사용자가 카카오 로그인 취소
    throw e;
  }
}

/** expo-auth-session(code 방식)으로 처리하는 제공자 */
type CodeProvider = 'naver' | 'google';

type ProviderConfig = {
  clientId: string;
  authorizationEndpoint: string;
  scopes: string[];
};

// promptAsync 는 authorizationEndpoint 만 있으면 된다 (토큰 교환은 백엔드 몫).
const PROVIDERS: Record<CodeProvider, ProviderConfig> = {
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

/**
 * 코드 방식 소셜 로그인 (naver / google).
 * - naver: 백엔드가 state 필요 (CSRF 검증)
 * - google: 백엔드가 redirect_uri 필요
 * ⚠️ 두 제공자 모두 커스텀 스킴 redirect 허용 여부는 콘솔 설정에서 확인 필요.
 */
export async function loginWith(provider: CodeProvider): Promise<SocialLoginResult> {
  const cfg = PROVIDERS[provider];
  if (!cfg.clientId) {
    throw new Error(`${provider} client id 가 설정되지 않았습니다. (.env 확인)`);
  }

  const redirectUri = AuthSession.makeRedirectUri({
    scheme: 'mobile',
    path: `oauth/${provider}`,
  });

  const request = new AuthSession.AuthRequest({
    clientId: cfg.clientId,
    redirectUri,
    responseType: AuthSession.ResponseType.Code,
    scopes: cfg.scopes,
    usePKCE: false,
  });

  const result = await request.promptAsync({
    authorizationEndpoint: cfg.authorizationEndpoint,
  });

  if (result.type === 'error') {
    throw new Error(result.error?.message ?? `${provider} 인증에 실패했습니다.`);
  }
  if (result.type !== 'success') {
    return null; // cancel / dismiss
  }

  const code = result.params.code;
  if (!code) {
    throw new Error(`${provider} 인가 코드를 받지 못했습니다.`);
  }

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
    if ((e as { code?: string })?.code === 'ERR_REQUEST_CANCELED') return null;
    throw e;
  }

  if (!credential.identityToken) {
    throw new Error('애플 인증 토큰을 받지 못했습니다.');
  }

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

  return finishLogin('/api/v1/auth/apple/login/', body);
}
