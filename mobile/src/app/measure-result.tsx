import { Icon } from '@/components/icon';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts } from '@/constants/theme';

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

// 초기 추정값(현재 mock — 추후 API 응답으로 대체). 사용자가 직접 수정 가능.
const INITIAL_MEASURES = [
  { label: '어깨너비', value: '41.2', unit: 'cm' },
  { label: '가슴둘레', value: '92.5', unit: 'cm' },
  { label: '허리둘레', value: '78.0', unit: 'cm' },
  { label: '엉덩이둘레', value: '95.8', unit: 'cm' },
];

const SIZES = [
  { brand: '무신사 스탠다드', size: 'M', fit: '딱 맞음' },
  { brand: '유니클로', size: 'L', fit: '여유 있음' },
  { brand: 'COS', size: 'M', fit: '딱 맞음' },
];

// G3 치수 결과·사이즈 매칭 — 완료 시 측정 플로우 닫기
export default function MeasureResult() {
  // 사진 없이 진행했으면(photos=0) 추정 근거 안내문을 다르게 보여준다.
  const { photos } = useLocalSearchParams<{ photos?: string }>();
  const noPhoto = photos === '0';

  // 추정 치수는 사용자가 직접 손볼 수 있도록 편집 가능한 상태로 둔다.
  const [measures, setMeasures] = useState(INITIAL_MEASURES);
  const updateMeasure = (index: number, value: string) =>
    setMeasures((prev) =>
      prev.map((m, i) => (i === index ? { ...m, value } : m)),
    );

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
              {noPhoto
                ? '키·몸무게로 추정한 결과예요.'
                : '사진과 입력 정보로 추정한 결과예요.'}
            </Text>
          </View>

          {/* 추정 치수 — 각 값 탭하여 직접 수정 가능 */}
          <View style={styles.sectionHead}>
            <Text style={styles.sectionTitlePlain}>추정 치수</Text>
            <Text style={styles.editHint}>탭하여 수정</Text>
          </View>
          <View style={styles.measureGrid}>
            {measures.map((m, i) => (
              <View key={m.label} style={styles.measureTile}>
                <Text style={styles.measureLabel}>{m.label}</Text>
                <View style={styles.measureValueRow}>
                  <TextInput
                    style={styles.measureInput}
                    value={m.value}
                    onChangeText={(t) => updateMeasure(i, t)}
                    keyboardType="decimal-pad"
                    selectTextOnFocus
                    maxLength={5}
                    returnKeyType="done"
                  />
                  <Text style={styles.measureUnit}>{m.unit}</Text>
                </View>
              </View>
            ))}
          </View>

          {/* 사이즈 매칭 */}
          <Text style={styles.sectionTitle}>브랜드 사이즈 매칭</Text>
          <View style={styles.sizeCard}>
            {SIZES.map((s, i) => (
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
                {i < SIZES.length - 1 ? <View style={styles.sizeLine} /> : null}
              </View>
            ))}
          </View>

          <Text style={styles.note}>
            * 추정값이라 실제와 오차가 있을 수 있어요. 결과는 2D 가상착장·사이즈 추천에 활용돼요.
          </Text>

          <Pressable style={styles.remeasure} onPress={() => router.replace('/measure-input')}>
            <Icon name="arrow.clockwise" tintColor={ink(0.5)} size={14} />
            <Text style={styles.remeasureText}>다시 측정하기</Text>
          </Pressable>
        </ScrollView>

        <View style={styles.bottomBar}>
          <Pressable
            style={styles.cta}
            onPress={() =>
              router.canDismiss() ? router.dismissAll() : router.replace('/home')
            }>
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

  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 30, marginBottom: 12 },
  sectionHead: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginTop: 30,
    marginBottom: 12,
  },
  sectionTitlePlain: { fontSize: 13, fontWeight: '600', color: INK },
  editHint: { fontSize: 11.5, color: ink(0.4) },
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
    fontSize: 26,
    fontWeight: '600',
    color: INK,
    padding: 0,
    minWidth: 56,
    borderBottomWidth: 1,
    borderBottomColor: ink(0.18),
    paddingBottom: 2,
  },
  measureUnit: { fontSize: 13, color: ink(0.4), marginBottom: 4 },

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
