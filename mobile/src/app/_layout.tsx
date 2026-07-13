import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { DevReset } from '@/components/dev-reset';
import { ConfirmProvider, ToastProvider } from '@/components/ui';
import { authStore } from '@/state/auth';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const colorScheme = useColorScheme();

  // 앱 시작 시 저장된 토큰으로 세션 복원 (없으면 게스트)
  useEffect(() => {
    authStore.bootstrap();
  }, []);
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      {/* 전역 피드백 레이어: 어디서든 useToast()/useConfirm() 호출 가능 */}
      <ConfirmProvider>
        <ToastProvider>
          <AnimatedSplashOverlay />
          {/* 헤더는 전 화면 숨김. 진입 흐름(스플래시/온보딩/인증)은 파일명 그대로 자동 등록됨 */}
          <Stack screenOptions={{ headerShown: false }}>
            {/* 메인 앱 = 하단 5탭 */}
            <Stack.Screen name="(tabs)" />
            {/* 위에서 올라오는 모달 화면들 */}
            <Stack.Screen name="item-add" options={{ presentation: 'modal' }} />
            <Stack.Screen name="import" options={{ presentation: 'modal' }} />
          </Stack>
          {/* 개발 전용: 어디서든 스플래시로 돌아가는 단축 버튼 (배포 빌드엔 안 뜸) */}
          <DevReset />
        </ToastProvider>
      </ConfirmProvider>
    </ThemeProvider>
  );
}
