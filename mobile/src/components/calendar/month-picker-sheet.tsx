import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { ContentMax, Editorial, Fonts, ink, Type } from '@/constants/theme';

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

/**
 * 년·월 고르기 — 달력 머리의 '2026년 7월'을 누르면 열린다.
 *
 * 화살표만으로는 한 달씩만 움직여 작년 기록까지 가는 데 열두 번을 눌러야 한다.
 * 년도는 좌우 스텝, 월은 한눈에 보이는 격자로 나눴다(월은 12개라 목록보다 격자가 빠르다).
 */
export function MonthPickerSheet({
  visible,
  year,
  month,
  onClose,
  onSelect,
}: {
  visible: boolean;
  year: number;
  month: number;
  onClose: () => void;
  onSelect: (year: number, month: number) => void;
}) {
  const [draftYear, setDraftYear] = useState(year);
  const [wasVisible, setWasVisible] = useState(visible);

  // 열 때마다 보고 있던 년도에서 시작한다 (effect 가 아니라 렌더 중 조정)
  if (visible !== wasVisible) {
    setWasVisible(visible);
    if (visible) setDraftYear(year);
  }

  const today = new Date();
  const thisYear = today.getFullYear();
  const thisMonth = today.getMonth() + 1;

  const pick = (m: number) => {
    onSelect(draftYear, m);
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.yearRow}>
            <Pressable hitSlop={12} onPress={() => setDraftYear((y) => y - 1)}>
              <Icon name="chevron.left" tintColor={ink(0.45)} size={18} />
            </Pressable>
            <Text style={styles.yearText}>{draftYear}년</Text>
            <Pressable hitSlop={12} onPress={() => setDraftYear((y) => y + 1)}>
              <Icon name="chevron.right" tintColor={ink(0.45)} size={18} />
            </Pressable>
          </View>

          <View style={styles.grid}>
            {MONTHS.map((m) => {
              const on = draftYear === year && m === month;
              const isThisMonth = draftYear === thisYear && m === thisMonth;
              return (
                <Pressable
                  key={m}
                  style={[styles.month, on && styles.monthOn]}
                  onPress={() => pick(m)}>
                  <Text style={[styles.monthText, on && styles.monthTextOn]}>{m}월</Text>
                  {isThisMonth && !on ? <View style={styles.todayDot} /> : null}
                </Pressable>
              );
            })}
          </View>

          <Pressable
            style={styles.todayBtn}
            onPress={() => {
              onSelect(thisYear, thisMonth);
              onClose();
            }}>
            <Text style={styles.todayText}>이번 달로</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: ink(0.35),
  },
  sheet: {
    width: '100%',
    maxWidth: ContentMax.card,
    backgroundColor: Editorial.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Editorial.line,
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 16,
  },

  yearRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 24,
    marginBottom: 18,
  },
  yearText: { fontFamily: Fonts.serif, fontSize: 19, color: Editorial.ink },

  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  month: {
    /* 3열 — gap 8 두 칸을 뺀 나머지를 셋으로 나눈다 */
    width: '31%',
    flexGrow: 1,
    height: 46,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  monthOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  monthText: { fontSize: Type.footnote, color: Editorial.textSoft },
  monthTextOn: { color: '#fff', fontWeight: '700' },
  todayDot: {
    position: 'absolute',
    bottom: 8,
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: ink(0.35),
  },

  todayBtn: { alignSelf: 'center', paddingVertical: 12, paddingHorizontal: 16, marginTop: 6 },
  todayText: {
    fontSize: Type.caption,
    color: Editorial.textCaption,
    textDecorationLine: 'underline',
  },
});
