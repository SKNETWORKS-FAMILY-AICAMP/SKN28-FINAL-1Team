import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, ContentMax, Fonts } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { CHAT_MODE_META, chatStore, type ChatMode as Mode } from '@/state/chat';

const INK = Editorial.ink;

/** 카드 문구는 이 화면만의 것이고, 이름·색은 목록과 공유한다(CHAT_MODE_META). */
type ModeCard = {
  key: Mode;
  icon: IconName;
  title: string;
  desc: string;
  note: string;
};
const MODES: ModeCard[] = [
  {
    key: 'taste',
    icon: 'sparkles',
    title: '추구미 반영 추천',
    desc: '설정한 취향과 무드를 반영해\n새로운 룩을 제안해요.',
    note: '옷장에 없는 아이템도 추천',
  },
  {
    key: 'closet',
    icon: 'tshirt',
    title: '옷장 기반 추천',
    desc: '지금 가지고 있는 옷들로\n입을 수 있는 코디를 짜드려요.',
    note: '내 옷장 42개로 조합',
  },
];

// C3 모드 선택 — 새 대화의 추천 방식 고르기
export default function ChatMode() {
  const { contentStyle } = useBreakpoint();

  /* 여기서 세션을 만들고 대화 화면으로 넘긴다. replace 인 이유 — 모드 선택은 대화로 가는
     경유지라, 대화에서 뒤로 가면 이 화면이 아니라 목록으로 돌아가야 한다. */
  const startChat = (mode: Mode) => {
    const session = chatStore.createSession(mode);
    router.replace({ pathname: '/chat-room', params: { id: session.id } });
  };

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
              onPress={() => startChat(m.key)}>
              <View style={styles.cardHead}>
                <View style={styles.cardIcon}>
                  <Icon name={m.icon} tintColor={CHAT_MODE_META[m.key].tint} size={24} />
                </View>
                <Text style={styles.cardTitle}>{m.title}</Text>
              </View>
              <Text style={styles.cardDesc}>{m.desc}</Text>
              <View style={styles.cardFoot}>
                <View style={[styles.dot, { backgroundColor: CHAT_MODE_META[m.key].tint }]} />
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
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },
  top: { paddingHorizontal: 24, paddingTop: 8, alignItems: 'flex-end' },
  close: { fontSize: 20, color: Editorial.textCaption },

  head: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 8 },
  eyebrow: { fontSize: 11, letterSpacing: 2, color: Editorial.textCaption, fontWeight: '600' },
  title: { fontFamily: Fonts.serif, fontSize: 28, color: INK, marginTop: 10 },
  lead: { fontSize: 14, color: Editorial.textCaption, marginTop: 10 },

  /* 두 카드를 한 줄에 나란히 — 고를 것이 둘뿐이라 위아래로 쌓으면 비교가 어렵다. */
  cards: { flexDirection: 'row', paddingHorizontal: 24, paddingTop: 24, gap: 14 },
  card: {
    flex: 1,
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 20,
    padding: 20,
    gap: 12,
  },
  /* 카드 폭이 절반이 되므로 아이콘을 제목 옆이 아니라 위에 둔다. 옆에 두면
     좁은 화면에서 제목이 아이콘 옆 좁은 틈으로 밀려 줄줄이 쪼개진다. */
  cardHead: { alignItems: 'flex-start', gap: 12 },
  cardIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    // 배경은 두 카드 공통. 모드별로 다른 건 아이콘 글리프와 점 색(m.tint)뿐이다.
    backgroundColor: Editorial.surface,
  },
  cardTitle: { fontFamily: Fonts.serif, fontSize: 20, color: INK },
  cardDesc: { fontSize: 13.5, color: Editorial.textCaption, lineHeight: 20 },
  cardFoot: { flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: 4 },
  dot: { width: 6, height: 6, borderRadius: 3, flexShrink: 0 },
  // 좁은 카드에서 화살표를 밀어내지 않고 스스로 줄바꿈되게
  cardNote: { flexShrink: 1, fontSize: 12, color: Editorial.textCaption, fontWeight: '500' },
  spacer: { flex: 1 },
});
