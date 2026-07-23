import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { ink, Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { prefsStore, usePrefs } from '@/state/prefs';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = '#1c1917';

const SEASONS = [
  { label: '봄 웜', desc: '화사하고 맑은 웜톤', swatch: '#F5A26B' },
  { label: '여름 쿨', desc: '부드럽고 시원한 쿨톤', swatch: '#9FB4CE' },
  { label: '가을 웜', desc: '깊고 따뜻한 웜톤', swatch: '#B5793B' },
  { label: '겨울 쿨', desc: '선명하고 차가운 쿨톤', swatch: '#3B4A6B' },
];

// 퍼스널컬러 설정 — 4계절 톤 중 선택 (추천 색 조합의 기준)
export default function PersonalColor() {
  const { contentStyle } = useBreakpoint();
  const prefs = usePrefs();
  const [sel, setSel] = useState<string | null>(prefs.personalColor);
  const toast = useToast();

  const save = () => {
    prefsStore.setPersonalColor(sel);
    toast('퍼스널컬러를 저장했어요', { variant: 'success' });
    goBack('/(tabs)/my');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>퍼스널컬러</Text>
          <View style={{ width: 20 }} />
        </View>
      </SafeAreaView>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
        <Text style={styles.title}>어떤 톤이 가장 잘 어울려요?</Text>
        <Text style={styles.lead}>얼굴이 화사해 보이는 톤을 골라주세요. 추천 색 조합에 반영해요.</Text>

        <View style={styles.grid}>
          {SEASONS.map((s) => {
            const on = sel === s.label;
            return (
              <Pressable
                key={s.label}
                style={[styles.card, on && styles.cardOn]}
                onPress={() => setSel(on ? null : s.label)}>
                <View style={styles.cardTop}>
                  <View style={styles.cardHead}>
                    <View style={[styles.swatch, { backgroundColor: s.swatch }]} />
                    <Text style={styles.cardLabel}>{s.label}</Text>
                  </View>
                  {on ? (
                    <Icon name="checkmark.circle.fill" tintColor={INK} size={24} />
                  ) : null}
                </View>
                <Text style={styles.cardDesc} numberOfLines={2}>
                  {s.desc}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.help}>잘 모르겠으면 나중에 진단하고 골라도 돼요.</Text>
      </ScrollView>

      <View style={styles.bottomDivider} />
      <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
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
  headerTitle: { fontSize: 17, fontWeight: '600', color: INK },

  content: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 24 },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK, lineHeight: 30 },
  lead: { fontSize: 15.5, color: ink(0.5), lineHeight: 23, marginTop: 12 },

  grid: {
    marginTop: 24,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  card: {
    width: '47%',
    borderWidth: 1,
    borderColor: ink(0.12),
    borderRadius: 16,
    padding: 16,
    gap: 10,
    minHeight: 116,
  },
  cardOn: { borderColor: INK, backgroundColor: '#faf9f7' },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  swatch: { width: 32, height: 32, borderRadius: 16, flexShrink: 0 },
  cardLabel: { fontSize: 15, fontWeight: '600', color: ink(0.9), flexShrink: 1 },
  cardDesc: { fontSize: 12.5, color: ink(0.48), lineHeight: 18 },

  help: { fontSize: 14, color: ink(0.4), marginTop: 20, textAlign: 'center' },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { backgroundColor: '#fff', paddingHorizontal: 24, paddingTop: 12 },
  cta: {
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { color: '#fff', fontSize: 16, fontWeight: '500' },
});
