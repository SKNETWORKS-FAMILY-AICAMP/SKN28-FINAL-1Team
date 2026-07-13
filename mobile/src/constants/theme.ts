/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#000000',
    background: '#ffffff',
    backgroundElement: '#F0F0F3',
    backgroundSelected: '#E0E1E6',
    textSecondary: '#60646C',
  },
  dark: {
    text: '#ffffff',
    background: '#000000',
    backgroundElement: '#212225',
    backgroundSelected: '#2E3135',
    textSecondary: '#B0B4BA',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

/**
 * 에디토리얼 '본(bone)' 팔레트 — 실제 화면들이 각자 로컬로 복붙해 쓰던 값들을 한 곳으로 통합.
 * 새 화면·공용 컴포넌트는 이걸 import 해서 쓰고, 기존 화면은 손볼 때 점진적으로 이걸로 교체.
 * 앱은 현재 라이트 고정(다크모드는 팀 결정 대기)이라 단일 팔레트.
 */
export const Editorial = {
  ink: '#1c1917', // 웜 블랙 — 본문/버튼/활성 상태
  bone: '#ecebe7', // 이미지 placeholder 배경
  white: '#ffffff',
  surface: '#f3f2ef', // 검색바·태그 배경
  surfaceSoft: '#f7f6f3', // 패널·타일 배경
  surfaceTag: '#f0efe9', // '내 옷' 태그 등
  accent: '#f3e4de', // 웜 피치 — 'new'/경고 배경 강조
  wine: '#5E2B2F', // 경고 텍스트/아이콘
  danger: '#E23B2E', // 폼 에러
  kakao: '#FEE500',
} as const;

/** ink 위 불투명도 램프: 보조 텍스트·보더·백드롭에 사용 (rgba(28,25,23,a)) */
export const ink = (a: number) => `rgba(28,25,23,${a})`;

/**
 * 타이포 스케일 — "글자가 너무 작다"는 피드백 반영해 바닥을 12로 올림.
 * (기존 화면들은 10~13px 하드코딩이 많았음.) 공용 컴포넌트는 이 스케일을 따름.
 */
export const Type = {
  micro: 12, // 배지·아주 작은 라벨 (기존 10~11)
  caption: 13, // 캡션·보조 (기존 11~12)
  footnote: 14, // 리스트 보조 텍스트 (기존 12.5~13)
  body: 15, // 본문 기본
  label: 16, // 버튼·강조 본문
  lead: 18, // 소제목
} as const;

/** 숫자가 본문과 어울리도록 — 폭 고정(tabular)해 들쭉날쭉함 제거. 숫자 표시 Text에 style로 spread. */
export const numeric = { fontVariant: ['tabular-nums'] as const };

// web은 유리(글래스) 탭바가 콘텐츠 위에 떠 있으므로 그만큼 하단 여백 확보
export const BottomTabInset = Platform.select({ ios: 50, android: 80, web: 76 }) ?? 0;
export const MaxContentWidth = 800;
