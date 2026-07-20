import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ErrorState, LoadingState } from '@/components/ui';
import { BottomTabInset, Fonts } from '@/constants/theme';
import { useHome, type HomeData, type HomeWeather } from '@/hooks/use-home';
import { useAuth } from '@/state/auth';

// ── 에디토리얼 본 팔레트 (라이트 고정) ──
const INK = '#1c1917';
const BONE = '#ecebe7';
const CHIP = '#f3f2ef';
const SOFT = '#f7f6f3';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

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
  const { user } = useAuth();
  const { data, error, loading, reload } = useHome();

  const nickname = displayName(data?.nickname, user?.nickname, user?.email);

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}>
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

/** 홈 본문 — 오늘의 룩 / 빠른 추천 / 스탯 (데이터 로드 성공 시) */
function HomeBody({ data }: { data: HomeData }) {
  return (
    <>
      {/* 오늘의 룩 */}
      <View style={styles.block}>
        <View style={styles.rowBetween}>
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitle}>오늘의 룩</Text>
            <Text style={styles.date}>{todayLabel()}</Text>
          </View>
          <Text style={styles.weather}>{weatherLabel(data.weather)}</Text>
        </View>
        <View style={styles.lookCard}>
          <Pressable
            style={styles.lookImage}
            onPress={() => router.push('/look-detail')}
          />
          <View style={styles.lookBody}>
            <Text style={styles.lookText}>{data.today_look.comment}</Text>
            <View style={styles.tagRow}>
              {data.today_look.tags.map((t) => (
                <View key={t} style={styles.tag}>
                  <Text style={styles.tagText}>{t}</Text>
                </View>
              ))}
            </View>
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

      {/* 빠른 추천 */}
      <View style={styles.block}>
        <Text style={styles.sectionTitle}>빠른 추천</Text>
        <View style={styles.chipRow}>
          {data.quick_recommends.map((c) => (
            <Pressable key={c} onPress={() => router.push('/chat-room')}>
              <View style={styles.chip}>
                <Text style={styles.chipText}>{c}</Text>
              </View>
            </Pressable>
          ))}
        </View>
      </View>

      {/* 스탯 */}
      <View style={styles.statsRow}>
        <View style={styles.statTile}>
          <Text style={styles.statNum}>{data.closet_count}</Text>
          <Text style={styles.statLabel}>내 옷장</Text>
        </View>
        <View style={styles.statTile}>
          <Text style={styles.statNum}>{data.saved_look_count}</Text>
          <Text style={styles.statLabel}>저장한 룩</Text>
        </View>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: BottomTabInset + 24,
    gap: 24,
  },

  // 헤더
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  greeting: { flex: 1, fontFamily: Fonts.serif, fontSize: 24, fontWeight: '500', color: INK },
  date: { fontSize: 12, color: ink(0.45), marginTop: 2 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 14, flexShrink: 0 },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: CHIP },

  block: { gap: 12 },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionTitle: { fontSize: 13, fontWeight: '500', color: INK },
  sectionHead: { gap: 2 },
  weather: { fontSize: 12, color: ink(0.45) },

  // 오늘의 룩 카드
  lookCard: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 20,
    overflow: 'hidden',
  },
  lookImage: { height: 230, backgroundColor: BONE },
  lookBody: { padding: 16, gap: 12 },
  lookText: { fontSize: 13, fontWeight: '500', color: ink(0.9) },
  tagRow: { flexDirection: 'row', gap: 6 },
  tag: {
    backgroundColor: CHIP,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  tagText: { fontSize: 10.5, fontWeight: '500', color: ink(0.6) },
  lookButtons: { flexDirection: 'row', gap: 8, marginTop: 4 },
  saveBtn: {
    flex: 1,
    height: 40,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnText: { color: '#ffffff', fontSize: 13, fontWeight: '500' },
  altBtn: {
    flex: 1,
    height: 40,
    borderRadius: 999,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  altBtnText: { color: ink(0.7), fontSize: 13, fontWeight: '500' },

  // 빠른 추천
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: ink(0.14),
    borderRadius: 999,
    paddingHorizontal: 15,
    paddingVertical: 8,
  },
  chipText: { fontSize: 12, fontWeight: '500', color: ink(0.6) },

  // 스탯
  statsRow: { flexDirection: 'row', gap: 10 },
  statTile: {
    flex: 1,
    backgroundColor: SOFT,
    borderWidth: 1,
    borderColor: ink(0.06),
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 4,
  },
  statNum: { fontFamily: Fonts.serif, fontSize: 22, fontWeight: '600', color: INK },
  statLabel: { fontSize: 11, color: ink(0.45) },
});
