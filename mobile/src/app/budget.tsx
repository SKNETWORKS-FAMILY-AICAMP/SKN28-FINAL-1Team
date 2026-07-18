import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { Fonts } from '@/constants/theme';
import { formatBudget, prefsStore, usePrefs } from '@/state/prefs';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
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

// 예산 설정 — 상품 추천 시 이 예산 내 아이템을 우선 노출
export default function Budget() {
  const prefs = usePrefs();
  const [sel, setSel] = useState<number | null>(prefs.budget);
  const toast = useToast();

  const save = () => {
    prefsStore.setBudget(sel);
    toast('예산을 저장했어요', { variant: 'success' });
    router.back();
  };

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
        <Text style={styles.title}>한 벌에 얼마까지{'\n'}쓸 수 있어요?</Text>
        <Text style={styles.lead}>이 예산 안에서 살 수 있는 상품을 우선 추천해드려요.</Text>

        {/* 선택된 예산 미리보기 */}
        <View style={styles.preview}>
          <Text style={styles.previewLabel}>내 예산</Text>
          <Text style={styles.previewValue}>
            {sel != null ? formatBudget(sel) : '아직 미설정'}
          </Text>
        </View>

        {/* 프리셋 */}
        <View style={styles.grid}>
          {PRESETS.map((p) => {
            const on = sel === p.value;
            return (
              <Pressable
                key={p.value}
                style={[styles.chip, on && styles.chipOn]}
                onPress={() => setSel(on ? null : p.value)}>
                <Text style={[styles.chipText, on && styles.chipTextOn]}>{p.label}</Text>
              </Pressable>
            );
          })}
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
  title: { fontFamily: Fonts.serif, fontSize: 26, color: INK, lineHeight: 34 },
  lead: { fontSize: 14, color: ink(0.5), lineHeight: 21, marginTop: 12 },

  preview: {
    marginTop: 24,
    backgroundColor: '#f7f6f3',
    borderRadius: 16,
    paddingHorizontal: 20,
    paddingVertical: 20,
    gap: 6,
  },
  previewLabel: { fontSize: 12, color: ink(0.45) },
  previewValue: { fontFamily: Fonts.serif, fontSize: 30, fontWeight: '600', color: INK },

  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 24 },
  chip: {
    width: '31%',
    height: 52,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipOn: { backgroundColor: INK, borderColor: INK },
  chipText: { fontSize: 14.5, color: ink(0.7), fontWeight: '600' },
  chipTextOn: { color: '#fff' },

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
