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
 * 카카오 REST API 키 — authorize 요청의 client_id 로 쓴다.
 * 공개키라 앱에 둬도 안전하다. (client_secret 은 백엔드 전용, 앱엔 절대 넣지 않음)
 * 카카오 개발자 콘솔에서 발급받아 .env 의 EXPO_PUBLIC_KAKAO_REST_API_KEY 에 넣으면 된다.
 */
export const KAKAO_REST_API_KEY = process.env.EXPO_PUBLIC_KAKAO_REST_API_KEY ?? '';

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
 *   POST /api/v1/auth/{provider}/login/   authorization code → JWT
 *     body: { code, redirect_uri(kakao·google 필수), state(naver 필수) }
 *     resp: { access, refresh, user, is_new_user }
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
