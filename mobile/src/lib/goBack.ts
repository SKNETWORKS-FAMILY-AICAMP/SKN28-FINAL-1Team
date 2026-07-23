import { Platform } from 'react-native';
import { Href, router } from 'expo-router';

/**
 * 뒤로가기.
 *
 * 웹에서는 상세 화면들이 (tabs) 탭으로 등록돼 있어 expo-router 의 router.back() 이나
 * 브라우저 히스토리가 직전 화면이 아니라 엉뚱한 탭(예: 마이)으로 가는 경우가 있다.
 * 그래서 웹에서는 히스토리에 기대지 않고 **항상 지정된 목적지(fallback)로 확정 이동**한다.
 * (각 화면은 자신이 돌아가야 할 자리를 fallback 으로 넘긴다.)
 *
 * 네이티브에서는 정상적인 스택이라 이력이 있으면 뒤로, 없으면 fallback 으로 보낸다.
 */
export function goBack(fallback: Href = '/(tabs)/home') {
  if (Platform.OS === 'web') {
    router.replace(fallback);
    return;
  }
  if (router.canGoBack()) router.back();
  else router.replace(fallback);
}
