import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { HomeStatusSlot } from '@/components/home/home-status-slot';
import { Avatar, ErrorState, LoadingState, SmartImage, useToast } from '@/components/ui';
import { DEMO_HOME } from '@/constants/demo';
import { Editorial, ink, Fonts , ContentMax} from '@/constants/theme';
import { PROFILE_IMAGE, TODAY_LOOK_IMAGE } from '@/constants/look-images';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useHome, type HomeData, type HomeWeather } from '@/hooks/use-home';
import { useRefresh } from '@/hooks/use-refresh';
import { useWardrobeItems } from '@/hooks/use-wardrobe';
import { useAuth } from '@/state/auth';
import { savedLookStore } from '@/state/saved';

// ── 에디토리얼 본 팔레트 (라이트 고정) ──
const INK = Editorial.ink;
const CHIP = Editorial.surface;

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

/** 홈 오늘의 룩 placeholder — URL만 바꿔서 미리보기 */
/* 오늘의 룩 사진 비율(가로:세로). 고정 높이로 두면 카드가 넓어지는 데스크톱에서
   가로로 납작한 틀이 되어 세로 사진이 가운데만 잘린다. */
const LOOK_IMAGE_RATIO = 1 / 1.05;

/** "7월 15일 화요일" — 오늘 날짜 (기기 로컬 기준) */
function todayLabel(): string {
  const d = new Date();
  return `${d.getMonth() + 1}월 ${d.getDate()}일 ${WEEKDAYS[d.getDay()]}요일`;
}

/** "서울 24° · 맑음" — 값이 없으면 우아하게 생략 */
function weatherLabel(w: HomeWeather): string {
  const region = w.region ?? '서울';
  const temp = w.temperature != null ? `${w.temperature}°` : '—';
  return w.sky_state ? `${region} ${temp} · ${w.sky_state}` : `${region} ${temp}`;
}

// 홈 탭 (Figma B1) — GET /api/v1/home/ 연동
export default function HomeScreen() {
  const { contentStyle } = useBreakpoint();
  const tabInset = useBottomTabInset();
  const { status, isDemo } = useAuth();
  /* 비회원은 부를 것이 없어(토큰도, 옷장도 없다) 온보딩 전용 홈을 즉시 보여준다.
     데모 세션도 부른다 — 토큰이 없을 뿐 요청은 통과한다(dev 서버가 무토큰 요청을 허용).
     그래야 발표에서 진짜 날씨가 뜬다. 예전엔 여기서 막아 두어 고정 목업만 보였다. */
  const { data: apiData, error, loading, reload } = useHome(undefined, status === 'authed');
  const { refreshing, onRefresh } = useRefresh(reload);
  /* 실패하면 데모 세션만 목업으로 물러난다 — 인증이 켜지면 401 이 나는데,
     체험용 링크에서 홈이 통째로 에러 화면이 되는 것보다 낫다. */
  const data = apiData ?? (isDemo ? DEMO_HOME : null);

  /* 옷장이 비었는지는 **실제 옷장**에 물어본다.
     홈 API 의 closet_count 는 백엔드가 아직 고정값(MOCK_CLOSET_COUNT)을 주기 때문에,
     그대로 믿으면 옷장이 텅 비어도 "42벌 있다"고 보고 추천 카드를 띄운다.
     옷장·채팅 모드 선택과 같은 출처(필터 없음)를 써서 세 화면이 늘 같은 수를 본다. */
  const { items: closetItems, loading: closetLoading } = useWardrobeItems({}, status === 'authed');

  /* 서비스 페르소나 이름으로 부른다. 백엔드 nickname 은 개발용 계정명이라 그대로 쓰지 않는다. */
  const nickname = '코지';

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          /* 비회원·데모는 불러올 것이 없어 당겨도 반응하지 않는다. */
          refreshControl={
            status === 'authed' ? (
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={INK} />
            ) : undefined
          }
          contentContainerStyle={[styles.content, { paddingBottom: tabInset + 24 }, contentStyle(ContentMax.card)]}>
          {/* 헤더: 인사말 + 기록/캘린더/프로필 (한 줄) */}
          <View style={styles.header}>
            <Text style={styles.greeting} numberOfLines={1}>
              안녕하세요 {nickname}님
            </Text>
            <View style={styles.headerRight}>
              {/* 분석 기록은 늘 열 수 있어야 하는 진입점이라 본문이 아니라 헤더에 둔다.
                  본문에 두면 상시로 세로 공간을 먹어 오늘의 룩 카드가 밀린다. */}
              <Pressable hitSlop={10} onPress={() => router.push('/outfit-history')}>
                <Icon name="archivebox" tintColor={INK} size={24} />
              </Pressable>
              <Pressable hitSlop={10} onPress={() => router.push('/calendar')}>
                <Icon name="calendar" tintColor={INK} size={24} />
              </Pressable>
              {/* 옆의 캘린더 아이콘은 눌리는데 아바타만 안 눌리면 어긋난다 → 마이로 보낸다 */}
              <Pressable hitSlop={10} onPress={() => router.push('/my')}>
                <Avatar name={nickname} asset={PROFILE_IMAGE} size={40} />
              </Pressable>
            </View>
          </View>

          {/* 상태 카드는 홈이 어느 분기를 그리든 보여야 한다 — 분기 안에 넣으면
              옷장에 옷이 있는 회원은 진행 중인 분석을 볼 데가 없어진다. */}
          <HomeStatusSlot />

          {status === 'loading' ? (
            <LoadingState message="홈을 준비하는 중…" />
          ) : status === 'guest' ? (
            <EmptyClosetStart />
          ) : loading || closetLoading ? (
            <LoadingState message="오늘의 추천을 불러오는 중…" />
          ) : error || !data ? (
            <ErrorState onRetry={reload} />
          ) : closetItems.length === 0 ? (
            <EmptyClosetStart />
          ) : (
            <HomeBody data={data} />
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

/** 옷장 데이터가 없는 첫 방문자를 위한 홈. 분석 경험부터 제공해 추천의 근거를 만든다. */
function EmptyClosetStart() {
  return (
    <View style={styles.emptyStart}>
      <View style={styles.emptyEyebrow}>
        <Text style={styles.emptyEyebrowText}>MY FIRST LOOK</Text>
      </View>
      <Text style={styles.emptyTitle}>옷장이 비어 있어도 괜찮아요</Text>
      <Text style={styles.emptyBody}>사진 한 장으로 내 스타일을 시작해 볼까요?</Text>
      <View style={styles.emptyActions}>
        <Pressable style={styles.emptyPrimary} onPress={() => router.push('/outfit-review')}>
          <Text style={styles.emptyPrimaryText} numberOfLines={1}>
            내 착장 분석하기
          </Text>
        </Pressable>
        <Pressable style={styles.emptySecondary} onPress={() => router.push('/(tabs)/lookbook')}>
          <Text style={styles.emptySecondaryText} numberOfLines={1}>
            스타일 둘러보기
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

type DisplayLook = {
  image?: string | null;
  asset?: number;
  comment: string;
  tags: string[];
  /** 눌렀을 때 열 룩 상세 (constants/today-look.ts LOOK_VARIANTS) */
  variantId: string;
};

/** '다른 룩' 순환용 대안 추천 — 오늘의 룩(API) 다음으로 돌아가며 보여준다(룩북 피드와 같은 사진 재사용). */
const ALT_LOOKS: DisplayLook[] = [
  {
    image: 'https://i.pinimg.com/736x/55/26/0d/55260de328aec1e50740655fd4b5fdc5.jpg',
    comment: '데이트에 어울리게 색을 절제한 부드러운 캐주얼로 골라봤어요.',
    tags: ['#데이트', '#캐주얼'],
    variantId: 'date',
  },
  {
    image: 'https://i.pinimg.com/736x/b4/cd/22/b4cd22015add333e10cd2ba06067406b.jpg',
    comment: '나들이용으로 편하면서도 산뜻한 조합이에요.',
    tags: ['#나들이', '#미니멀'],
    variantId: 'outdoor',
  },
  {
    image: 'https://i.pinimg.com/736x/ec/96/f3/ec96f39eb800d19290736c17f0253ed9.jpg',
    comment: '일교차가 큰 날 가볍게 걸치기 좋은 레이어드 룩이에요.',
    tags: ['#여행', '#캐주얼'],
    variantId: 'outdoor',
  },
];

/** 홈 본문 — 오늘의 룩 (데이터 로드 성공 시) */
function HomeBody({ data }: { data: HomeData }) {
  const toast = useToast();
  const [idx, setIdx] = useState(0);

  // 오늘의 룩(API)을 맨 앞에 두고 대안 룩을 이어 붙여 '다른 룩'으로 순환한다.
  // 백엔드가 사진을 주면 그걸, 없으면 번들 목업(룩상세와 같은 사진)을 쓴다.
  const looks = useMemo<DisplayLook[]>(
    () => [
      {
        image: data.today_look.image ?? null,
        asset: data.today_look.image ? undefined : TODAY_LOOK_IMAGE,
        comment: data.today_look.comment,
        tags: data.today_look.tags,
        variantId: 'daily',
      },
      ...ALT_LOOKS,
    ],
    [data],
  );
  const look = looks[idx % looks.length];

  // 지금 보고 있는 룩을 '저장됨'에 담고 룩북 저장됨 탭으로 이동한다.
  const saveCurrentLook = () => {
    savedLookStore.addLook({
      image: look.image ?? undefined,
      asset: look.image ? undefined : look.asset,
      comment: look.comment,
      tags: look.tags,
    });
    toast('저장됨에 담았어요');
    router.push('/(tabs)/lookbook?tab=saved');
  };

  return (
    <View style={styles.lookSection}>
      <View style={styles.lookCard}>
          <View style={styles.lookMetaRow}>
            <Text style={styles.sectionTitle} numberOfLines={1}>
              오늘의 룩
            </Text>
            <Text style={styles.metaText} numberOfLines={1}>
              {todayLabel()} | {weatherLabel(data.weather)}
            </Text>
          </View>
          <Pressable onPress={() => router.push(`/look-detail?id=${look.variantId}`)}>
            <SmartImage
              uri={look.image}
              asset={look.image ? undefined : look.asset}
              width="100%"
              aspectRatio={LOOK_IMAGE_RATIO}
              radius={0}
              contentFit="cover"
            />
          </Pressable>
          <View style={styles.lookBody}>
            <Text style={styles.lookText} numberOfLines={2}>
              {look.comment}
            </Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.tagRow}>
              {look.tags.map((t) => (
                <View key={t} style={styles.tag}>
                  <Text style={styles.tagText}>{t}</Text>
                </View>
              ))}
            </ScrollView>
            <View style={styles.lookButtons}>
              <Pressable style={styles.saveBtn} onPress={saveCurrentLook}>
                <Text style={styles.saveBtnText}>저장</Text>
              </Pressable>
              <Pressable style={styles.altBtn} onPress={() => setIdx((i) => i + 1)}>
                <Text style={styles.altBtnText}>다른 룩</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },
  content: {
    paddingHorizontal: 20,
    paddingTop: 16,
    gap: 24,
  },
  lookSection: { gap: 14 },

  // 헤더
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  greeting: { flex: 1, fontFamily: Fonts.serif, fontSize: 18, fontWeight: '500', color: INK },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 14, flexShrink: 0 },

  emptyStart: {
    borderRadius: 28,
    backgroundColor: CHIP,
    borderWidth: 1, borderColor: Editorial.line,
    paddingHorizontal: 28,
    paddingVertical: 34,
    alignItems: 'flex-start',
  },
  emptyEyebrow: { paddingBottom: 16 },
  emptyEyebrowText: { fontSize: 10, letterSpacing: 1.7, fontWeight: '600', color: Editorial.textCaption },
  emptyTitle: { fontFamily: Fonts.serif, fontSize: 28, lineHeight: 36, color: INK },
  emptyBody: { marginTop: 14, fontSize: 16, lineHeight: 24, color: Editorial.textCaption },
  // 두 버튼을 한 줄에 나란히. flex:1 로 폭을 반씩 나눠 가진다.
  emptyActions: { marginTop: 28, alignSelf: 'stretch', flexDirection: 'row', gap: 10 },
  emptyPrimary: {
    flex: 1,
    height: 50,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Editorial.cta,
  },
  emptyPrimaryText: { color: '#ffffff', fontSize: 14, fontWeight: '600' },
  emptySecondary: {
    flex: 1,
    height: 50,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  emptySecondaryText: { fontSize: 14, fontWeight: '600', color: Editorial.textSoft },

  lookMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
    paddingHorizontal: 24,
    paddingTop: 14,
    paddingBottom: 10,
  },
  sectionTitle: { flexShrink: 0, fontSize: 15, fontWeight: '500', color: INK },
  metaText: {
    flexShrink: 1,
    fontSize: 13,
    color: Editorial.textCaption,
    textAlign: 'right',
  },

  // 오늘의 룩 카드
  lookCard: {
    flexShrink: 0,
    alignSelf: 'stretch',
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 28,
    overflow: 'hidden',
  },
  lookBody: { flexShrink: 0, padding: 24, gap: 16 },
  lookText: { fontSize: 17, fontWeight: '500', color: Editorial.ink },
  tagRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  tag: {
    backgroundColor: Editorial.control,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  tagText: { fontSize: 12, fontWeight: '500', color: Editorial.textCaption },
  lookButtons: { flexDirection: 'row', gap: 10, marginTop: 4 },
  saveBtn: {
    flex: 1,
    height: 44,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnText: { color: '#ffffff', fontSize: 14, fontWeight: '500' },
  altBtn: {
    flex: 1,
    height: 44,
    borderRadius: 999,
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  altBtnText: { color: Editorial.textSoft, fontSize: 14, fontWeight: '500' },
});
