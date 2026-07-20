import { Icon } from '@/components/icon';
import { router, useLocalSearchParams } from 'expo-router';
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

import { ErrorState, LoadingState } from '@/components/ui';
import { Fonts } from '@/constants/theme';
import { measureStore, useMeasure } from '@/state/measure';

const INK = '#1c1917';
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

// 추정 치수 표시 순서·라벨 (값은 measureStore 결과에서). measures 키와 일치.
const MEASURE_ROWS = [
  { key: 'shoulder', label: '어깨너비' },
  { key: 'chest', label: '가슴둘레' },
  { key: 'waist', label: '허리둘레' },
  { key: 'hip', label: '엉덩이둘레' },
] as const;

// G3 치수 결과·사이즈 매칭 — measureStore 결과를 구독. 완료 시 측정 플로우 닫기
export default function MeasureResult() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const { status, result } = useMeasure();

  // 플로우를 거치지 않고 직접 진입했으면(status idle) 추정을 시작한다.
  useEffect(() => {
    if (status === 'idle') measureStore.estimate();
  }, [status]);

  // 사용자가 직접 수정하는 편집값(문자열) — 결과가 도착하면 초기화
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => {
    if (result) {
      // 소수점 1자리로 표기 (예: 78 → "78.0")
      setValues({
        shoulder: result.measures.shoulder.toFixed(1),
        chest: result.measures.chest.toFixed(1),
        waist: result.measures.waist.toFixed(1),
        hip: result.measures.hip.toFixed(1),
      });
    }
  }, [result]);

  // 로딩 / 에러 — 결과가 아직 없을 때
  if (status !== 'success' || !result) {
    return (
      <View style={styles.container}>
        <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
          <View style={styles.stateWrap}>
            <Steps active={2} />
            {status === 'error' ? (
              <ErrorState
                title="치수 추정에 실패했어요"
                onRetry={() => measureStore.estimate()}
                style={styles.stateFill}
              />
            ) : (
              <LoadingState
                message="입력 정보로 치수를 추정하고 있어요…"
                style={styles.stateFill}
              />
            )}
          </View>
        </SafeAreaView>
      </View>
    );
  }

  // 완료 — 수정한 값을 스토어에 반영하고 플로우 닫기
  const onDone = () => {
    const num = (k: keyof typeof result.measures) => {
      const v = parseFloat(values[k]);
      return Number.isFinite(v) ? v : result.measures[k];
    };
    measureStore.updateMeasures({
      shoulder: num('shoulder'),
      chest: num('chest'),
      waist: num('waist'),
      hip: num('hip'),
    });
    if (returnTo === 'my') {
      router.replace('/(tabs)/my');
    } else {
      router.replace('/(tabs)/home');
    }
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <Steps active={2} />

          <View style={styles.hero}>
            <View style={styles.mark}>
              <Icon name="checkmark" tintColor="#fff" size={22} />
            </View>
            <Text style={styles.title}>치수 측정 완료</Text>
            <Text style={styles.lead}>
              {result.usedPhotos
                ? '사진과 입력 정보로 추정한 결과예요.'
                : '키·몸무게로 추정한 결과예요.'}
            </Text>
          </View>

          {/* 추정 치수 — 각 값 탭하여 직접 수정 가능 */}
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitlePlain}>추정 치수</Text>
            <Text style={styles.editHint}>탭하여 수정</Text>
          </View>
          <View style={styles.measureGrid}>
            {MEASURE_ROWS.map((row) => (
              <View key={row.key} style={styles.measureTile}>
                <Text style={styles.measureLabel}>{row.label}</Text>
                <View style={styles.measureValueRow}>
                  <TextInput
                    style={styles.measureInput}
                    value={values[row.key] ?? ''}
                    onChangeText={(t) =>
                      setValues((prev) => ({ ...prev, [row.key]: t }))
                    }
                    keyboardType="decimal-pad"
                    selectTextOnFocus
                    maxLength={5}
                    returnKeyType="done"
                  />
                  <Text style={styles.measureUnit}>cm</Text>
                </View>
              </View>
            ))}
          </View>

          {/* 사이즈 매칭 */}
          <Text style={styles.sectionTitle}>브랜드 사이즈 매칭</Text>
          <View style={styles.sizeCard}>
            {result.sizes.map((s, i) => (
              <View key={s.brand}>
                <View style={styles.sizeRow}>
                  <Text style={styles.sizeBrand}>{s.brand}</Text>
                  <View style={styles.sizeRight}>
                    <View style={styles.sizeBadge}>
                      <Text style={styles.sizeBadgeText}>{s.size}</Text>
                    </View>
                    <Text style={styles.sizeFit}>{s.fit}</Text>
                  </View>
                </View>
                {i < result.sizes.length - 1 ? <View style={styles.sizeLine} /> : null}
              </View>
            ))}
          </View>

          <Text style={styles.note}>
            * 실제와 오차가 있을 수 있어요. 결과는 2D 가상착장·사이즈 추천에 활용돼요.
          </Text>

          <Pressable
            style={styles.remeasure}
            onPress={() =>
              router.replace({
                pathname: '/measure-input',
                params: returnTo ? { returnTo } : undefined,
              })
            }>
            <Icon name="arrow.clockwise" tintColor={ink(0.5)} size={14} />
            <Text style={styles.remeasureText}>다시 측정하기</Text>
          </Pressable>
        </ScrollView>

        <View style={styles.bottomBar}>
          <Pressable style={styles.cta} onPress={onDone}>
            <Text style={styles.ctaText}>완료</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 24 },
  stateWrap: { flex: 1, paddingHorizontal: 24, paddingTop: 12 },
  stateFill: { flex: 1 },

  steps: { flexDirection: 'row', gap: 6, marginBottom: 28 },
  step: { flex: 1, height: 3, borderRadius: 2, backgroundColor: ink(0.1) },
  stepOn: { backgroundColor: INK },

  hero: { alignItems: 'center', gap: 8 },
  mark: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 6,
  },
  title: { fontFamily: Fonts.serif, fontSize: 26, color: INK },
  lead: { fontSize: 14, color: ink(0.5) },

  sectionTitle: { fontSize: 16, fontWeight: '600', color: INK, marginTop: 30, marginBottom: 12 },
  sectionHead: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginTop: 30,
    marginBottom: 12,
  },
  sectionTitlePlain: { fontSize: 16, fontWeight: '600', color: INK },
  editHint: { fontSize: 12, color: ink(0.4) },
  measureGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 16,
    overflow: 'hidden',
  },
  measureTile: { width: '50%', paddingHorizontal: 18, paddingVertical: 16, gap: 6 },
  measureLabel: { fontSize: 12, color: ink(0.45) },
  measureValueRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 4 },
  measureInput: {
    fontFamily: Fonts.serif,
    fontSize: 20,
    fontWeight: '600',
    color: INK,
    padding: 0,
    minWidth: 48,
    borderBottomWidth: 1,
    borderBottomColor: ink(0.18),
    paddingBottom: 2,
  },
  measureUnit: { fontSize: 12, color: ink(0.4), marginBottom: 3 },

  sizeCard: { borderWidth: 1, borderColor: ink(0.09), borderRadius: 16, paddingHorizontal: 16 },
  sizeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 16,
  },
  sizeBrand: { fontSize: 14.5, color: ink(0.9), fontWeight: '500' },
  sizeRight: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  sizeBadge: {
    minWidth: 34,
    height: 30,
    paddingHorizontal: 10,
    borderRadius: 8,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sizeBadgeText: { fontSize: 13, color: '#fff', fontWeight: '700' },
  sizeFit: { fontSize: 12, color: ink(0.45), width: 58, textAlign: 'right' },
  sizeLine: { height: 1, backgroundColor: ink(0.07) },

  note: { fontSize: 11.5, color: ink(0.4), lineHeight: 18, marginTop: 16 },
  remeasure: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'center',
    marginTop: 22,
    paddingVertical: 6,
  },
  remeasureText: { fontSize: 13, color: ink(0.5) },

  bottomBar: {
    paddingHorizontal: 24,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  cta: {
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '500' },
});
