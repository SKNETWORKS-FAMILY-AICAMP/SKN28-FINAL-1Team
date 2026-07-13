import { useSyncExternalStore } from 'react';

import { AuthEndpoints } from '@/constants/config';
import { api, onUnauthorized } from '@/lib/apiClient';
import { clearTokens, getAccessToken, saveTokens } from '@/lib/secureStore';

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
};

let state: AuthState = { status: 'loading', user: null };
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
    const token = await getAccessToken();
    if (!token) {
      setState({ status: 'guest', user: null });
      return;
    }
    try {
      const user = await api.get<AuthUser>(AuthEndpoints.me);
      setState({ status: 'authed', user });
    } catch {
      // 토큰이 있으나 검증 실패 → 게스트로. (401 이면 apiClient 가 이미 토큰 정리)
      setState({ status: 'guest', user: null });
    }
  },

  /** 로그인 성공(일반/소셜 공통): 토큰 저장 + 상태 갱신 */
  async signIn(
    tokens: { access: string; refresh: string },
    user: AuthUser,
  ): Promise<void> {
    await saveTokens(tokens.access, tokens.refresh);
    setState({ status: 'authed', user });
  },

  /** 로그아웃: simplejwt(stateless)라 서버 엔드포인트가 없다 → 클라이언트 토큰 폐기로 처리 */
  async signOut(): Promise<void> {
    await clearTokens();
    setState({ status: 'guest', user: null });
  },
};

// 세션 만료(재발급 실패) → 게스트로 강등. (apiClient 가 토큰은 이미 삭제함)
onUnauthorized(() => {
  setState({ status: 'guest', user: null });
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
    signIn: authStore.signIn,
    signOut: authStore.signOut,
  };
}
