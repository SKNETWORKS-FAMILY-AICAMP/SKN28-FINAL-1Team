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

import { ErrorState, LoadingState, useToast } from '@/components/ui';
import { BODY_MEASURES, type BodyMeasureSpec } from '@/constants/body-measures';
import { ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { ApiError } from '@/lib/apiClient';
import { MEASURE_KEYS, measureStore, useMeasure, type Measurement } from '@/state/measure';

const INK = Editorial.ink;

function Steps({ active }: { active: number }) {
  return (
    <View style={styles.steps}>
      {[0, 1, 2].map((i) => (
        <View key={i} style={[styles.step, i <= active && styles.stepOn]} />
      ))}
    </View>
  );
}

function isValid(spec: BodyMeasureSpec, raw: string | undefined): boolean {
  const value = Number(raw);
  return Number.isFinite(value) && value >= spec.min && value <= spec.max;
}

// G3 치수 결과·사이즈 매칭 — measureStore 결과를 구독. 완료 시 측정 플로우 닫기
export default function MeasureResult() {
  const { contentStyle } = useBreakpoint();
  const tabInset = useBottomTabInset();
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const { status, result, photos, error, needsBasicInfo } = useMeasure();
  const toast = useToast();
  const [savingDone, setSavingDone] = useState(false);

  // 플로우를 거치지 않고 직접 진입했으면(status idle) 추정을 시작한다.
  useEffect(() => {
    if (status === 'idle') measureStore.estimate();
  }, [status]);

  // 사용자가 직접 수정하는 편집값(문자열) — 결과가 도착하면 초기화
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!result) return;
    // cm는 소수점 1자리, 비율은 소수점 3자리로 표기한다.
    setValues(
      BODY_MEASURES.reduce<Record<string, string>>((acc, spec) => {
        acc[spec.key] = result.measures[spec.key].toFixed(spec.decimals);
        return acc;
      }, {}),
    );
  }, [result]);

  // 로딩 / 에러 — 결과가 아직 없을 때
  if (status !== 'success' || !result) {
    return (
      <View style={styles.container}>
        <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
          <View style={styles.stateWrap}>
            <Steps active={2} />
            {/* 기본 정보가 없어서 실패한 경우엔 재시도 버튼을 주면 안 된다 —
                같은 요청이 같은 400 으로 돌아와 사용자가 빠져나갈 수 없다. */}
            {status === 'error' && needsBasicInfo ? (
              <ErrorState
                title="추정할 정보가 없어요"
                description={error ?? '키·몸무게를 입력하거나 사진을 등록해 주세요.'}
                onRetry={() =>
                  router.replace({ pathname: '/measure-input', params: returnTo ? { returnTo } : {} })
                }
                retryLabel="정보 입력하러 가기"
                retryIcon="chevron.left"
                style={styles.stateFill}
              />
            ) : status === 'error' ? (
              <ErrorState
                title="치수 추정에 실패했어요"
                description={error ?? undefined}
                /* 사진으로 온 실패는 사진으로 다시 시도해야 한다 — estimate() 로 재시도하면
                   사용자가 올린 사진을 무시하고 키·몸무게 기반 결과를 돌려준다. */
                onRetry={() =>
                  photos.front && photos.side
                    ? measureStore.startPhotoMeasurement()
                    : measureStore.estimate()
                }
                style={styles.stateFill}
              />
            ) : (
              <LoadingState
                message={
                  photos.front && photos.side
                    ? '사진으로 치수를 측정하고 있어요… (최대 약 5분)'
                    : '입력 정보로 치수를 추정하고 있어요…'
                }
                style={styles.stateFill}
              />
            )}
          </View>
        </SafeAreaView>
      </View>
    );
  }

  // 완료 — 수정한 값을 서버에 저장(PATCH detail)하고 플로우 닫기
  const onDone = async () => {
    const measures = BODY_MEASURES.reduce((acc, spec) => {
      acc[spec.key] = Number(values[spec.key]);
      return acc;
    }, {} as Measurement);
    if (BODY_MEASURES.some((spec) => !isValid(spec, values[spec.key]))) return;
    setSavingDone(true);
    try {
      await measureStore.saveDetail(measures);
    } catch (e) {
      // 저장 실패해도 로컬 결과엔 반영됨 — 알리고 화면은 닫는다.
      toast(
        e instanceof ApiError ? e.message : '치수 저장에 실패했어요. 임시로 진행할게요.',
        { variant: 'error' },
      );
    } finally {
      setSavingDone(false);
      if (returnTo === 'my') {
        router.replace('/(tabs)/my');
      } else {
        router.replace('/(tabs)/home');
      }
    }
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScrollView contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]} showsVerticalScrollIndicator={false}>
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
            {BODY_MEASURES.map((spec) => (
              <View key={spec.key} style={styles.measureTile}>
                <Text style={styles.measureLabel}>{spec.label}</Text>
                <View style={styles.measureValueRow}>
                  <TextInput
                    style={[
                      styles.measureInput,
                      !isValid(spec, values[spec.key]) && styles.measureInputBad,
                    ]}
                    value={values[spec.key] ?? ''}
                    onChangeText={(t) =>
                      setValues((prev) => ({ ...prev, [spec.key]: t }))
                    }
                    keyboardType="decimal-pad"
                    selectTextOnFocus
                    maxLength={6}
                    returnKeyType="done"
                  />
                  {spec.unit ? <Text style={styles.measureUnit}>{spec.unit}</Text> : null}
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

        <View style={[styles.bottomBar, { paddingBottom: tabInset }, contentStyle(ContentMax.narrow)]}>
          <Pressable
            style={[
              styles.cta,
              (savingDone || BODY_MEASURES.some((spec) => !isValid(spec, values[spec.key]))) && styles.ctaOff,
            ]}
            onPress={onDone}
            disabled={savingDone || BODY_MEASURES.some((spec) => !isValid(spec, values[spec.key]))}>
            <Text style={styles.ctaText}>{savingDone ? '저장 중…' : '완료'}</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },
  content: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 24 },
  stateWrap: { flex: 1, paddingHorizontal: 24, paddingTop: 12 },
  stateFill: { flex: 1 },

  steps: { flexDirection: 'row', gap: 6, marginBottom: 28 },
  step: { flex: 1, height: 3, borderRadius: 2, backgroundColor: ink(0.1) },
  stepOn: { backgroundColor: Editorial.selected },

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
  lead: { fontSize: 14, color: Editorial.textCaption },

  sectionTitle: { fontSize: 16, fontWeight: '600', color: INK, marginTop: 30, marginBottom: 12 },
  sectionHead: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginTop: 30,
    marginBottom: 12,
  },
  sectionTitlePlain: { fontSize: 16, fontWeight: '600', color: INK },
  editHint: { fontSize: 12, color: Editorial.textCaption },
  measureGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 16,
    overflow: 'hidden',
  },
  measureTile: { width: '50%', paddingHorizontal: 18, paddingVertical: 16, gap: 6 },
  measureLabel: { fontSize: 12, color: Editorial.textCaption },
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
  measureInputBad: { color: Editorial.danger, borderBottomColor: Editorial.danger },
  measureUnit: { fontSize: 12, color: Editorial.textCaption, marginBottom: 3 },

  sizeCard: { borderWidth: 1, borderColor: ink(0.09), borderRadius: 16, paddingHorizontal: 16 },
  sizeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 16,
  },
  sizeBrand: { fontSize: 14.5, color: Editorial.ink, fontWeight: '500' },
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
  sizeFit: { fontSize: 12, color: Editorial.textCaption, width: 58, textAlign: 'right' },
  sizeLine: { height: 1, backgroundColor: ink(0.07) },

  note: { fontSize: 11.5, color: Editorial.textCaption, lineHeight: 18, marginTop: 16 },
  remeasure: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'center',
    marginTop: 22,
    paddingVertical: 6,
  },
  remeasureText: { fontSize: 13, color: Editorial.textCaption },

  bottomBar: {
    paddingHorizontal: 24,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  cta: {
    height: 52,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaOff: { opacity: 0.45 },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '500' },
});
