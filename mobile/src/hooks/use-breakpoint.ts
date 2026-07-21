import { useWindowDimensions } from 'react-native';

import { Breakpoints, PhoneFrameWidth } from '@/constants/theme';

export type Layout = 'mobile' | 'tablet' | 'desktop';

/**
 * 반응형 레이아웃 판단의 단일 출처. 화면 폭이 필요한 곳은 모두 이 훅을 쓴다.
 *
 * - 기기 종류가 아니라 **창 폭**으로 판단한다. 데스크톱에서 창을 좁히면 모바일 레이아웃이 되어야 하고,
 *   태블릿처럼 경계가 모호한 기기도 폭으로 보면 일관되게 처리된다.
 * - 모듈 최상단에서 Dimensions.get() 을 부르면 화면이 리사이즈돼도 값이 갱신되지 않는다.
 *   반드시 컴포넌트 안에서 이 훅으로 읽을 것.
 *
 * frameWidth 는 모바일 레이아웃에서 콘텐츠에 실제로 주어지는 폭이다(폰 프레임 상한 적용).
 * 데스크톱에서는 화면을 꽉 채우므로 각 화면이 자체 최대 폭을 정한다.
 */
export function useBreakpoint() {
  const { width, height } = useWindowDimensions();

  const isDesktop = width >= Breakpoints.desktop;
  const isTablet = !isDesktop && width >= Breakpoints.tablet;

  const layout: Layout = isDesktop ? 'desktop' : isTablet ? 'tablet' : 'mobile';

  return {
    width,
    height,
    layout,
    isMobile: layout === 'mobile',
    isTablet,
    isDesktop,
    /** 폰 프레임 상한을 적용한 콘텐츠 폭 — 기존 화면들이 쓰던 Math.min(width, 440) 과 동일 */
    frameWidth: Math.min(width, PhoneFrameWidth),
  };
}
