/**
 * 데모(체험) 계정 데이터.
 *
 * 백엔드에는 이메일/비밀번호 로그인 API 가 없다(소셜 3종 전용). 그래서 로그인 폼의
 * '로그인' 버튼은 서버 세션 대신 이 데모 계정으로 진입시킨다 — 시연에서 '로그인한
 * 사용자의 홈'과 '비회원 둘러보기'를 구분해 보여주기 위한 자리다.
 *
 * JWT 가 없어 홈 API 를 호출할 수 없으므로 홈 데이터도 여기 고정값을 쓴다.
 * 이메일/비번 로그인 API 가 생기면 이 파일과 authStore.signInDemo 를 함께 걷어낸다.
 */
import type { HomeData } from '@/hooks/use-home';
import type { AuthUser } from '@/state/auth';

export const DEMO_USER: AuthUser = {
  id: 0,
  username: 'demo',
  email: 'demo@cozy.app',
  nickname: '코지',
  profile_image: null,
  social_accounts: [],
};

export const DEMO_HOME: HomeData = {
  nickname: '코지',
  weather: {
    region: '서울',
    temperature: 24,
    sky_state: '맑음',
    is_stale: false,
    observed_at: null,
  },
  today_look: {
    comment: '볕이 좋은 날이라 밝은 톤 상의에 차분한 색 하의를 맞춰 시선을 위로 모았어요.',
    tags: ['#데일리', '#미니멀'],
    image: null,
  },
  quick_recommends: ['출근룩', '주말 나들이', '비 오는 날'],
  closet_count: 42,
  saved_look_count: 8,
};
