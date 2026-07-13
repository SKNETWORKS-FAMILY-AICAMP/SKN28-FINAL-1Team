import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts } from '@/constants/theme';

const INK = '#1c1917';
const BONE = '#ecebe7';
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

const GUIDE: { icon: IconName; text: string }[] = [
  { icon: 'ruler', text: '카메라와 2m 거리에서 전신이 나오게' },
  { icon: 'figure.stand', text: '팔을 살짝 벌리고 정면·측면으로 서기' },
  { icon: 'sun.max', text: '밝고 단색인 배경에서 촬영' },
  { icon: 'tshirt', text: '몸매가 드러나는 옷을 입어주세요' },
];

// G2 정면·측면 촬영 — 촬영 가이드 + 2컷 업로드
export default function MeasureCapture() {
  const [shots, setShots] = useState<{ front: boolean; side: boolean }>({
    front: false,
    side: false,
  });
  const both = shots.front && shots.side;

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <View style={styles.top}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <Steps active={1} />
          <Text style={styles.eyebrow}>STEP 2 / 3</Text>
          <Text style={styles.title}>정면·측면 사진을{'\n'}촬영해요</Text>
          <Text style={styles.lead}>2장의 사진으로 어깨·가슴·허리 둘레를 추정해요.</Text>

          {/* 촬영 슬롯 2컷 */}
          <View style={styles.slots}>
            {(['front', 'side'] as const).map((k) => {
              const done = shots[k];
              return (
                <Pressable
                  key={k}
                  style={styles.slot}
                  onPress={() => setShots((s) => ({ ...s, [k]: true }))}>
                  <View style={styles.silhouette}>
                    <Icon
                      name={done ? 'checkmark.circle.fill' : 'camera'}
                      tintColor={done ? INK : ink(0.35)}
                      size={26}
                    />
                  </View>
                  <Text style={styles.slotLabel}>{k === 'front' ? '정면' : '측면'}</Text>
                  <Text style={[styles.slotState, done && styles.slotStateDone]}>
                    {done ? '촬영 완료' : '탭하여 촬영'}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {/* 가이드 */}
          <Text style={styles.sectionTitle}>촬영 가이드</Text>
          <View style={styles.guideCard}>
            {GUIDE.map((g, i) => (
              <View key={i} style={styles.guideRow}>
                <View style={styles.guideIcon}>
                  <Icon name={g.icon} tintColor={INK} size={15} />
                </View>
                <Text style={styles.guideText}>{g.text}</Text>
              </View>
            ))}
          </View>

          {/* 프라이버시 */}
          <View style={styles.privacy}>
            <Icon name="lock.shield" tintColor={ink(0.5)} size={15} />
            <Text style={styles.privacyText}>
              사진은 치수 추정에만 쓰이고 90일 후 자동 삭제돼요.
            </Text>
          </View>
        </ScrollView>

        <View style={styles.bottomBar}>
          <Pressable
            style={[styles.cta, !both && styles.ctaDisabled]}
            disabled={!both}
            onPress={() => router.push('/measure-result')}>
            <Text style={styles.ctaText}>
              {both ? '측정 시작하기' : '두 사진을 촬영해주세요'}
            </Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  top: { paddingHorizontal: 20, paddingTop: 8 },
  content: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 24 },

  steps: { flexDirection: 'row', gap: 6, marginBottom: 24 },
  step: { flex: 1, height: 3, borderRadius: 2, backgroundColor: ink(0.1) },
  stepOn: { backgroundColor: INK },

  eyebrow: { fontSize: 11, letterSpacing: 1.5, color: ink(0.4), fontWeight: '600' },
  title: { fontFamily: Fonts.serif, fontSize: 28, color: INK, marginTop: 10, lineHeight: 34 },
  lead: { fontSize: 14, color: ink(0.5), marginTop: 12 },

  slots: { flexDirection: 'row', gap: 12, marginTop: 26 },
  slot: {
    flex: 1,
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 18,
    paddingVertical: 20,
  },
  silhouette: {
    width: 90,
    height: 120,
    borderRadius: 14,
    backgroundColor: BONE,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  slotLabel: { fontSize: 15, fontWeight: '600', color: INK },
  slotState: { fontSize: 12, color: ink(0.4) },
  slotStateDone: { color: INK, fontWeight: '500' },

  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 30, marginBottom: 12 },
  guideCard: { backgroundColor: '#f7f6f3', borderRadius: 16, padding: 8 },
  guideRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 8, paddingVertical: 10 },
  guideIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  guideText: { flex: 1, fontSize: 13.5, color: ink(0.7) },

  privacy: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 20,
    paddingHorizontal: 4,
  },
  privacyText: { flex: 1, fontSize: 12, color: ink(0.45), lineHeight: 18 },

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
  ctaDisabled: { backgroundColor: ink(0.22) },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '500' },
});
