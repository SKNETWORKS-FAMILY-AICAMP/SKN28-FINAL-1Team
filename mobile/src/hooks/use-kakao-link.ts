/**
 * 카카오톡 초대 카드로 앱이 열렸을 때 초대장 화면으로 보내는 훅.
 *
 * 카카오는 앱이 깔린 사람에게는 웹 링크 대신 **앱을 직접 실행**한다. 이때 들어오는
 * URL 이 expo-router 의 경로 규칙과 전혀 다르게 생겨서(아래 참고) 라우터가 스스로
 * 매칭하지 못한다. 그래서 URL 을 직접 받아 `/invite?code=` 로 갈아 끼운다.
 *
 *   안드로이드 : kakao{네이티브앱키}://kakaolink?code=ABC123
 *   iOS        : kakao{네이티브앱키}://kakaolink?code=ABC123
 *   (웹 링크로 들어온 경우 : https://.../invite?code=ABC123 — 이건 라우터가 처리한다)
 *
 * 앱이 꺼져 있다가 링크로 켜진 경우와, 이미 떠 있는데 링크가 온 경우를 모두 받아야
 * 한다 — 전자는 getInitialURL(), 후자는 addEventListener('url'). 하나만 달면
 * "앱을 처음 켤 때만 되고 두 번째부터 안 되는" 증상이 나온다.
 */
import * as Linking from 'expo-linking';
import { useRouter } from 'expo-router';
import { useEffect } from 'react';

/** 카카오가 넘겨준 참여 코드를 뽑는다. 카카오 링크가 아니면 null. */
export function parseKakaoInviteCode(url: string | null): string | null {
  if (!url) return null;
  // 카카오 실행 URL 의 host 는 항상 kakaolink 다. 우리 앱 스킴(mobile://)이나
  // 웹 URL 은 라우터가 알아서 처리하므로 여기서 가로채지 않는다.
  if (!url.includes('kakaolink')) return null;

  try {
    const { queryParams } = Linking.parse(url);
    const code = queryParams?.code;
    const value = Array.isArray(code) ? code[0] : code;
    return typeof value === 'string' && value.trim() ? value.trim().toUpperCase() : null;
  } catch {
    return null;
  }
}

export function useKakaoInviteLink(): void {
  const router = useRouter();

  useEffect(() => {
    let alive = true;

    const go = (url: string | null) => {
      const code = parseKakaoInviteCode(url);
      if (!alive || !code) return;
      router.push(`/invite?code=${encodeURIComponent(code)}`);
    };

    // 앱이 꺼져 있다가 링크로 켜진 경우
    void Linking.getInitialURL().then(go);
    // 앱이 이미 떠 있는 상태로 링크가 온 경우
    const sub = Linking.addEventListener('url', ({ url }) => go(url));

    return () => {
      alive = false;
      sub.remove();
    };
  }, [router]);
}
