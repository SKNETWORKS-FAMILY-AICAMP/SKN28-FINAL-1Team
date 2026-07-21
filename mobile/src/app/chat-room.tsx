import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import {
  Animated,
  KeyboardAvoidingView,
  Platform,
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
const WINE = '#5E2B2F';
const BONE = '#eae0d3';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const QUICK = ['더 캐주얼하게', '다른 색으로', '아우터 추천', '신발만 바꿔줘'];

type Msg =
  | { id: string; role: 'ai' | 'user'; kind: 'text'; text: string }
  | { id: string; role: 'user'; kind: 'image' }
  | { id: string; role: 'ai'; kind: 'rec'; title: string; tags: string[] }
  | { id: string; role: 'ai'; kind: 'typing' };

const SEED: Msg[] = [
  {
    id: 'a1',
    role: 'ai',
    kind: 'text',
    text: '안녕하세요 코지님! 오늘 서울은 8도로 쌀쌀해요.\n미니멀한 무드로 따뜻한 코디 골라봤어요.',
  },
  { id: 'u1', role: 'user', kind: 'text', text: '출근할 때 입을 거예요' },
  { id: 'a2', role: 'ai', kind: 'text', text: '그럼 단정하면서 포근한 룩은 어떠세요? 니트에 슬랙스를 매치했어요.' },
  { id: 'a3', role: 'ai', kind: 'rec', title: '포근한 니트 오피스룩', tags: ['니트', '슬랙스', '로퍼'] },
];

// 타이핑 표시 — 점 3개가 순차로 밝아지는 애니메이션
function TypingDots() {
  const dots = [useRef(new Animated.Value(0.3)).current, useRef(new Animated.Value(0.3)).current, useRef(new Animated.Value(0.3)).current];
  useEffect(() => {
    const anims = dots.map((d, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 180),
          Animated.timing(d, { toValue: 1, duration: 320, useNativeDriver: true }),
          Animated.timing(d, { toValue: 0.3, duration: 320, useNativeDriver: true }),
          Animated.delay((2 - i) * 180),
        ]),
      ),
    );
    anims.forEach((a) => a.start());
    return () => anims.forEach((a) => a.stop());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <View style={styles.typing}>
      {dots.map((d, i) => (
        <Animated.View key={i} style={[styles.typingDot, { opacity: d }]} />
      ))}
    </View>
  );
}

// C2 채팅 대화 — 말풍선 + 인라인 추천 카드 + 사진 첨부 + AI 타이핑
export default function ChatRoom() {
  const [text, setText] = useState('');
  const [messages, setMessages] = useState<Msg[]>(SEED);
  const toast = useToast();

  const idRef = useRef(100);
  const nextId = () => `m${++idRef.current}`;
  const scrollRef = useRef<ScrollView>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const scrollToEnd = () => {
    const t = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 60);
    timers.current.push(t);
  };

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  // 유저 메시지 → 타이핑 표시 → AI 답변 (프로토타입: 정해진 답변)
  const simulateReply = (fromImage: boolean) => {
    const typingId = nextId();
    setMessages((m) => [...m, { id: typingId, role: 'ai', kind: 'typing' }]);
    scrollToEnd();
    const t = setTimeout(() => {
      const reply: Msg = fromImage
        ? {
            id: nextId(),
            role: 'ai',
            kind: 'text',
            text: '사진 잘 받았어요! 이 무드를 추구미로 기억해둘게요.\n비슷한 분위기로 코디를 찾아볼까요?',
          }
        : {
            id: nextId(),
            role: 'ai',
            kind: 'text',
            text: '좋아요, 말씀하신 방향으로 다시 골라볼게요. 잠시만요…',
          };
      setMessages((m) => m.filter((x) => x.id !== typingId).concat(reply));
      scrollToEnd();
    }, 1500);
    timers.current.push(t);
  };

  const send = () => {
    const t = text.trim();
    if (!t) return;
    setMessages((m) => [...m, { id: nextId(), role: 'user', kind: 'text', text: t }]);
    setText('');
    scrollToEnd();
    simulateReply(false);
  };

  // 사진 넣기 — 이 앱은 카메라/피커 없이 목업(예시 데이터)으로 첨부
  const attachPhoto = () => {
    setMessages((m) => [...m, { id: nextId(), role: 'user', kind: 'image' }]);
    toast('사진을 첨부했어요');
    scrollToEnd();
    simulateReply(true);
  };

  return (
    <View style={styles.container}>
      {/* 헤더 */}
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={styles.header}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <View style={styles.headerCenter}>
            <Text style={styles.headerTitle}>가을 데일리 미니멀</Text>
            <View style={styles.modeBadge}>
              <View style={styles.modeDot} />
              <Text style={styles.modeText}>추구미 반영</Text>
            </View>
          </View>
          <Pressable hitSlop={12}>
            <Icon name="ellipsis" tintColor={ink(0.5)} size={18} />
          </Pressable>
        </View>
      </SafeAreaView>
      <View style={styles.divider} />

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}>
        <ScrollView
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={styles.messages}
          keyboardShouldPersistTaps="handled">
          {messages.map((m) => {
            if (m.role === 'user') {
              return (
                <View key={m.id} style={styles.userRow}>
                  {m.kind === 'image' ? (
                    <View style={styles.userImage}>
                      <Icon name="photo" tintColor={ink(0.3)} size={30} />
                    </View>
                  ) : (
                    <View style={styles.userBubble}>
                      <Text style={styles.userText}>{m.text}</Text>
                    </View>
                  )}
                </View>
              );
            }
            // AI
            return (
              <View key={m.id} style={styles.aiRow}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarMark}>c</Text>
                </View>
                <View style={styles.aiCol}>
                  {m.kind === 'typing' ? (
                    <View style={[styles.aiBubble, styles.typingBubble]}>
                      <TypingDots />
                    </View>
                  ) : m.kind === 'rec' ? (
                    <Pressable style={styles.recCard} onPress={() => router.push('/look-detail')}>
                      <View style={styles.recImage}>
                        <Text style={styles.recImageLabel}>LOOK</Text>
                      </View>
                      <View style={styles.recBody}>
                        <Text style={styles.recTitle}>{m.title}</Text>
                        <View style={styles.recTags}>
                          {m.tags.map((t) => (
                            <View key={t} style={styles.recTag}>
                              <Text style={styles.recTagText}>{t}</Text>
                            </View>
                          ))}
                        </View>
                        <View style={styles.recCta}>
                          <Text style={styles.recCtaText}>룩 자세히 보기</Text>
                          <Icon name="arrow.right" tintColor={INK} size={13} />
                        </View>
                      </View>
                    </Pressable>
                  ) : (
                    <View style={styles.aiBubble}>
                      <Text style={styles.aiText}>{m.text}</Text>
                    </View>
                  )}
                </View>
              </View>
            );
          })}
        </ScrollView>

        {/* 빠른 프롬프트 */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.quickScroll}
          contentContainerStyle={styles.quickRow}
          keyboardShouldPersistTaps="handled">
          {QUICK.map((q) => (
            <Pressable key={q} style={styles.quickChip} onPress={() => setText(q)}>
              <Text style={styles.quickText}>{q}</Text>
            </Pressable>
          ))}
        </ScrollView>

        {/* 입력 바 */}
        <SafeAreaView edges={['bottom']} style={styles.inputSafe}>
          <View style={styles.inputBar}>
            <Pressable style={styles.photoBtn} onPress={attachPhoto} hitSlop={8}>
              <Icon name="photo" tintColor={ink(0.55)} size={22} />
            </Pressable>
            <TextInput
              style={styles.input}
              value={text}
              onChangeText={setText}
              placeholder="메시지를 입력하세요"
              placeholderTextColor={ink(0.35)}
              multiline
            />
            <Pressable
              style={[styles.sendBtn, text.trim().length > 0 && styles.sendBtnOn]}
              onPress={send}>
              <Icon
                name="arrow.up"
                tintColor={text.trim().length > 0 ? '#fff' : ink(0.35)}
                size={18}
              />
            </Pressable>
          </View>
        </SafeAreaView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  flex: { flex: 1 },

  headerSafe: { backgroundColor: '#ffffff' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
  },
  headerCenter: { flex: 1, alignItems: 'center', gap: 3 },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },
  modeBadge: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  modeDot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: WINE },
  modeText: { fontSize: 11, color: ink(0.45) },
  divider: { height: 1, backgroundColor: ink(0.08) },

  messages: { padding: 16, gap: 16 },
  aiRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', maxWidth: '90%' },
  aiCol: { flex: 1, gap: 10 },
  avatar: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  avatarMark: { fontFamily: Fonts.serif, fontSize: 15, color: '#fff' },
  aiBubble: {
    flexShrink: 1,
    alignSelf: 'flex-start',
    backgroundColor: '#f3ece2',
    borderRadius: 18,
    borderTopLeftRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  aiText: { fontSize: 14, color: ink(0.9), lineHeight: 21 },
  typingBubble: { paddingVertical: 15 },
  typing: { flexDirection: 'row', gap: 5, alignItems: 'center' },
  typingDot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: ink(0.45) },

  userRow: { alignSelf: 'flex-end', maxWidth: '80%' },
  userBubble: {
    backgroundColor: INK,
    borderRadius: 18,
    borderTopRightRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  userText: { fontSize: 14, color: '#fff', lineHeight: 21 },
  userImage: {
    width: 150,
    height: 190,
    borderRadius: 18,
    borderTopRightRadius: 6,
    backgroundColor: BONE,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // 추천 카드
  recCard: {
    alignSelf: 'stretch',
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 18,
    overflow: 'hidden',
    backgroundColor: '#fff',
  },
  recImage: {
    height: 150,
    backgroundColor: BONE,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recImageLabel: { fontFamily: Fonts.serif, fontSize: 16, letterSpacing: 3, color: ink(0.25) },
  recBody: { padding: 14, gap: 10 },
  recTitle: { fontSize: 14, fontWeight: '600', color: INK },
  recTags: { flexDirection: 'row', gap: 6 },
  recTag: {
    backgroundColor: '#f3ece2',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  recTagText: { fontSize: 11, color: ink(0.6), fontWeight: '500' },
  recCta: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 2 },
  recCtaText: { fontSize: 13, fontWeight: '600', color: INK },

  // 빠른 프롬프트
  quickScroll: { flexGrow: 0, maxHeight: 52 },
  quickRow: { paddingHorizontal: 16, gap: 8, paddingVertical: 8 },
  quickChip: {
    height: 34,
    justifyContent: 'center',
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  quickText: { fontSize: 13, lineHeight: 16, color: ink(0.6), fontWeight: '500' },

  // 입력 바
  inputSafe: { backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: ink(0.08) },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingHorizontal: 12,
    paddingTop: 10,
    paddingBottom: 6,
  },
  photoBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
  },
  input: {
    flex: 1,
    minHeight: 42,
    maxHeight: 120,
    backgroundColor: '#f3ece2',
    borderRadius: 21,
    paddingHorizontal: 16,
    paddingTop: 11,
    paddingBottom: 11,
    fontSize: 14,
    color: ink(0.9),
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#e9e7e2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnOn: { backgroundColor: INK },
});
