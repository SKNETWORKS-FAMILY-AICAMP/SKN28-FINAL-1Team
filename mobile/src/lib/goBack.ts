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
 * ⚠️ 웹은 router.replace 가 아니라 **router.navigate** 를 쓴다. replace 로 하면 특정 탭
 * (확인된 예: '/(tabs)/closet')로의 이동이 조용히 무시돼(no-op) 뒤로가기가 먹통이 된다
 * — home/my/lookbook 는 되는데 closet 만 안 되는 재현을 CDP 클릭으로 확인. navigate 는
 * 탭 트리거 방식과 동일하게 동작해 모든 탭 목적지로 확정 이동한다. replace 로 되돌리지 말 것.
 *
 * 네이티브에서는 정상적인 스택이라 이력이 있으면 뒤로, 없으면 fallback 으로 보낸다.
 */
export function goBack(fallback: Href = '/(tabs)/home') {
  if (Platform.OS === 'web') {
    router.navigate(fallback);
    return;
  }
  if (router.canGoBack()) router.back();
  else router.replace(fallback);
}
