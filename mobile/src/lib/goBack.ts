import { Href, router } from 'expo-router';

/**
 * 뒤로가기. 웹에서 URL 로 바로 들어오면 되돌아갈 이력이 없어 router.back() 이
 * 아무 반응도 하지 않으므로, 그럴 때는 화면이 속한 자리로 대신 보낸다.
 */
export function goBack(fallback: Href = '/(tabs)/home') {
  if (router.canGoBack()) router.back();
  else router.replace(fallback);
}
