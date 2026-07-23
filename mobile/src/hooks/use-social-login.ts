import { useCallback, useState } from 'react';

import { useToast } from '@/components/ui';
import type { SocialProvider } from '@/constants/config';
import {
  loginWithApple,
  loginWithGoogle,
  loginWithKakao,
  loginWithNaver,
  type SocialLoginResult,
} from '@/lib/socialLogin';

/** 로딩 표시 키 — 소셜 제공자 + 애플 */
type LoginKey = SocialProvider | 'apple';

/**
 * 소셜 로그인 진입점 훅.
 * - 버튼별 로딩 상태(pending)를 제공하고, 실패는 토스트로 알린다.
 * - 성공/취소 결과는 호출한 화면이 라우팅에 쓴다. (취소=null)
 */
export function useSocialLogin() {
  const toast = useToast();
  const [pending, setPending] = useState<LoginKey | null>(null);

  const run = useCallback(
    async (
      key: LoginKey,
      fn: () => Promise<SocialLoginResult>,
    ): Promise<SocialLoginResult> => {
      setPending(key);
      try {
        return await fn();
      } catch (e) {
        toast(e instanceof Error ? e.message : '로그인에 실패했어요', {
          variant: 'error',
        });
        return null;
      } finally {
        setPending(null);
      }
    },
    [toast],
  );

  return {
    pending,
    kakao: () => run('kakao', loginWithKakao),
    naver: () => run('naver', loginWithNaver),
    google: () => run('google', loginWithGoogle),
    apple: () => run('apple', loginWithApple),
  };
}
