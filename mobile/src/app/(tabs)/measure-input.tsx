import { router, useLocalSearchParams } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useEffect, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { measureStore } from '@/state/measure';

const INK = '#1c1917';
const WINE = '#5E2B2F';
const ink = (a: number) => `rgba(28,25,23,${a})`;

function Steps({ active }: { active: number }) {
  return (
    <View style={styles.steps}>
      {[0, 1, 2].map((i) => (
        <View key={i} style={[styles.step, i <= active && styles.stepOn]} />
      ))}
    </View>
  );
}

// G1 체형 정보 입력 — 키/몸무게 + BMI 자동계산
export default function MeasureInput() {
  const { contentStyle } = useBreakpoint();
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const [height, setHeight] = useState('');
  const [weight, setWeight] = useState('');
  const [sex, setSex] = useState<'female' | 'male' | null>(null);

  // 새 측정 플로우 진입 → 이전 데이터 초기화
  useEffect(() => {
    measureStore.reset();
  }, []);

  const h = parseFloat(height);
  const w = parseFloat(weight);
  const bmi = h > 0 && w > 0 ? w / (h / 100) ** 2 : null;
  const bmiLabel = bmi
    ? bmi < 18.5
      ? '저체중'
      : bmi < 23
        ? '정상'
        : bmi < 25
          ? '과체중'
          : '비만'
    : '';
  const canNext = h > 0 && w > 0;

  const goCapture = () => {
    router.push({
      pathname: '/measure-capture',
      params: returnTo ? { returnTo } : undefined,
    });
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <View style={styles.top}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
            <Text style={styles.close}>✕</Text>
          </Pressable>
        </View>

        <ScrollView
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}
          keyboardShouldPersistTaps="handled">
          <Steps active={0} />
          <Text style={styles.eyebrow}>STEP 1 / 3</Text>
          <Text style={styles.title}>체형 정보를 알려주세요</Text>
          <Text style={styles.lead}>키와 몸무게로 치수를 더 정확히 추정해요.</Text>

          {/* 키 */}
          <View style={styles.field}>
            <Text style={styles.label}>키</Text>
            <View style={styles.inputRow}>
              <TextInput
                style={styles.input}
                value={height}
                onChangeText={setHeight}
                placeholder="0"
                placeholderTextColor={ink(0.25)}
                keyboardType="number-pad"
              />
              <Text style={styles.unit}>cm</Text>
            </View>
            <View style={styles.underline} />
          </View>

          {/* 몸무게 */}
          <View style={styles.field}>
            <Text style={styles.label}>몸무게</Text>
            <View style={styles.inputRow}>
              <TextInput
                style={styles.input}
                value={weight}
                onChangeText={setWeight}
                placeholder="0"
                placeholderTextColor={ink(0.25)}
                keyboardType="number-pad"
              />
              <Text style={styles.unit}>kg</Text>
            </View>
            <View style={styles.underline} />
          </View>

          {/* BMI */}
          <View style={styles.field}>
            <Text style={styles.label}>BMI (자동 계산)</Text>
            <View style={styles.inputRow}>
              <Text style={styles.bmiValue}>{bmi ? bmi.toFixed(1) : '—'}</Text>
              {bmiLabel ? (
                <View style={styles.bmiTag}>
                  <Text style={styles.bmiTagText}>{bmiLabel}</Text>
                </View>
              ) : null}
            </View>
            <View style={styles.underline} />
          </View>

          {/* 성별 */}
          <View style={styles.field}>
            <Text style={styles.label}>성별</Text>
            <View style={styles.sexRow}>
              {([
                ['female', '여성'],
                ['male', '남성'],
              ] as const).map(([key, lbl]) => {
                const on = sex === key;
                return (
                  <Pressable
                    key={key}
                    style={[styles.sexChip, on && styles.sexChipOn]}
                    onPress={() => setSex(key)}>
                    <Text style={[styles.sexText, on && styles.sexTextOn]}>{lbl}</Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          <Pressable style={styles.skipWrap} hitSlop={8} onPress={goCapture}>
            <Text style={styles.skipText}>입력 없이 건너뛰기</Text>
          </Pressable>
        </ScrollView>

        <View style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
          <Pressable
            style={[styles.cta, !canNext && styles.ctaDisabled]}
            disabled={!canNext}
            onPress={() => {
              measureStore.setInput({ height: h, weight: w, sex: sex ?? 'none' });
              goCapture();
            }}>
            <Text style={styles.ctaText}>다음</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  top: { paddingHorizontal: 24, paddingTop: 8, alignItems: 'flex-end' },
  close: { fontSize: 20, color: ink(0.5) },
  content: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 24 },

  steps: { flexDirection: 'row', gap: 6, marginBottom: 24 },
  step: { flex: 1, height: 3, borderRadius: 2, backgroundColor: ink(0.1) },
  stepOn: { backgroundColor: INK },

  eyebrow: { fontSize: 11, letterSpacing: 1.5, color: ink(0.4), fontWeight: '600' },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK, marginTop: 10, lineHeight: 30 },
  lead: { fontSize: 14, color: ink(0.5), marginTop: 12 },

  field: { marginTop: 28 },
  label: { fontSize: 13, fontWeight: '600', color: ink(0.55), letterSpacing: 0.2 },
  inputRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, marginTop: 8 },
  input: { flex: 1, fontFamily: Fonts.serif, fontSize: 26, color: ink(0.9), padding: 0 },
  unit: { fontSize: 14, color: ink(0.4), marginBottom: 4 },
  underline: { marginTop: 8, height: 1, backgroundColor: ink(0.15) },

  bmiValue: { flex: 1, fontFamily: Fonts.serif, fontSize: 26, color: ink(0.9) },
  bmiTag: {
    backgroundColor: '#f3e4de',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    marginBottom: 4,
  },
  bmiTagText: { fontSize: 11, color: WINE, fontWeight: '600' },

  sexRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  sexChip: {
    flex: 1,
    height: 44,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  sexChipOn: { backgroundColor: INK, borderColor: INK },
  sexText: { fontSize: 13, color: ink(0.6), fontWeight: '500' },
  sexTextOn: { color: '#fff' },

  bottomBar: {
    paddingHorizontal: 24,
    paddingTop: 8,
    paddingBottom: 4,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  skipWrap: { alignItems: 'center', marginTop: 40, paddingVertical: 4 },
  skipText: { fontSize: 14, color: ink(0.5), fontWeight: '500', textDecorationLine: 'underline' },
  cta: {
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaDisabled: { backgroundColor: ink(0.22) },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '500' },
});
