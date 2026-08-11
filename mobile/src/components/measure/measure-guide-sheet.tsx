import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import {
  BODY_MEASURES,
  BODY_MEASURE_BY_KEY,
  type BodyMeasureKey,
} from '@/constants/body-measures';
import { Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

import { BodyFigureAll } from './body-figure';

const INK = Editorial.ink;

/**
 * '재는 법' 안내 시트 — 마네킹 하나에 10곳을 전부 찍고, 번호로 목록과 잇는다.
 *
 * 값만 보여주면 사용자는 어깨너비를 등을 돌아 재고 4~5cm 크게 적는다(가장 흔한 오차).
 * 숫자를 고칠 수 있게 열어 둔 이상, 기준을 그림으로 같이 줘야 고친 값이 쓸모 있다.
 *
 * 항목을 하나씩 넘겨 보는 방식을 쓰지 않는다 — 열 곳의 위아래 관계가 안 보이고,
 * 자기가 찾는 항목까지 몇 번을 넘겨야 하는지 모른 채 넘기게 된다.
 * 특정 항목으로 열면(ⓘ) 그 번호만 진하게 남기고 나머지는 흐리게 해서 눈이 바로 간다.
 */
export function MeasureGuideSheet({
  visible,
  measureKey,
  onClose,
}: {
  visible: boolean;
  /** 강조할 항목. null 이면 10개를 같은 세기로 보여준다 */
  measureKey: BodyMeasureKey | null;
  onClose: () => void;
}) {
  const { isDesktop } = useBreakpoint();

  /* 주의사항은 강조된 항목 것을 보여주고, 특정 항목 없이 열렸으면 어깨너비 것을 쓴다 —
     10개 주의사항을 한 번에 늘어놓으면 정작 가장 많이 틀리는 어깨가 묻힌다. */
  const noted = BODY_MEASURE_BY_KEY[measureKey ?? 'shoulder'];

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
            <Text style={styles.title}>재는 법</Text>
            <Pressable hitSlop={10} onPress={onClose}>
              <Icon name="xmark" tintColor={ink(0.5)} size={20} />
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.body}>
            <View style={styles.figureWrap}>
              <BodyFigureAll highlight={measureKey} width={228} />
            </View>

            <View style={styles.list}>
              {BODY_MEASURES.map((spec, i) => {
                const on = spec.key === measureKey;
                return (
                  <View key={spec.key} style={[styles.row, on && styles.rowOn]}>
                    <View style={[styles.no, on && styles.noOn]}>
                      <Text style={[styles.noText, on && styles.noTextOn]}>{i + 1}</Text>
                    </View>
                    <View style={styles.rowTexts}>
                      <Text style={[styles.rowLabel, on && styles.rowLabelOn]}>{spec.label}</Text>
                      <Text style={styles.rowSummary}>{spec.summary}</Text>
                    </View>
                  </View>
                );
              })}
            </View>

            {/* 재는 순서는 한 항목 것만 편다 — 10개를 다 늘어놓으면 30줄이 되어 목록이 묻힌다.
                ⓘ 로 연 항목이 있으면 그 항목, 그냥 열었으면 가장 많이 틀리는 어깨너비. */}
            <View style={styles.detail}>
              <Text style={styles.detailHead}>{noted.label} 자세히</Text>
              {noted.steps.map((step, i) => (
                <View key={step} style={styles.stepRow}>
                  <Text style={styles.stepNo}>{i + 1}</Text>
                  <Text style={styles.stepText}>{step}</Text>
                </View>
              ))}
              {noted.caution ? (
                <View style={styles.caution}>
                  <Icon name="exclamationmark.triangle" tintColor={Editorial.wine} size={14} />
                  <Text style={styles.cautionText}>{noted.caution}</Text>
                </View>
              ) : null}
            </View>
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
    marginBottom: 4,
  },
  title: { fontSize: Type.lead, fontWeight: '600', color: INK },

  body: { paddingTop: 12, paddingBottom: 8 },
  figureWrap: {
    alignItems: 'center',
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: Editorial.lineSoft,
    borderRadius: 16,
  },

  list: { marginTop: 16, gap: 2 },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingVertical: 7,
    paddingHorizontal: 8,
    borderRadius: 10,
  },
  rowOn: { backgroundColor: ink(0.05) },
  no: {
    width: 19,
    height: 19,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  noOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  noText: { fontSize: 10.5, fontWeight: '700', color: Editorial.textCaption },
  noTextOn: { color: Editorial.white },
  rowTexts: { flex: 1, gap: 1 },
  rowLabel: { fontSize: Type.footnote, color: INK, fontWeight: '500' },
  rowLabelOn: { fontWeight: '700' },
  rowSummary: { fontSize: Type.caption, color: Editorial.textCaption, lineHeight: 19 },

  detail: {
    marginTop: 18,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: Editorial.lineSoft,
    gap: 9,
  },
  detailHead: { fontSize: Type.footnote, fontWeight: '600', color: INK, marginBottom: 1 },
  stepRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  stepNo: {
    width: 19,
    height: 19,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Editorial.line,
    textAlign: 'center',
    lineHeight: 18,
    fontSize: 10.5,
    color: Editorial.textCaption,
  },
  stepText: { flex: 1, fontSize: Type.caption, color: Editorial.textSoft, lineHeight: 20 },

  caution: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    marginTop: 4,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  cautionText: { flex: 1, fontSize: Type.caption, color: Editorial.textSoft, lineHeight: 19 },
});
