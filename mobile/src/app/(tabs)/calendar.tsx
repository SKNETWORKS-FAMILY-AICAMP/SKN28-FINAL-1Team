import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ShareLookSheet } from '@/components/calendar/share-look-sheet';
import { LoginGate, SmartImage } from '@/components/ui';
import { ContentMax, Editorial, Fonts, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useAuth } from '@/state/auth';
import { calendarStore, toDateKey, todayKey, useCalendarEntries } from '@/state/calendar';

const INK = Editorial.ink;

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

const TODAY = todayKey();

// B2 착장 캘린더 — 월 그리드 + 선택일 상세(기록·공유)
export default function Calendar() {
  const { isLoggedIn } = useAuth();
  const { contentStyle } = useBreakpoint();
  const entries = useCalendarEntries();

  const now = useMemo(() => new Date(), []);
  const [view, setView] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const [selectedDay, setSelectedDay] = useState(now.getDate());
  const [shareOpen, setShareOpen] = useState(false);

  const { cells, selectedKey } = useMemo(() => {
    const first = new Date(view.year, view.month - 1, 1).getDay();
    const days = new Date(view.year, view.month, 0).getDate();
    return {
      cells: [
        ...Array<number | null>(first).fill(null),
        ...Array.from({ length: days }, (_, i) => i + 1),
      ],
      selectedKey: toDateKey(view.year, view.month, selectedDay),
    };
  }, [view, selectedDay]);

  const entry = entries[selectedKey];

  const moveMonth = (delta: number) => {
    const d = new Date(view.year, view.month - 1 + delta, 1);
    setView({ year: d.getFullYear(), month: d.getMonth() + 1 });
    setSelectedDay(1);
  };

  const openEntry = (dateKey: string) => router.push(`/calendar-entry?date=${dateKey}`);

  // 착장 기록은 내 데이터라 비회원에게 보여줄 것이 없다. (훅 순서 유지를 위해 전부 호출한 뒤 분기)
  if (!isLoggedIn) {
    return (
      <LoginGate
        title="착장 기록은 로그인하고 볼 수 있어요"
        body="입은 옷을 날짜별로 남겨두면 다시 꺼내 보기 쉬워요."
      />
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.default)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/home')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>착장 캘린더</Text>
          <Pressable hitSlop={12} onPress={() => openEntry(TODAY)}>
            <Icon name="plus" tintColor={INK} size={20} />
          </Pressable>
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(ContentMax.default)]}>
        {/* 월 네비 */}
        <View style={styles.monthRow}>
          <Pressable hitSlop={10} onPress={() => moveMonth(-1)}>
            <Icon name="chevron.left" tintColor={ink(0.4)} size={16} />
          </Pressable>
          <Text style={styles.monthText}>
            {view.year}년 {view.month}월
          </Text>
          <Pressable hitSlop={10} onPress={() => moveMonth(1)}>
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
                i === 6 && { color: Editorial.textCaption },
              ]}>
              {d}
            </Text>
          ))}
        </View>

        {/* 날짜 그리드 — 기록이 있는 날은 룩 사진이 셀 배경이 된다 */}
        <View style={styles.grid}>
          {cells.map((day, idx) => {
            if (day === null) return <View key={`e${idx}`} style={styles.cell} />;
            const key = toDateKey(view.year, view.month, day);
            const rec = entries[key];
            const on = day === selectedDay;
            return (
              <Pressable key={day} style={styles.cell} onPress={() => setSelectedDay(day)}>
                <View style={[styles.dayInner, on && styles.dayInnerOn]}>
                  {rec?.photo ? (
                    <>
                      <SmartImage uri={rec.photo} width="100%" radius={11} style={styles.dayThumb} />
                      {/* 사진 위에서도 날짜가 읽히도록 얇게 덮는다 */}
                      <View style={styles.dayScrim} />
                    </>
                  ) : rec ? (
                    <View style={styles.dayFill} />
                  ) : null}
                  <Text
                    style={[
                      styles.dayNum,
                      rec && styles.dayNumRec,
                      on && styles.dayNumOn,
                      rec?.photo && styles.dayNumOnPhoto,
                      key === TODAY && styles.dayNumToday,
                    ]}>
                    {day}
                  </Text>
                  {rec?.shared ? (
                    <View style={[styles.sharedDot, !rec.photo && styles.sharedDotDark]} />
                  ) : null}
                </View>
              </Pressable>
            );
          })}
        </View>

        {/* 선택일 상세 */}
        <View style={styles.detail}>
          <View style={styles.detailHead}>
            <Text style={styles.detailDate}>
              {view.month}월 {selectedDay}일
            </Text>
            {entry ? (
              <Pressable
                style={styles.shareBtn}
                onPress={() => setShareOpen(true)}
                hitSlop={8}>
                <Icon name="square.and.arrow.up" tintColor={INK} size={15} />
                <Text style={styles.shareBtnText}>공유</Text>
              </Pressable>
            ) : null}
          </View>

          {entry ? (
            <>
              <Pressable style={styles.recCard} onPress={() => openEntry(selectedKey)}>
                <SmartImage uri={entry.photo} width={60} height={72} radius={12} />
                <View style={styles.recBody}>
                  <Text style={styles.recTitle}>
                    {entry.items.length > 0 ? `옷 ${entry.items.length}개 기록` : '룩 사진 기록'}
                  </Text>
                  <View style={styles.recTags}>
                    {entry.tags.map((t) => (
                      <Text key={t} style={styles.recTag}>
                        #{t}
                      </Text>
                    ))}
                  </View>
                </View>
                <Icon name="chevron.right" tintColor={ink(0.25)} size={15} />
              </Pressable>

              {/* 담긴 옷 미리보기 */}
              {entry.items.length > 0 ? (
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.itemRow}>
                  {entry.items.map((it) => (
                    <View key={`${it.source}:${it.id}`} style={styles.itemChip}>
                      <SmartImage uri={it.image} width={56} aspectRatio={1} radius={10} />
                      <Text style={styles.itemName} numberOfLines={1}>
                        {it.name}
                      </Text>
                    </View>
                  ))}
                </ScrollView>
              ) : null}

              <Text style={styles.sharedNote}>
                {entry.shared ? '함께 쓰는 옷장 친구에게 공개 중' : '나만 보는 기록'}
              </Text>
            </>
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>이 날은 기록된 착장이 없어요</Text>
              <Pressable style={styles.addBtn} onPress={() => openEntry(selectedKey)}>
                <Icon name="plus" tintColor="#fff" size={16} />
                <Text style={styles.addText}>이 날 착장 기록하기</Text>
              </Pressable>
              <Pressable onPress={() => router.push('/chat-mode')}>
                <Text style={styles.subLink}>코디 추천받기</Text>
              </Pressable>
            </View>
          )}
        </View>
      </ScrollView>

      {entry ? (
        <ShareLookSheet
          entry={entry}
          visible={shareOpen}
          onClose={() => setShareOpen(false)}
          onToggleShared={(next) => calendarStore.setShared(entry.date, next)}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 8,
  },
  headerTitle: { fontSize: Type.body, fontWeight: '600', color: INK },

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
  weekday: {
    flex: 1,
    textAlign: 'center',
    fontSize: Type.micro,
    color: Editorial.textCaption,
    fontWeight: '500',
  },

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
  dayInnerOn: { borderWidth: 1.5, borderColor: Editorial.selected },
  dayThumb: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  dayScrim: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: ink(0.3) },
  /* 사진 없이 옷만 기록한 날 — 사진 대신 옅은 면으로 '기록 있음'을 표시 */
  dayFill: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 11,
    backgroundColor: ink(0.07),
  },
  dayNum: { fontSize: Type.caption, color: Editorial.textCaption },
  dayNumRec: { color: INK, fontWeight: '700' },
  dayNumOn: { fontWeight: '700', color: INK },
  dayNumOnPhoto: { color: '#fff' },
  dayNumToday: { textDecorationLine: 'underline' },
  sharedDot: {
    position: 'absolute',
    bottom: 5,
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#fff',
  },
  sharedDotDark: { backgroundColor: ink(0.45) },

  detail: { marginTop: 22 },
  detailHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
    marginLeft: 4,
  },
  detailDate: { fontSize: Type.caption, fontWeight: '600', color: INK },
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    height: 32,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  shareBtnText: { fontSize: Type.micro, fontWeight: '600', color: INK },

  recCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 16,
    padding: 12,
  },
  recBody: { flex: 1, gap: 6 },
  recTitle: { fontSize: Type.footnote, fontWeight: '500', color: INK },
  recTags: { flexDirection: 'row', gap: 8 },
  recTag: { fontSize: Type.micro, color: Editorial.textCaption },

  itemRow: { gap: 8, paddingTop: 12, paddingRight: 16 },
  itemChip: { width: 56 },
  itemName: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 4 },

  sharedNote: { fontSize: Type.micro, color: Editorial.textMuted, marginTop: 12, marginLeft: 4 },

  empty: {
    alignItems: 'center',
    gap: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderStyle: 'dashed',
    borderRadius: 16,
    paddingVertical: 30,
  },
  emptyText: { fontSize: Type.caption, color: Editorial.textCaption },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 18,
    height: 44,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    justifyContent: 'center',
  },
  addText: { fontSize: Type.footnote, color: '#fff', fontWeight: '600' },
  subLink: { fontSize: Type.caption, color: Editorial.textCaption, textDecorationLine: 'underline' },
});
