import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BottomTabInset, Fonts } from '@/constants/theme';

// ── 에디토리얼 본 팔레트 (라이트 고정) ──
const INK = '#1c1917';
const BONE = '#ecebe7';
const CHIP = '#f3f2ef';
const SOFT = '#f7f6f3';
const ink = (a: number) => `rgba(28,25,23,${a})`;

// 홈 탭 (Figma B1)
export default function HomeScreen() {
  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}>
          {/* 헤더: 인사말 + 캘린더/프로필 */}
          <View style={styles.header}>
            <View>
              <Text style={styles.greeting}>안녕하세요 코지님</Text>
              <Text style={styles.date}>7월 7일 월요일</Text>
            </View>
            <View style={styles.headerRight}>
              <Pressable hitSlop={10} onPress={() => router.push('/calendar')}>
                <Icon name="calendar" tintColor={INK} size={24} />
              </Pressable>
              <View style={styles.avatar} />
            </View>
          </View>

          {/* 오늘의 룩 */}
          <View style={styles.block}>
            <View style={styles.rowBetween}>
              <Text style={styles.sectionTitle}>오늘의 룩</Text>
              <Text style={styles.weather}>서울 24° · 맑음</Text>
            </View>
            <View style={styles.lookCard}>
              <Pressable
                style={styles.lookImage}
                onPress={() => router.push('/look-detail')}
              />
              <View style={styles.lookBody}>
                <Text style={styles.lookText}>
                  8도예요. 포근한 니트 코디 골라봤어요.
                </Text>
                <View style={styles.tagRow}>
                  {['니트', '코트', '로퍼'].map((t) => (
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
              {['출근룩', '데이트룩', '면접룩', '주말룩'].map((c) => (
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
              <Text style={styles.statNum}>42</Text>
              <Text style={styles.statLabel}>내 옷장</Text>
            </View>
            <View style={styles.statTile}>
              <Text style={styles.statNum}>8</Text>
              <Text style={styles.statLabel}>저장한 룩</Text>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
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
  },
  greeting: { fontFamily: Fonts.serif, fontSize: 24, fontWeight: '500', color: INK },
  date: { fontSize: 12, color: ink(0.45), marginTop: 3 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: CHIP },

  block: { gap: 12 },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionTitle: { fontSize: 13, fontWeight: '500', color: INK },
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
