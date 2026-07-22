import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const BONE = '#eae0d3';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];
const FIRST_WEEKDAY = 3; // 2026년 7월 1일 = 수요일
const DAYS_IN_MONTH = 31;

// 착장 기록이 있는 날 (day → 룩)
const RECORDS: Record<number, { title: string; tags: string[]; tone: number }> = {
  3: { title: '레이어드 트렌치', tags: ['#가을', '#클래식'], tone: 0.12 },
  5: { title: '주말 브런치 룩', tags: ['#데이트'], tone: 0.06 },
  7: { title: '포근한 니트 오피스룩', tags: ['#출근', '#미니멀'], tone: 0.1 },
  8: { title: '미니멀 오피스', tags: ['#출근'], tone: 0.18 },
  12: { title: '데님 캐주얼', tags: ['#주말'], tone: 0.22 },
  15: { title: '봄 산책 코디', tags: ['#러블리'], tone: 0.08 },
  20: { title: '겨울 울 코트', tags: ['#포멀'], tone: 0.28 },
};

// B2 착장 캘린더 — 월 그리드 + 선택일 상세
export default function Calendar() {
  const { contentStyle } = useBreakpoint();
  const [selected, setSelected] = useState(7);
  const cells: (number | null)[] = [
    ...Array(FIRST_WEEKDAY).fill(null),
    ...Array.from({ length: DAYS_IN_MONTH }, (_, i) => i + 1),
  ];
  const rec = RECORDS[selected];

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.default)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/home')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>착장 캘린더</Text>
          <View style={{ width: 20 }} />
        </View>
      </SafeAreaView>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[styles.content, contentStyle(ContentMax.default)]}>
        {/* 월 네비 */}
        <View style={styles.monthRow}>
          <Pressable hitSlop={10}>
            <Icon name="chevron.left" tintColor={ink(0.4)} size={16} />
          </Pressable>
          <Text style={styles.monthText}>2026년 7월</Text>
          <Pressable hitSlop={10}>
            <Icon name="chevron.right" tintColor={ink(0.4)} size={16} />
          </Pressable>
        </View>

        {/* 요일 헤더 */}
        <View style={styles.weekHeader}>
          {WEEKDAYS.map((d, i) => (
            <Text
              key={d}
              style={[
                styles.weekday,
                i === 0 && { color: '#c0392b' },
                i === 6 && { color: ink(0.55) },
              ]}>
              {d}
            </Text>
          ))}
        </View>

        {/* 날짜 그리드 */}
        <View style={styles.grid}>
          {cells.map((day, idx) => {
            if (day === null) return <View key={`e${idx}`} style={styles.cell} />;
            const r = RECORDS[day];
            const on = day === selected;
            return (
              <Pressable key={day} style={styles.cell} onPress={() => setSelected(day)}>
                <View style={[styles.dayInner, on && styles.dayInnerOn]}>
                  {r ? (
                    <View
                      style={[styles.dayThumb, { backgroundColor: `rgba(28,25,23,${r.tone})` }]}
                    />
                  ) : null}
                  <Text
                    style={[
                      styles.dayNum,
                      r && styles.dayNumRec,
                      on && styles.dayNumOn,
                    ]}>
                    {day}
                  </Text>
                </View>
              </Pressable>
            );
          })}
        </View>

        {/* 선택일 상세 */}
        <View style={styles.detail}>
          <Text style={styles.detailDate}>7월 {selected}일</Text>
          {rec ? (
            <Pressable style={styles.recCard} onPress={() => router.push('/saved-look')}>
              <View style={[styles.recThumb, { backgroundColor: `rgba(28,25,23,${rec.tone})` }]} />
              <View style={styles.recBody}>
                <Text style={styles.recTitle}>{rec.title}</Text>
                <View style={styles.recTags}>
                  {rec.tags.map((t) => (
                    <Text key={t} style={styles.recTag}>{t}</Text>
                  ))}
                </View>
              </View>
              <Icon name="chevron.right" tintColor={ink(0.25)} size={15} />
            </Pressable>
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>이 날은 기록된 착장이 없어요</Text>
              <Pressable style={styles.addBtn} onPress={() => router.push('/chat-mode')}>
                <Text style={styles.addText}>코디 추천받기</Text>
              </Pressable>
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  headerSafe: { backgroundColor: '#ffffff' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 8,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },

  content: { paddingHorizontal: 16, paddingBottom: 32 },
  monthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 20,
    paddingVertical: 16,
  },
  monthText: { fontFamily: Fonts.serif, fontSize: 19, color: INK },

  weekHeader: { flexDirection: 'row', paddingBottom: 6 },
  weekday: { flex: 1, textAlign: 'center', fontSize: 11.5, color: ink(0.4), fontWeight: '500' },

  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: { width: `${100 / 7}%`, aspectRatio: 0.82, alignItems: 'center', justifyContent: 'center' },
  dayInner: {
    width: '86%',
    height: '90%',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  dayInnerOn: { borderWidth: 1.5, borderColor: INK },
  dayThumb: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: 11 },
  dayNum: { fontSize: 13, color: ink(0.6) },
  dayNumRec: { color: ink(0.9), fontWeight: '600' },
  dayNumOn: { fontWeight: '700', color: INK },

  detail: { marginTop: 22 },
  detailDate: { fontSize: 13, fontWeight: '600', color: INK, marginBottom: 12, marginLeft: 4 },
  recCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 16,
    padding: 12,
  },
  recThumb: { width: 60, height: 72, borderRadius: 12, backgroundColor: BONE },
  recBody: { flex: 1, gap: 6 },
  recTitle: { fontSize: 14.5, fontWeight: '500', color: ink(0.9) },
  recTags: { flexDirection: 'row', gap: 8 },
  recTag: { fontSize: 11.5, color: ink(0.4) },

  empty: {
    alignItems: 'center',
    gap: 14,
    borderWidth: 1,
    borderColor: ink(0.1),
    borderStyle: 'dashed',
    borderRadius: 16,
    paddingVertical: 30,
  },
  emptyText: { fontSize: 13, color: ink(0.4) },
  addBtn: {
    paddingHorizontal: 18,
    height: 40,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addText: { fontSize: 13, color: '#fff', fontWeight: '500' },
});
