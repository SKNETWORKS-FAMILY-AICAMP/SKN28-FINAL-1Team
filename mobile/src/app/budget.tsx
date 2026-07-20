import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { Fonts } from '@/constants/theme';
import { formatBudget, prefsStore, usePrefs } from '@/state/prefs';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const PRESETS = [
  { label: '5만원', value: 50000 },
  { label: '10만원', value: 100000 },
  { label: '20만원', value: 200000 },
  { label: '30만원', value: 300000 },
  { label: '50만원', value: 500000 },
  { label: '100만원', value: 1000000 },
];

function parseBudgetInput(raw: string): number | null {
  const digits = raw.replace(/[^0-9]/g, '');
  if (!digits) return null;
  const n = Number(digits);
  return n > 0 ? n : null;
}

// 예산 설정 — 상품 추천 시 이 예산 내 아이템을 우선 노출
export default function Budget() {
  const prefs = usePrefs();
  const [sel, setSel] = useState<number | null>(prefs.budget);
  const [custom, setCustom] = useState('');
  const toast = useToast();

  useEffect(() => {
    if (prefs.budget != null && !PRESETS.some((p) => p.value === prefs.budget)) {
      setCustom(String(Math.round(prefs.budget / 10000)));
    }
  }, [prefs.budget]);

  const selectPreset = (value: number) => {
    setCustom('');
    setSel((prev) => (prev === value ? null : value));
  };

  const onCustomChange = (text: string) => {
    const cleaned = text.replace(/[^0-9]/g, '');
    setCustom(cleaned);
    if (cleaned) {
      setSel(parseBudgetInput(cleaned)! * 10000);
    } else if (!PRESETS.some((p) => p.value === sel)) {
      setSel(null);
    }
  };

  const save = () => {
    prefsStore.setBudget(sel);
    toast('예산을 저장했어요', { variant: 'success' });
    router.back();
  };

  const presetActive = (value: number) => sel === value && !custom;

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={styles.header}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>예산 설정</Text>
          <View style={{ width: 20 }} />
        </View>
      </SafeAreaView>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <Text style={styles.title}>한 달 옷 구매 예산은 얼마예요?</Text>
        <Text style={styles.lead}>설정한 금액 안에서 맞는 아이템을 우선 추천해드려요.</Text>

        {/* 프리셋 */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>빠른 선택</Text>
          <View style={styles.grid}>
            {PRESETS.map((p) => {
            const on = presetActive(p.value);
            return (
              <Pressable
                key={p.value}
                style={[styles.chip, on && styles.chipOn]}
                onPress={() => selectPreset(p.value)}>
                <Text style={[styles.chipText, on && styles.chipTextOn]}>{p.label}</Text>
              </Pressable>
            );
            })}
          </View>
        </View>

        {/* 직접 입력 */}
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>직접 입력</Text>
          <View style={[styles.customRow, custom.length > 0 && styles.customRowActive]}>
            <TextInput
              style={styles.customInput}
              value={custom}
              onChangeText={onCustomChange}
              placeholder="예: 15"
              placeholderTextColor={ink(0.3)}
              keyboardType="number-pad"
            />
            <Text style={styles.customUnit}>만원</Text>
          </View>
          <Text style={styles.customHint}>원하는 금액을 만원 단위로 입력해주세요</Text>
        </View>

        <View style={styles.finalRow}>
          <Text style={styles.finalLabel}>최종 설정 금액</Text>
          <Text style={sel != null ? styles.finalValue : styles.finalEmpty}>
            {sel != null ? formatBudget(sel) : '미설정'}
          </Text>
        </View>
      </ScrollView>

      <View style={styles.bottomDivider} />
      <SafeAreaView edges={['bottom']} style={styles.bottomBar}>
        <Pressable style={styles.cta} onPress={save}>
          <Text style={styles.ctaText}>저장</Text>
        </Pressable>
      </SafeAreaView>
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
    paddingBottom: 10,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },

  content: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 24 },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK, lineHeight: 30 },
  lead: { fontSize: 14, color: ink(0.5), lineHeight: 21, marginTop: 12 },

  section: { marginTop: 28, gap: 14 },
  sectionLabel: { fontSize: 16, fontWeight: '600', color: INK, letterSpacing: -0.2 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  chip: {
    width: '31%',
    height: 48,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.12),
    backgroundColor: '#fafaf9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipOn: { backgroundColor: INK, borderColor: INK },
  chipText: { fontSize: 14, color: ink(0.65), fontWeight: '600' },
  chipTextOn: { color: '#fff' },

  customRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: 1,
    borderColor: ink(0.12),
    borderRadius: 14,
    paddingHorizontal: 16,
    height: 52,
    backgroundColor: '#fafaf9',
  },
  customRowActive: { borderColor: INK, backgroundColor: '#ffffff' },
  customInput: { flex: 1, fontSize: 17, fontWeight: '500', color: INK, padding: 0 },
  customUnit: { fontSize: 15, color: ink(0.5), fontWeight: '600' },
  customHint: { fontSize: 12.5, color: ink(0.4), marginTop: -6 },

  finalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 32,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  finalLabel: { fontSize: 14, fontWeight: '500', color: ink(0.5) },
  finalValue: { fontSize: 17, fontWeight: '600', color: INK },
  finalEmpty: { fontSize: 14, color: ink(0.35) },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { backgroundColor: '#fff', paddingHorizontal: 24, paddingTop: 12 },
  cta: {
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '500' },
});
