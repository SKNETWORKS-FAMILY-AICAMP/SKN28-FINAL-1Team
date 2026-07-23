import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ink, ContentMax, Fonts } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const WINE = '#5E2B2F';

type Mode = {
  key: string;
  icon: IconName;
  tint: string;
  title: string;
  desc: string;
  note: string;
};
const MODES: Mode[] = [
  {
    key: 'taste',
    icon: 'sparkles',
    tint: WINE,
    title: '추구미 반영 추천',
    desc: '설정한 취향과 무드를 반영해\n새로운 룩을 제안해요.',
    note: '옷장에 없는 아이템도 추천',
  },
  {
    key: 'closet',
    icon: 'tshirt',
    tint: INK,
    title: '옷장 기반 추천',
    desc: '지금 가지고 있는 옷들로\n입을 수 있는 코디를 짜드려요.',
    note: '내 옷장 42개로 조합',
  },
];

// C3 모드 선택 — 새 대화의 추천 방식 고르기
export default function ChatMode() {
  const { contentStyle } = useBreakpoint();
  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <View style={[styles.top, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/chat')}>
            <Text style={styles.close}>✕</Text>
          </Pressable>
        </View>

        <View style={[styles.head, contentStyle(ContentMax.narrow)]}>
          <Text style={styles.eyebrow}>NEW CHAT</Text>
          <Text style={styles.title}>어떻게 추천받을까요?</Text>
          <Text style={styles.lead}>대화를 시작할 방식을 골라주세요.</Text>
        </View>

        <View style={[styles.cards, contentStyle(ContentMax.narrow)]}>
          {MODES.map((m) => (
            <Pressable
              key={m.key}
              style={styles.card}
              onPress={() => router.push('/chat-room')}>
              <View style={[styles.cardIcon, { backgroundColor: `${m.tint}12` }]}>
                <Icon name={m.icon} tintColor={m.tint} size={24} />
              </View>
              <Text style={styles.cardTitle}>{m.title}</Text>
              <Text style={styles.cardDesc}>{m.desc}</Text>
              <View style={styles.cardFoot}>
                <View style={[styles.dot, { backgroundColor: m.tint }]} />
                <Text style={styles.cardNote}>{m.note}</Text>
                <View style={styles.spacer} />
                <Icon name="arrow.right" tintColor={ink(0.35)} size={16} />
              </View>
            </Pressable>
          ))}
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

  head: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 8 },
  eyebrow: { fontSize: 11, letterSpacing: 2, color: ink(0.4), fontWeight: '600' },
  title: { fontFamily: Fonts.serif, fontSize: 28, color: INK, marginTop: 10 },
  lead: { fontSize: 14, color: ink(0.5), marginTop: 10 },

  cards: { paddingHorizontal: 24, paddingTop: 24, gap: 14 },
  card: {
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 20,
    padding: 20,
    gap: 12,
  },
  cardIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: { fontFamily: Fonts.serif, fontSize: 20, color: INK, marginTop: 2 },
  cardDesc: { fontSize: 13.5, color: ink(0.55), lineHeight: 20 },
  cardFoot: { flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: 4 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  cardNote: { fontSize: 12, color: ink(0.45), fontWeight: '500' },
  spacer: { flex: 1 },
});
