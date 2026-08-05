import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { TabBarHeight } from '@/constants/theme';

/**
 * 하단 탭바가 실제로 가리는 높이.
 *
 * 탭바는 `position:absolute` 로 콘텐츠 위에 떠 있어서, 스크롤 내용 아래에 이만큼
 * 여백을 줘야 마지막 줄이 가리지 않는다. 바의 내용 높이(TabBarHeight)에 기기의
 * 하단 안전영역을 더한다 — 아이폰 홈 인디케이터(34)나 안드로이드 제스처 바가
 * 기기마다 달라 상수로는 맞출 수 없기 때문이다.
 *
 * 바 자체도 `paddingBottom: Math.max(insets.bottom, 8)` 로 그리므로 계산식이 같다.
 */
export function useBottomTabInset(): number {
  const insets = useSafeAreaInsets();
  return TabBarHeight + Math.max(insets.bottom, 8);
}
