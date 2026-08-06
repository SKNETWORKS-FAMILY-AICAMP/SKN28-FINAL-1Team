import { router } from 'expo-router';

import { ScreenStub } from '@/components/screen-stub';
import { LoginGate } from '@/components/ui';
import { useAuth } from '@/state/auth';

/**
 * 착장 분석 기록 — 지난 분석을 서랍처럼 열어보는 화면. (홈 헤더의 보관함 아이콘으로 진입)
 *
 * 아직 자리만 잡아둔 뼈대다. 목록 연동은 feature/front-outfit-history 에서 채운다.
 * 이 파일을 먼저 만들어 두는 이유는, 홈 헤더의 진입점이 없는 라우트를 가리키지 않게 하고
 * 기록 담당이 home.tsx 를 건드리지 않고도 화면만 채울 수 있게 하려는 것이다.
 *
 * 비회원에게는 목록을 주지 않는다 — 백엔드 GET /api/v1/outfits/analyses/ 가 IsAuthenticated 이고
 * 익명 기록(user=NULL)은 조회 대상에서 빠진다. 비회원 분석은 로그인 시점에 claim 으로 계정에
 * 옮겨온 뒤에야 여기에 나타난다.
 */
export default function OutfitHistoryScreen() {
  const { isLoggedIn } = useAuth();

  if (!isLoggedIn) {
    return (
      <LoginGate
        title="분석 기록은 로그인하고 볼 수 있어요"
        body="로그인하면 그동안 분석한 착장을 모아서 다시 볼 수 있어요."
      />
    );
  }

  return (
    <ScreenStub
      eyebrow="MY ANALYSIS"
      title="분석 기록"
      actions={[{ label: '홈으로', onPress: () => router.replace('/(tabs)/home'), primary: false }]}
    />
  );
}
