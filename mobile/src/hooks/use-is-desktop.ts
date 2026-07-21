import { Platform, useWindowDimensions } from 'react-native';

/** 데스크톱(진짜 웹) 레이아웃으로 전환하는 폭 기준. global.css의 프레임 해제 값과 일치시킬 것. */
export const DESKTOP_BREAKPOINT = 1024;

/**
 * 웹 브라우저이면서 화면 폭이 데스크톱 기준 이상일 때만 true.
 * 네이티브(iOS/Android)와 모바일 브라우저는 항상 false → 기존 폰 프레임 UI 유지.
 */
export function useIsDesktop(): boolean {
  const { width } = useWindowDimensions();
  return Platform.OS === 'web' && width >= DESKTOP_BREAKPOINT;
}
