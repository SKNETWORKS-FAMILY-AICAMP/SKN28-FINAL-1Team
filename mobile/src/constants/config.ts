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

/** 백엔드가 지원하는 소셜 제공자. ⚠️ 애플은 아래 APPLE_LOGIN_ENABLED 참고. */
export type SocialProvider = 'kakao' | 'naver' | 'google';

/**
 * 애플 로그인 노출 여부. **지금은 끈다.**
 *
 * 백엔드가 애플에 **code 방식만** 열어 두었고(`authenticate_with_token` 은 애플 미지원),
 * code 방식은 `redirect_uri` 를 필수로 받는다. 그런데 네이티브 Apple Sign In 에는
 * 리디렉트 주소라는 게 없어서 앱이 채울 값이 없다 → 누르면 반드시 실패한다.
 * 반드시 실패하는 버튼을 띄워 두느니 감춘다.
 *
 * ⚠️ App Store 정책(4.8)상 다른 소셜 로그인을 제공하면 Sign in with Apple 이 필요하다.
 *    **심사 제출 전에는 백엔드가 네이티브(bundle id 클라이언트·redirect_uri 없음)를
 *    받아주도록 고치고 이 값을 다시 true 로 되돌려야 한다.**
 * 앱 쪽 구현(loginWithApple)은 그대로 두었으므로 이 한 줄만 바꾸면 다시 나온다.
 */
export const APPLE_LOGIN_ENABLED = false;

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
  signup: '/api/v1/auth/signup/',
  login: '/api/v1/auth/login/',
  verifyEmail: '/api/v1/auth/email/verify/',
  resendEmail: '/api/v1/auth/email/resend/',
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
 * 착장 사진 분석. 인증 없이 호출할 수 있고, JWT가 있으면 개인화 정보를 반영한다.
 * POST multipart { image, lat?, lon? } → { status, evaluation, context }
 */
export const OutfitAnalysisEndpoint = '/api/v1/outfits/analyze/';

/**
 * 착장 분석 기록 (api/apps/recommend/urls.py 기준).
 *   GET  /api/v1/outfits/analyses/?limit=&offset=&status=  → { count, limit, offset, results[] }
 *   GET  /api/v1/outfits/analyses/{id}/                    → 단건 (진행 상태 겸 결과)
 *   POST /api/v1/outfits/analyses/claim/  { claim_tokens[] } → 비로그인 접수 건을 계정으로 이전
 *
 * ⚠️ 목록만 JWT 필수다. 단건 조회는 AllowAny — UUID를 아는 사람이면 24시간 안에 볼 수 있다.
 *    익명 기록(user=NULL)은 목록에서 빠지므로, 비회원이 분석한 건은 claim 을 거쳐야 목록에 나타난다.
 *    claim 토큰은 발급 후 60분만 유효하다(조회 24시간과 다름).
 */
export const OutfitHistoryEndpoints = {
  list: '/api/v1/outfits/analyses/',
  detail: (analysisId: string) => `/api/v1/outfits/analyses/${analysisId}/`,
  claim: '/api/v1/outfits/analyses/claim/',
} as const;

/**
 * 신체치수 (api/apps/users/urls.py 기준). 전부 JWT 필요.
 *   GET   /api/v1/users/me/body/         → 전체 치수 (미입력 필드는 null)
 *   PUT   /api/v1/users/me/body/basic/   { height, weight }  (둘 다 필수)
 *   PATCH /api/v1/users/me/body/detail/  { chest,waist,hip,thigh,calf,arm,shoulder }  (전부 선택)
 *   POST  /api/v1/users/me/body/photos/  multipart front_image/side_image → 202 { transaction_id, status }
 *   GET   /api/v1/users/me/body/photos/{id}/  → { status: in_progress|succeeded|failed } (폴링)
 *   ※ 수치는 Decimal 소수 1자리(1~999.9). 사진 접수 후 백엔드가 상세치수를 채우면 GET body 로 읽는다.
 */
export const BodyEndpoints = {
  me: '/api/v1/users/me/body/',
  basic: '/api/v1/users/me/body/basic/',
  detail: '/api/v1/users/me/body/detail/',
  photos: '/api/v1/users/me/body/photos/',
  photo: (transactionId: string) => `/api/v1/users/me/body/photos/${transactionId}/`,
} as const;

/**
 * 추구미·선호도 (api/apps/users/urls.py 기준). JWT 필요.
 *   GET /api/v1/users/me/pursuit/  → { preferred:{카테고리키:[code]}, avoided:{카테고리키:[code]} }
 *   PUT /api/v1/users/me/pursuit/  같은 형식으로 통째로 저장(upsert, 전체 교체)
 *   ⚠️ PUT 은 카테고리 키가 백엔드 PREFERENCE_CATEGORIES(11개)와 정확히 일치해야 통과한다.
 *   ※ 옵션 목록(GET /api/v1/preference-options/)은 로컬 pursuit-options.ts 를 그대로 쓴다(프론트 기준).
 */
export const PursuitEndpoint = '/api/v1/users/me/pursuit/';

/**
 * 옷장 (api/apps/wardrobe/urls.py 기준). 전부 JWT 필요.
 *
 * 등록은 **비동기**다 — 사진을 올리면 202 로 job_id 만 받고, 이미지 프로세서가
 * 누끼·분류를 끝내면 콜백으로 아이템이 채워진다. 프론트는 job 을 폴링해야 한다.
 * 사진 1장에서 아이템이 **여러 개** 나올 수 있다(세그멘테이션).
 *
 *   POST  /api/v1/wardrobe/uploads/           multipart { image } → 202 { job_id, status }
 *   GET   /api/v1/wardrobe/uploads/{job_id}/  → { id, status, error_message, created_at, finished_at, items[] }
 *         status: PENDING | PROCESSING | DONE | FAILED
 *   GET   /api/v1/wardrobe/items/             → WardrobeApiItem[]  (?category_large=&confirmed=true|false)
 *   PATCH /api/v1/wardrobe/items/{id}/        태그 수정 + confirmed → 수정된 아이템
 *   DELETE /api/v1/wardrobe/items/{id}/       → 204
 *
 * ⚠️ 새로 만들어진 아이템은 confirmed=false(사용자 확인 대기)이고 추천 검색에서 제외된다.
 *    사용자가 태그를 확인·수정한 뒤 PATCH 로 confirmed=true 를 보내야 옷장에 정식 편입된다.
 * ⚠️ 업로드 제한: 15MB 이하, jpeg/png/webp/heic.
 */
export const WardrobeEndpoints = {
  uploads: '/api/v1/wardrobe/uploads/',
  uploadJob: (jobId: string) => `/api/v1/wardrobe/uploads/${jobId}/`,
  items: '/api/v1/wardrobe/items/',
  item: (itemId: string) => `/api/v1/wardrobe/items/${itemId}/`,
} as const;
