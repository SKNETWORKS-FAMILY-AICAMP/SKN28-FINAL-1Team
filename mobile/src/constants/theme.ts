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
    /** 한국어 제목이 궁서체처럼 보이지 않도록 시스템 산세리프로 통일한다. */
    serif: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'normal',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-display)',
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
  bone: '#eae0d3', // 이미지 placeholder 배경
  white: '#ffffff',
  surface: '#faf6f0', // 검색바·태그 배경 (기존 #faf6f0 는 너무 진해 연하게 조정)
  surfaceSoft: '#fcffff', // 패널·타일 배경
  surfaceTag: '#efe7db', // '내 옷' 태그 등
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

/**
 * 폰 프레임 폭 — 모바일 레이아웃에서 콘텐츠가 넓어지지 않게 잡는 상한.
 * global.css 의 #root max-width 와 반드시 같아야 한다. 여기가 단일 출처다.
 */
export const PhoneFrameWidth = 440;

/**
 * 데스크톱에서 본문이 과하게 늘어나지 않도록 잡는 최대 폭.
 * 한 줄이 너무 길면 읽기 어렵고, 목록은 라벨과 값이 양 끝으로 벌어져 시선이 끊긴다.
 */
export const ContentMax = {
  /** 세로 사진이 주인공인 카드 — 더 넓히면 사진이 지나치게 커지거나 잘린다 */
  card: 560,
  /** 폼·설정 목록 — 한 줄이 길어지면 안 되는 화면 */
  narrow: 720,
  /** 일반 본문 */
  default: 880,
  /** 그리드처럼 넓게 쓰는 화면 */
  wide: 1280,
} as const;

/**
 * 반응형 기준 폭. 창 폭이 이 값 **이상**이면 해당 레이아웃으로 본다.
 * 기기 종류(User-Agent)가 아니라 창 폭으로 판단해야 데스크톱에서 창을 줄였을 때도 맞게 동작한다.
 * 값을 바꾸면 useBreakpoint() 를 쓰는 모든 화면이 함께 따라온다.
 */
export const Breakpoints = {
  /** 2열 그리드가 좁아지기 시작하는 지점 */
  tablet: 768,
  /** 하단 탭바 → 좌측 사이드바로 바뀌는 지점 */
  desktop: 1024,
  /** 우측 채팅 패널까지 함께 띄우는 지점.
      사이드바 232 + 본문 최소 560 + 패널 400 = 1192 가 하한이라 여유를 둔 값이다. */
  wide: 1280,
} as const;

/** 옷장·룩북 2열 그리드 카드 — 이미지 비율·모서리 통일 */
export const GridCard = {
  pad: 20,
  gap: 10,
  maxWidth: PhoneFrameWidth,
  imageRatio: 1,
  radius: 16,
} as const;

export function gridCardWidth(windowWidth: number): number {
  const w = Math.min(windowWidth, GridCard.maxWidth);
  return (w - GridCard.pad * 2 - GridCard.gap) / 2;
}

export function gridCardImageHeight(cardWidth: number): number {
  return cardWidth * GridCard.imageRatio;
}
