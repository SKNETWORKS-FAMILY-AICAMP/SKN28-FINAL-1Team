import { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import {
  BODY_MEASURES,
  BODY_MEASURE_BY_KEY,
  type BodyMeasureKey,
} from '@/constants/body-measures';
import { Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

import { BodyFigure } from './body-figure';

const INK = Editorial.ink;

/**
 * '재는 법' 안내 시트 — 도식 + 순서 + 주의.
 *
 * 값만 보여주면 사용자는 어깨너비를 등을 돌아 재고 4~5cm 크게 적는다(가장 흔한 오차).
 * 숫자를 고칠 수 있게 열어 둔 이상, 기준을 그림으로 같이 줘야 고친 값이 쓸모 있다.
 *
 * 열 때 항목 하나를 받지만 시트 안에서 10개를 옮겨 다닐 수 있다 — 하나를 고치러 들어온
 * 사람이 나머지도 확인하는 흐름이라, 닫았다 여는 왕복을 만들지 않는다.
 */
export function MeasureGuideSheet({
  visible,
  measureKey,
  onClose,
}: {
  visible: boolean;
  measureKey: BodyMeasureKey | null;
  onClose: () => void;
}) {
  const { isDesktop } = useBreakpoint();
  const [active, setActive] = useState<BodyMeasureKey>(measureKey ?? 'shoulder');

  // 열 때마다 호출부가 지정한 항목으로 되돌린다 (지난번에 넘겨 본 항목이 남지 않게).
  useEffect(() => {
    if (visible && measureKey) setActive(measureKey);
  }, [visible, measureKey]);

  const spec = BODY_MEASURE_BY_KEY[active];

  return (
    <Modal
      visible={visible}
      transparent
      animationType={isDesktop ? 'fade' : 'slide'}
      onRequestClose={onClose}>
      <Pressable style={[styles.backdrop, isDesktop && styles.backdropCenter]} onPress={onClose}>
        <Pressable
          style={[styles.sheet, isDesktop && styles.dialog]}
          onPress={(e) => e.stopPropagation()}>
          {isDesktop ? null : <View style={styles.handle} />}

          <View style={styles.head}>
            <Text style={styles.title}>{spec.label} 재는 법</Text>
            <Pressable hitSlop={10} onPress={onClose}>
              <Icon name="xmark" tintColor={ink(0.5)} size={20} />
            </Pressable>
          </View>

          {/* 항목 전환 — 같은 인체 위에서 표시만 바뀐다 */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chips}>
            {BODY_MEASURES.map((m) => {
              const on = m.key === active;
              return (
                <Pressable
                  key={m.key}
                  style={[styles.chip, on && styles.chipOn]}
                  onPress={() => setActive(m.key)}>
                  <Text style={[styles.chipText, on && styles.chipTextOn]}>{m.label}</Text>
                </Pressable>
              );
            })}
          </ScrollView>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.body}>
            <View style={styles.figureWrap}>
              <BodyFigure measureKey={active} size={168} />
            </View>

            <Text style={styles.summary}>{spec.summary}</Text>

            <View style={styles.steps}>
              {spec.steps.map((step, i) => (
                <View key={step} style={styles.stepRow}>
                  <Text style={styles.stepNo}>{i + 1}</Text>
                  <Text style={styles.stepText}>{step}</Text>
                </View>
              ))}
            </View>

            {spec.caution ? (
              <View style={styles.caution}>
                <Icon name="exclamationmark.triangle" tintColor={Editorial.wine} size={14} />
                <Text style={styles.cautionText}>{spec.caution}</Text>
              </View>
            ) : null}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: ink(0.42), justifyContent: 'flex-end' },
  backdropCenter: { justifyContent: 'center', alignItems: 'center', padding: 24 },

  sheet: {
    backgroundColor: Editorial.surface,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    paddingHorizontal: 20,
    paddingBottom: 28,
    maxHeight: '88%',
  },
  dialog: {
    width: '100%',
    maxWidth: 440,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Editorial.line,
    paddingTop: 20,
    maxHeight: '86%',
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: ink(0.14),
    alignSelf: 'center',
    marginTop: 10,
    marginBottom: 14,
  },

  head: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  title: { fontSize: Type.lead, fontWeight: '600', color: INK },

  chips: { gap: 8, paddingRight: 4, paddingBottom: 4 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  chipOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  chipText: { fontSize: Type.caption, color: Editorial.textCaption },
  chipTextOn: { color: Editorial.white },

  body: { paddingTop: 16, paddingBottom: 8 },
  figureWrap: {
    alignItems: 'center',
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: Editorial.lineSoft,
    borderRadius: 16,
  },

  summary: { fontSize: Type.body, color: INK, lineHeight: 23, marginTop: 18 },

  steps: { marginTop: 14, gap: 10 },
  stepRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  stepNo: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Editorial.line,
    textAlign: 'center',
    lineHeight: 19,
    fontSize: Type.micro,
    color: Editorial.textCaption,
  },
  stepText: { flex: 1, fontSize: Type.footnote, color: Editorial.textSoft, lineHeight: 21 },

  caution: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    marginTop: 18,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  cautionText: { flex: 1, fontSize: Type.caption, color: Editorial.textSoft, lineHeight: 19 },
});
