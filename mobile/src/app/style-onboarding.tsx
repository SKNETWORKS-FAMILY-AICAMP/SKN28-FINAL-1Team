import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts } from '@/constants/theme';

const INK = '#1c1917';
const WINE = '#5E2B2F';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const STYLES = [
  '미니멀', '캐주얼', '스트릿', '클래식', '러블리',
  '시크', '스포티', '빈티지', '로맨틱', '아메카지', '모던', '보이시',
];
const AVOID_COLORS = ['형광', '네온', '쨍한 원색', '올블랙', '파스텔'];
const AVOID_FITS = ['오버핏', '스키니', '크롭', '노출', '타이트'];

function Chip({
  label,
  on,
  onPress,
}: {
  label: string;
  on: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, on && styles.chipOn]}>
      <Text style={[styles.chipText, on && styles.chipTextOn]}>{label}</Text>
    </Pressable>
  );
}

// A7 스타일 온보딩 — 추구미(복수) + 기피 색/핏 → 홈 진입
export default function StyleOnboarding() {
  const [liked, setLiked] = useState<Set<string>>(new Set(['미니멀']));
  const [avoid, setAvoid] = useState<Set<string>>(new Set());

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, v: string) => {
    const next = new Set(set);
    next.has(v) ? next.delete(v) : next.add(v);
    setter(next);
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}>
          <Text style={styles.eyebrow}>STEP 2 · 스타일</Text>
          <Text style={styles.title}>어떤 무드를{'\n'}추구하세요?</Text>
          <Text style={styles.lead}>고를수록 추천이 정확해져요. 여러 개 골라도 좋아요.</Text>

          {/* 추구미 */}
          <View style={styles.section}>
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>추구하는 스타일</Text>
              <Text style={styles.count}>{liked.size}개 선택</Text>
            </View>
            <View style={styles.wrap}>
              {STYLES.map((s) => (
                <Chip
                  key={s}
                  label={s}
                  on={liked.has(s)}
                  onPress={() => toggle(liked, setLiked, s)}
                />
              ))}
            </View>
          </View>

          {/* 기피 색 */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>피하고 싶은 색</Text>
            <View style={styles.wrap}>
              {AVOID_COLORS.map((s) => (
                <Chip
                  key={s}
                  label={s}
                  on={avoid.has(s)}
                  onPress={() => toggle(avoid, setAvoid, s)}
                />
              ))}
            </View>
          </View>

          {/* 기피 핏 */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>피하고 싶은 핏</Text>
            <View style={styles.wrap}>
              {AVOID_FITS.map((s) => (
                <Chip
                  key={s}
                  label={s}
                  on={avoid.has(s)}
                  onPress={() => toggle(avoid, setAvoid, s)}
                />
              ))}
            </View>
          </View>
        </ScrollView>

        <View style={styles.bottomBar}>
          <Pressable style={styles.skip} onPress={() => router.replace('/home')}>
            <Text style={styles.skipText}>나중에</Text>
          </Pressable>
          <Pressable
            style={[styles.cta, liked.size === 0 && styles.ctaDisabled]}
            disabled={liked.size === 0}
            onPress={() => router.replace('/home')}>
            <Text style={styles.ctaText}>시작하기</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: { paddingHorizontal: 24, paddingTop: 20, paddingBottom: 24 },

  eyebrow: { fontSize: 11, letterSpacing: 1.5, color: ink(0.4), fontWeight: '600' },
  title: { fontFamily: Fonts.serif, fontSize: 28, color: INK, marginTop: 10, lineHeight: 34 },
  lead: { fontSize: 14, color: ink(0.5), lineHeight: 21, marginTop: 12 },

  section: { marginTop: 30, gap: 14 },
  sectionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: INK },
  count: { fontSize: 12, color: ink(0.4) },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 },

  chip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    backgroundColor: '#ffffff',
  },
  chipOn: { backgroundColor: WINE, borderColor: WINE },
  chipText: { fontSize: 13.5, color: ink(0.6), fontWeight: '500' },
  chipTextOn: { color: '#ffffff' },

  bottomBar: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 24,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  skip: {
    height: 52,
    paddingHorizontal: 22,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  skipText: { fontSize: 14, color: ink(0.55), fontWeight: '500' },
  cta: {
    flex: 1,
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaDisabled: { backgroundColor: ink(0.22) },
  ctaText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },
});
