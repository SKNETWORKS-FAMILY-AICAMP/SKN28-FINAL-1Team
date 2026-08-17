import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { DevReset } from '@/components/dev-reset';
import { ConfirmProvider, ToastProvider } from '@/components/ui';
import { useKakaoInviteLink } from '@/hooks/use-kakao-link';
import { clearLegacyPendingShare } from '@/lib/secureStore';
import { initSocialSDKs } from '@/lib/socialLogin';
import { authStore } from '@/state/auth';
import { outfitAnalysisStore } from '@/state/outfit-analysis';
import { outfitClaimStore } from '@/state/outfit-claim';
import { prefsStore } from '@/state/prefs';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const colorScheme = useColorScheme();

  /* 카카오 초대 카드로 앱이 열리면 초대장 화면으로 보낸다. 최상위에 둬야
     앱이 꺼져 있다 켜진 경우(getInitialURL)도 놓치지 않는다. */
  useKakaoInviteLink();

  // 앱 시작 시: 소셜 SDK 초기화(카카오/네이버/구글) + 저장된 토큰으로 세션 복원
  useEffect(() => {
    initSocialSDKs();
    /* 예산은 세션이 정해진 뒤에 받아 온다 — 룩 상세·찜 목록이 '예산 내' 배지에 쓰는 값이라
       그 화면에 들어가기 전에 채워져 있어야 한다. */
    void authStore.bootstrap().then(() => prefsStore.loadBudget());
    outfitAnalysisStore.bootstrap();
    /* 두 스토어를 구독하므로 뒤에 둔다 — 비로그인 분석의 claim 토큰을 모았다가 로그인 때 넘긴다. */
    outfitClaimStore.bootstrap();
    /* 공유 예약이 서버로 옮겨가기 전(secureStore) 남은 값을 치운다. 아무도 읽지 않지만
       남겨 두면 나중에 "예약이 어디 있지"를 두 군데서 찾게 된다. */
    void clearLegacyPendingShare();
  }, []);
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      {/* 전역 피드백 레이어: 어디서든 useToast()/useConfirm() 호출 가능 */}
      <ConfirmProvider>
        <ToastProvider>
          <AnimatedSplashOverlay />
          {/* 헤더는 전 화면 숨김. 진입 흐름(스플래시/온보딩/인증)은 파일명 그대로 자동 등록됨 */}
          <Stack screenOptions={{ headerShown: false }}>
            {/* 메인 앱 = 홈 · 옷장 · 질문(+) · 룩북 · 마이 */}
            <Stack.Screen name="(tabs)" />
            {/* 위에서 올라오는 모달 화면들 */}
            <Stack.Screen name="look-add" options={{ presentation: 'modal' }} />
            <Stack.Screen name="item-add" options={{ presentation: 'modal' }} />
            <Stack.Screen name="item-add-library" options={{ presentation: 'modal' }} />
            <Stack.Screen name="import" options={{ presentation: 'modal' }} />
            <Stack.Screen name="calendar-entry" options={{ presentation: 'modal' }} />
            <Stack.Screen name="outfit-review" options={{ presentation: 'modal' }} />
            <Stack.Screen name="edit-profile" options={{ presentation: 'modal' }} />
          </Stack>
          {/* 개발 전용: 어디서든 스플래시로 돌아가는 단축 버튼 (배포 빌드엔 안 뜸) */}
          <DevReset />
        </ToastProvider>
      </ConfirmProvider>
    </ThemeProvider>
  );
}
