import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ErrorState, LoadingState, SmartImage } from '@/components/ui';
import { BottomTabInset, Fonts , ContentMax} from '@/constants/theme';
import { TODAY_LOOK_IMAGE } from '@/constants/look-images';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useHome, type HomeData, type HomeWeather } from '@/hooks/use-home';
import { useAuth } from '@/state/auth';

// ── 에디토리얼 본 팔레트 (라이트 고정) ──
const INK = '#1c1917';
const CHIP = '#faf6f0';
const ink = (a: number) => `rgba(28,25,23,${a})`;

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

// 백엔드가 별명 없을 때 자동 생성하는 username(예: naver_XXXX)은 인사말로 부적절 → 폴백.
const AUTO_USERNAME = /^(naver|kakao|google)_/;

/** 인사말용 표시 이름: 실제 별명 → 이메일 앞부분 → '회원' 순 폴백 */
function displayName(
  homeNickname: string | undefined,
  userNickname: string | null | undefined,
  email: string | null | undefined,
): string {
  for (const n of [homeNickname, userNickname]) {
    if (n && !AUTO_USERNAME.test(n)) return n;
  }
  if (email) return email.split('@')[0];
  return '회원';
}

// 홈 탭 (Figma B1) — GET /api/v1/home/ 연동
export default function HomeScreen() {
  const { contentStyle } = useBreakpoint();
  const { user } = useAuth();
  const { data, error, loading, reload } = useHome();

  /* 서비스 페르소나 이름으로 부른다. 백엔드 nickname 은 개발용 계정명이라 그대로 쓰지 않는다. */
  const nickname = '코지';

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.content, contentStyle(ContentMax.card)]}>
          {/* 헤더: 인사말 + 캘린더/프로필 (한 줄) */}
          <View style={styles.header}>
            <Text style={styles.greeting} numberOfLines={1}>
              안녕하세요 {nickname}님
            </Text>
            <View style={styles.headerRight}>
              <Pressable hitSlop={10} onPress={() => router.push('/calendar')}>
                <Icon name="calendar" tintColor={INK} size={24} />
              </Pressable>
              <View style={styles.avatar} />
            </View>
          </View>

          {loading ? (
            <LoadingState message="오늘의 추천을 불러오는 중…" />
          ) : error || !data ? (
            <ErrorState onRetry={reload} />
          ) : (
            <HomeBody data={data} />
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

/** 홈 본문 — 오늘의 룩 (데이터 로드 성공 시) */
function HomeBody({ data }: { data: HomeData }) {
  // 백엔드가 사진을 주면 그걸, 없으면 번들 목업을 쓴다(룩상세와 같은 사진).
  const lookImageUri = data.today_look.image ?? null;

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
          <Pressable onPress={() => router.push('/look-detail')}>
            <SmartImage
              uri={lookImageUri}
              asset={lookImageUri ? undefined : TODAY_LOOK_IMAGE}
              width="100%"
              aspectRatio={LOOK_IMAGE_RATIO}
              radius={0}
              contentFit="cover"
            />
          </Pressable>
          <View style={styles.lookBody}>
            <Text style={styles.lookText} numberOfLines={2}>
              {data.today_look.comment}
            </Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.tagRow}>
              {data.today_look.tags.map((t) => (
                <View key={t} style={styles.tag}>
                  <Text style={styles.tagText}>{t}</Text>
                </View>
              ))}
            </ScrollView>
            <View style={styles.lookButtons}>
              <Pressable
                style={styles.saveBtn}
                onPress={() => router.push('/look-detail')}>
                <Text style={styles.saveBtnText}>저장</Text>
              </Pressable>
              <Pressable style={styles.altBtn}>
                <Text style={styles.altBtnText}>다른 룩</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: BottomTabInset + 24,
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
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: CHIP },

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
    color: ink(0.45),
    textAlign: 'right',
  },

  // 오늘의 룩 카드
  lookCard: {
    flexShrink: 0,
    alignSelf: 'stretch',
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 28,
    overflow: 'hidden',
  },
  lookBody: { flexShrink: 0, padding: 24, gap: 16 },
  lookText: { fontSize: 17, fontWeight: '500', color: ink(0.9) },
  tagRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  tag: {
    backgroundColor: CHIP,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  tagText: { fontSize: 12, fontWeight: '500', color: ink(0.6) },
  lookButtons: { flexDirection: 'row', gap: 10, marginTop: 4 },
  saveBtn: {
    flex: 1,
    height: 44,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnText: { color: '#ffffff', fontSize: 14, fontWeight: '500' },
  altBtn: {
    flex: 1,
    height: 44,
    borderRadius: 999,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  altBtnText: { color: ink(0.7), fontSize: 14, fontWeight: '500' },
});
