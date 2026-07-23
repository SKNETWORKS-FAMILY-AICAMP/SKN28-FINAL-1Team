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

/**
 * 네이버 로그인 (네이티브 SDK, @react-native-seoul/naver-login).
 * consumerKey/Secret 은 네이버 개발자센터 발급값. 네이버 모바일 SDK 는 secret 을 앱에
 * 내장하도록 요구하므로(카카오 네이티브 키와 동일한 준공개값) EXPO_PUBLIC_ 로 주입한다 — .env(gitignore).
 * URL_SCHEME 은 iOS 콜백용으로 우리가 정하는 값이며, app.json 플러그인 설정(urlScheme)과 반드시 일치해야 한다.
 */
export const NAVER_CONSUMER_KEY = process.env.EXPO_PUBLIC_NAVER_CONSUMER_KEY ?? '';
export const NAVER_CONSUMER_SECRET = process.env.EXPO_PUBLIC_NAVER_CONSUMER_SECRET ?? '';
export const NAVER_URL_SCHEME =
  process.env.EXPO_PUBLIC_NAVER_URL_SCHEME ?? 'cozynaverlogin';

/**
 * 구글 로그인 (네이티브 SDK, @react-native-google-signin/google-signin).
 * webClientId = Google Cloud "웹 애플리케이션" 클라이언트(백엔드 토큰 검증/aud 기준),
 * iosClientId = "iOS" 클라이언트. app.json 의 iosUrlScheme 은 iosClientId 를 역순(reversed)한 값이어야 한다.
 */
export const GOOGLE_WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? '';
export const GOOGLE_IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? '';

/**
 * 키가 채워졌을 때만 해당 SDK 를 초기화/호출한다.
 * 미설정(스캐폴딩) 상태에선 네이티브 SDK 를 건드리지 않아, 재빌드 전에도 앱이 안전하게 뜬다.
 */
export const isNaverConfigured = (): boolean =>
  Boolean(NAVER_CONSUMER_KEY && NAVER_CONSUMER_SECRET);
export const isGoogleConfigured = (): boolean =>
  Boolean(GOOGLE_WEB_CLIENT_ID || GOOGLE_IOS_CLIENT_ID);

/**
 * 인증 엔드포인트 (api/apps/users/urls.py 기준).
 *   POST /api/v1/auth/{provider}/login/   → { access, refresh, user, is_new_user }
 *     body (제공자별):
 *       - kakao : { access_token }        (네이티브 SDK)
 *       - naver : { access_token }        (네이티브 SDK)
 *       - google: { access_token }        (네이티브 SDK)
 *       - apple : { identity_token, ... }  (iOS 네이티브, 백엔드 미구현)
 *     ⚠️ naver/google 의 access_token 방식은 백엔드가 _TOKEN_LOGIN_PROVIDERS 에
 *        naver/google 을 추가해야 동작한다(현재 kakao 전용). 팀장 백엔드 변경 대기.
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

/**
 * 홈 화면 통합 조회 (api/apps/home/urls.py 기준).
 *   GET /api/v1/home/?lat=&lon=  → { nickname, weather, today_look, quick_recommends, closet_count, saved_look_count }
 *   - lat/lon 생략 시 백엔드가 서울시청 좌표로 대체. (위치 권한 붙기 전까진 생략 호출)
 *   - JWT 필요.
 */
export const HomeEndpoint = '/api/v1/home/';

/**
 * 신체치수 (api/apps/users/urls.py 기준). 전부 JWT 필요.
 *   GET   /api/v1/users/me/body/         → 전체 치수 (미입력 필드는 null)
 *   PUT   /api/v1/users/me/body/basic/   { height, weight }  (둘 다 필수)
 *   PATCH /api/v1/users/me/body/detail/  { chest,waist,hip,thigh,calf,arm,shoulder }  (전부 선택)
 *   ※ 수치는 Decimal 소수 1자리(1~999.9). 사진 업로드(photos)는 다음 단계에서 연동.
 */
export const BodyEndpoints = {
  me: '/api/v1/users/me/body/',
  basic: '/api/v1/users/me/body/basic/',
  detail: '/api/v1/users/me/body/detail/',
} as const;
