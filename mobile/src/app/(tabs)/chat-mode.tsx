import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, ContentMax, Fonts } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useWardrobeItems } from '@/hooks/use-wardrobe';
import { useAuth } from '@/state/auth';
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
/* 설명은 한 줄 명사구. 카드가 화면 폭을 다 쓰므로 굳이 문장으로 늘려 두 줄을 만들 이유가 없다. */
const MODES: ModeCard[] = [
  {
    key: 'taste',
    icon: 'sparkles',
    title: '추구미 반영 추천',
    desc: '취향과 무드에 맞춘 새 룩',
    note: '옷장에 없는 아이템도 추천',
  },
  {
    key: 'closet',
    icon: 'tshirt',
    title: '옷장 기반 추천',
    desc: '가진 옷으로 짜는 코디',
    note: '', // 실제 옷장 개수로 채운다 (closetNote)
  },
];

// C3 모드 선택 — 새 대화의 추천 방식 고르기
export default function ChatMode() {
  const { contentStyle } = useBreakpoint();
  const { isLoggedIn } = useAuth();
  /* 옷장 화면과 **같은 조건으로** 센다(필터 없음). confirmed=true 로 거르면 0 이 나온다 —
     백엔드에서 직접 넣은 옷은 확인 단계를 거치지 않아 확정 표시가 없기 때문이다(closet.tsx 참고).
     여기서만 다르게 세면 옷장엔 18벌인데 "옷을 먼저 등록해 주세요" 라고 말하게 된다. */
  const { items, loading } = useWardrobeItems({}, isLoggedIn);

  /* 개수를 고정값으로 두면 옷장이 비어 있어도 "42개로 조합"이라고 말하게 된다.
     불러오는 중이거나 비회원이면 개수를 빼고, 옷이 없으면 먼저 등록하라고 알린다. */
  const closetNote = !isLoggedIn
    ? '로그인하면 내 옷으로 조합해요'
    : loading
      ? '내 옷장으로 조합'
      : items.length === 0
        ? '옷을 먼저 등록해 주세요'
        : `내 옷장 ${items.length}개로 조합`;

  /* 여기서 세션을 만들고 대화 화면으로 넘긴다. replace 인 이유 — 모드 선택은 대화로 가는
     경유지라, 대화에서 뒤로 가면 이 화면이 아니라 목록으로 돌아가야 한다. */
  const startChat = (mode: Mode) => {
    const session = chatStore.createSession(mode);
    router.replace({ pathname: '/chat-room', params: { id: session.id } });
  };

  return (
    <View style={styles.container}>
      {/* 닫기 버튼은 두지 않는다 — 이 화면에서도 탭바(데스크톱은 사이드바)가 그대로 보여
          나갈 길이 이미 있고, 화면 구석의 ✕ 는 무엇을 닫는지 읽히지 않는다. */}
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
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
              {/* 점·화살표를 두지 않는다 — 카드 전체가 이미 누를 수 있고, 이 줄은 조건 한 마디다 */}
              <Text style={styles.cardNote}>{m.key === 'closet' ? closetNote : m.note}</Text>
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

  // ✕ 를 없앤 만큼 제목이 화면 위쪽에 붙지 않게 여백을 옮겨 왔다.
  head: { paddingHorizontal: 24, paddingTop: 28, paddingBottom: 8 },
  eyebrow: { fontSize: 11, letterSpacing: 2, color: Editorial.textCaption, fontWeight: '600' },
  title: { fontFamily: Fonts.serif, fontSize: 28, color: INK, marginTop: 10 },
  lead: { fontSize: 14, color: Editorial.textCaption, marginTop: 10 },

  /* 두 카드를 위아래로 쌓는다. 나란히 두면 폰에서 카드 폭이 절반이라
     '추구미 반영 추천' 같은 제목이 두 줄로 쪼개진다. */
  cards: { paddingHorizontal: 24, paddingTop: 24, gap: 14 },
  card: {
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 20,
    padding: 20,
    gap: 12,
  },
  /* 카드가 가로로 넓어졌으니 아이콘을 제목 옆에 둔다 — 위에 쌓으면 카드가 길어져
     두 장이 한 화면에 안 들어온다. */
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  cardIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    // 배경은 두 카드 공통. 모드별로 다른 건 아이콘 글리프뿐이다.
    backgroundColor: Editorial.surface,
  },
  cardTitle: { fontFamily: Fonts.serif, fontSize: 20, color: INK },
  cardDesc: { fontSize: 13.5, color: Editorial.textCaption, lineHeight: 20 },
  cardNote: { fontSize: 12, color: Editorial.textCaption, fontWeight: '500', marginTop: 4 },
});
