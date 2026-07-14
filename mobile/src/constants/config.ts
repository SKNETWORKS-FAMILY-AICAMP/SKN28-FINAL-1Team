/**
 * 앱 전역 설정. API 주소 / 인증 엔드포인트.
 *
 * API_BASE_URL 은 EXPO_PUBLIC_API_URL 환경변수로 덮어쓴다.
 *   - 예) EXPO_PUBLIC_API_URL=https://api.cozy.example  npx expo start
 *   - ⚠️ 실기기에서 로컬 백엔드에 붙으려면 localhost 대신 PC의 LAN IP 를 써야 한다.
 *        예) EXPO_PUBLIC_API_URL=http://192.168.0.10:8000
 *
 * 경로/응답 형식은 팀 백엔드(SKN28-FINAL-1Team, Django/DRF + simplejwt) 실제 구현 기준.
 */
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

/** 백엔드가 지원하는 소셜 제공자. ⚠️ 애플은 아직 백엔드 미지원(naver/kakao/google만). */
export type SocialProvider = 'kakao' | 'naver' | 'google';

/**
 * 카카오 네이티브 앱 키 — 네이티브 SDK 초기화(initializeKakaoSDK)에 사용.
 * 앱 바이너리(URL 스킴)에 어차피 포함되는 준공개값이라 app.json/여기에 둔다.
 * (client_secret 같은 진짜 시크릿은 백엔드 전용, 앱엔 절대 넣지 않음)
 */
export const KAKAO_NATIVE_APP_KEY =
  process.env.EXPO_PUBLIC_KAKAO_NATIVE_APP_KEY ?? '1366adcd2e8c643a4b5471fabd32b6ea';

/** 네이버 Client ID (authorize 요청용). client_secret 은 백엔드 전용. */
export const NAVER_CLIENT_ID = process.env.EXPO_PUBLIC_NAVER_CLIENT_ID ?? '';

/**
 * 구글 OAuth Client ID (authorize 요청용).
 * ⚠️ 백엔드가 code 를 교환하는 구조라 client 종류/redirect_uri 방식을 백엔드와 맞춰야 한다
 *    (구글 웹 클라이언트는 https redirect 를 요구하는 등 카카오보다 까다롭다).
 */
export const GOOGLE_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID ?? '';

/**
 * 인증 엔드포인트 (api/apps/users/urls.py 기준).
 *   POST /api/v1/auth/{provider}/login/   → { access, refresh, user, is_new_user }
 *     body (제공자별):
 *       - kakao : { access_token }        (네이티브 SDK)
 *       - naver : { code, state }          (expo-auth-session)
 *       - google: { code, redirect_uri }   (expo-auth-session)
 *       - apple : { identity_token, ... }  (iOS 네이티브, 백엔드 미구현)
 *   POST /api/v1/auth/token/refresh/      { refresh } → { access }
 *   GET/PATCH /api/v1/users/me/           내 정보 (Bearer 필요)
 *
 * ※ simplejwt(stateless)라 서버 로그아웃 엔드포인트는 없다 → 로그아웃은 클라이언트 토큰 폐기.
 */
export const AuthEndpoints = {
  socialLogin: (provider: SocialProvider) => `/api/v1/auth/${provider}/login/`,
  refresh: '/api/v1/auth/token/refresh/',
  me: '/api/v1/users/me/',
} as const;
