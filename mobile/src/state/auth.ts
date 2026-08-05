import { useSyncExternalStore } from 'react';

import { AuthEndpoints } from '@/constants/config';
import { DEMO_USER } from '@/constants/demo';
import { api, onUnauthorized } from '@/lib/apiClient';
import {
  clearDemoFlag,
  clearTokens,
  getAccessToken,
  hasDemoFlag,
  saveDemoFlag,
  saveTokens,
} from '@/lib/secureStore';

/**
 * 전역 인증 상태.
 * draft-item.ts 와 동일한 "경량 모듈 스토어 + useSyncExternalStore" 패턴.
 * 스토어를 모듈로 두면 React 밖(apiClient)에서도 세션을 조작할 수 있다.
 *
 * 일반 로그인/소셜 로그인 모두 성공하면 signIn(tokens, user) 하나로 수렴한다.
 */

export type SocialAccountInfo = {
  provider: string;
  email: string | null;
  connected_at: string;
};

/** 백엔드 UserSerializer 응답 형식 (api/apps/users/serializers.py) */
export type AuthUser = {
  id: number;
  username: string;
  email: string;
  nickname: string | null;
  profile_image: string | null;
  social_accounts: SocialAccountInfo[];
};

type Status = 'loading' | 'authed' | 'guest';

type AuthState = {
  status: Status;
  user: AuthUser | null;
  /** 토큰 없는 체험 세션(이메일/비번 로그인 API 부재로 인한 임시 진입). 화면은 목업 데이터를 쓴다. */
  isDemo: boolean;
};

let state: AuthState = { status: 'loading', user: null, isDemo: false };
const listeners = new Set<() => void>();

function setState(next: Partial<AuthState>): void {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

export const authStore = {
  getState: (): AuthState => state,

  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  /** 앱 시작 시 1회: 저장된 토큰으로 세션 복원 */
  async bootstrap(): Promise<void> {
    try {
      const token = await getAccessToken();
      if (token) {
        const user = await api.get<AuthUser>(AuthEndpoints.me);
        setState({ status: 'authed', user, isDemo: false });
        return;
      }
      // 토큰은 없지만 데모로 들어온 세션이면 그대로 복원한다(웹 새로고침·앱 재시작 대비).
      if (await hasDemoFlag()) {
        setState({ status: 'authed', user: DEMO_USER, isDemo: true });
        return;
      }
    } catch {
      // 토큰 없음/검증실패/저장소 접근불가 → 게스트. (401 이면 apiClient 가 토큰 정리)
    }
    setState({ status: 'guest', user: null, isDemo: false });
  },

  /** 로그인 성공(일반/소셜 공통): 토큰 저장 + 상태 갱신 */
  async signIn(
    tokens: { access: string; refresh: string },
    user: AuthUser,
  ): Promise<void> {
    await saveTokens(tokens.access, tokens.refresh);
    await clearDemoFlag();
    setState({ status: 'authed', user, isDemo: false });
  },

  /**
   * 데모 로그인: 토큰 없이 '로그인한 사용자' 상태로만 진입한다.
   * 백엔드에 이메일/비번 로그인이 생기면 signIn 으로 대체하고 이 메서드는 삭제한다.
   */
  async signInDemo(): Promise<void> {
    setState({ status: 'authed', user: DEMO_USER, isDemo: true });
    await saveDemoFlag();
  },

  /** 비회원 둘러보기: 로그인하지 않은 상태를 명시적으로 확정한다(직전 데모 세션도 정리). */
  async continueAsGuest(): Promise<void> {
    setState({ status: 'guest', user: null, isDemo: false });
    await clearDemoFlag();
  },

  /**
   * 표시 이름 저장 — PATCH /users/me/ 로 서버에 남기고 로컬 세션도 갱신한다.
   * 예전엔 로컬에만 두어 앱을 다시 켜면 사라졌다(서버는 진작 받을 준비가 돼 있었다).
   */
  async updateNickname(nickname: string): Promise<AuthUser> {
    const user = await api.patch<AuthUser>(AuthEndpoints.me, { nickname });
    setState({ user });
    return user;
  },

  /** 로그아웃: simplejwt(stateless)라 서버 엔드포인트가 없다 → 클라이언트 토큰 폐기로 처리 */
  async signOut(): Promise<void> {
    await Promise.all([clearTokens(), clearDemoFlag()]);
    setState({ status: 'guest', user: null, isDemo: false });
  },
};

// 세션 만료(재발급 실패) → 게스트로 강등. (apiClient 가 토큰은 이미 삭제함)
// 데모 세션은 애초에 토큰이 없어 401 이 정상이므로 강등하지 않는다 — 화면별 에러로만 드러난다.
onUnauthorized(() => {
  if (state.isDemo) return;
  setState({ status: 'guest', user: null, isDemo: false });
});

/** 화면에서 인증 상태를 구독 */
export function useAuth() {
  const snapshot = useSyncExternalStore(
    authStore.subscribe,
    authStore.getState,
    authStore.getState,
  );
  return {
    status: snapshot.status,
    user: snapshot.user,
    isLoggedIn: snapshot.status === 'authed',
    isLoading: snapshot.status === 'loading',
    isDemo: snapshot.isDemo,
    signIn: authStore.signIn,
    signOut: authStore.signOut,
  };
}
