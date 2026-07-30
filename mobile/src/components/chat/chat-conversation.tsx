import { router } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
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

import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { chatStore, nextMessageId, useChatSession, type ChatMessage } from '@/state/chat';

const INK = Editorial.ink;
const BONE = Editorial.bone;

const QUICK = ['더 캐주얼하게', '다른 색으로', '아우터 추천', '신발만 바꿔줘'];

/** 사이드 패널에서 쓰는 시작 인사 — 넓은 화면에선 옷장을 보며 바로 물어보는 흐름이다. */
const PANEL_SEED: ChatMessage[] = [
  {
    id: 'p1',
    role: 'ai',
    kind: 'text',
    text: '무엇을 입을지 고민되면 물어보세요.\n옷장을 보면서 바로 추천해드릴게요.',
  },
];

// 타이핑 표시 — 점 3개가 순차로 밝아지는 애니메이션
function TypingDots() {
  /* ref 세 개가 아니라 useMemo 하나로 — ref 값을 렌더 중에 읽으면 안 된다(react-hooks/refs). */
  const dots = useMemo(
    () => [new Animated.Value(0.3), new Animated.Value(0.3), new Animated.Value(0.3)],
    [],
  );
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
  }, [dots]);

  return (
    <View style={styles.typing}>
      {dots.map((d, i) => (
        <Animated.View key={i} style={[styles.typingDot, { opacity: d }]} />
      ))}
    </View>
  );
}

/**
 * 대화 본문(메시지 · 빠른 프롬프트 · 입력창).
 *
 * 두 곳에서 쓴다:
 *   - variant="screen" : /chat-room 화면. 헤더는 화면 쪽이 그린다. sessionId 로 세션에 붙는다.
 *   - variant="panel"  : 넓은 화면(≥1280)에서 우측에 상주하는 패널. 세션에 속하지 않는
 *                        즉석 문답이라 대화를 지역 상태로만 들고 있다.
 *
 * 패널은 폭이 이미 고정이라 본문 최대 폭을 걸지 않고, 하단 SafeArea 여백도 쓰지 않는다.
 */
export function ChatConversation({
  variant = 'screen',
  sessionId,
}: {
  variant?: 'screen' | 'panel';
  sessionId?: string;
}) {
  const isPanel = variant === 'panel';
  const { contentStyle } = useBreakpoint();
  // 패널은 자체 폭이 고정이라 최대 폭 제한이 필요 없다.
  const widthStyle = isPanel ? null : contentStyle(ContentMax.narrow);

  const [text, setText] = useState('');
  const session = useChatSession(sessionId);
  const [panelMessages, setPanelMessages] = useState<ChatMessage[]>(PANEL_SEED);
  const messages = session?.messages ?? panelMessages;
  /* 타이핑 표시는 답변을 기다리는 '지금'만의 상태라 저장하지 않는다 (state/chat.ts 참고). */
  const [typing, setTyping] = useState(false);
  const toast = useToast();

  const scrollRef = useRef<ScrollView>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const scrollToEnd = () => {
    const t = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 60);
    timers.current.push(t);
  };

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  /* 스토어는 외부 상태라 setState 의 함수형 갱신을 쓸 수 없다 → 쓸 때마다 현재 값을 읽는다. */
  const append = (...added: ChatMessage[]) => {
    if (sessionId) {
      const current = chatStore.getSession(sessionId)?.messages ?? [];
      chatStore.setMessages(sessionId, [...current, ...added]);
    } else {
      setPanelMessages((m) => [...m, ...added]);
    }
  };

  // 유저 메시지 → 타이핑 표시 → AI 답변 (프로토타입: 정해진 답변)
  const simulateReply = (fromImage: boolean) => {
    setTyping(true);
    scrollToEnd();
    const t = setTimeout(() => {
      setTyping(false);
      append({
        id: nextMessageId(),
        role: 'ai',
        kind: 'text',
        text: fromImage
          ? '사진 잘 받았어요! 이 무드를 추구미로 기억해둘게요.\n비슷한 분위기로 코디를 찾아볼까요?'
          : '좋아요, 말씀하신 방향으로 다시 골라볼게요. 잠시만요…',
      });
      scrollToEnd();
    }, 1500);
    timers.current.push(t);
  };

  const send = () => {
    const t = text.trim();
    if (!t) return;
    append({ id: nextMessageId(), role: 'user', kind: 'text', text: t });
    if (sessionId) chatStore.nameFromFirstMessage(sessionId, t);
    setText('');
    scrollToEnd();
    simulateReply(false);
  };

  // 사진 넣기 — 이 앱은 카메라/피커 없이 목업(예시 데이터)으로 첨부
  const attachPhoto = () => {
    append({ id: nextMessageId(), role: 'user', kind: 'image' });
    toast('사진을 첨부했어요');
    scrollToEnd();
    simulateReply(true);
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={0}>
      <ScrollView
        ref={scrollRef}
        style={styles.flex}
        contentContainerStyle={[styles.messages, widthStyle]}
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
          return (
            <View key={m.id} style={styles.aiRow}>
              <View style={styles.avatar}>
                <Text style={styles.avatarMark}>c</Text>
              </View>
              <View style={styles.aiCol}>
                {m.kind === 'rec' ? (
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

        {typing ? (
          <View style={styles.aiRow}>
            <View style={styles.avatar}>
              <Text style={styles.avatarMark}>c</Text>
            </View>
            <View style={styles.aiCol}>
              <View style={[styles.aiBubble, styles.typingBubble]}>
                <TypingDots />
              </View>
            </View>
          </View>
        ) : null}
      </ScrollView>

      {/* 빠른 프롬프트 */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.quickScroll}
        contentContainerStyle={[styles.quickRow, widthStyle]}
        keyboardShouldPersistTaps="handled">
        {QUICK.map((q) => (
          <Pressable key={q} style={styles.quickChip} onPress={() => setText(q)}>
            <Text style={styles.quickText}>{q}</Text>
          </Pressable>
        ))}
      </ScrollView>

      {/* 입력 바 */}
      <SafeAreaView edges={isPanel ? [] : ['bottom']} style={styles.inputSafe}>
        <View style={[styles.inputBar, widthStyle]}>
          <Pressable style={styles.photoBtn} onPress={attachPhoto} hitSlop={8}>
            <Icon name="photo" tintColor={ink(0.55)} size={22} />
          </Pressable>
          {/* 웹에서 multiline 은 textarea 로 렌더되어 기본 2줄 높이를 갖는다.
              numberOfLines={1} 로 한 줄에서 시작하게 하고, 길어지면 maxHeight 까지 늘어난다. */}
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="메시지를 입력하세요"
            placeholderTextColor={ink(0.35)}
            multiline
            numberOfLines={1}
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
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },

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
    backgroundColor: Editorial.surface,
    borderWidth: 1, borderColor: Editorial.line,
    borderRadius: 18,
    borderTopLeftRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  aiText: { fontSize: 14, color: Editorial.ink, lineHeight: 21 },
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
    backgroundColor: Editorial.surface,
  },
  recImage: {
    height: 150,
    // 말풍선·태그와 같은 연한 톤으로 통일 (bone 은 상대적으로 진하다)
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recImageLabel: { fontFamily: Fonts.serif, fontSize: 16, letterSpacing: 3, color: Editorial.textMuted },
  recBody: { padding: 14, gap: 10 },
  recTitle: { fontSize: 14, fontWeight: '600', color: INK },
  recTags: { flexDirection: 'row', gap: 6 },
  recTag: {
    backgroundColor: Editorial.control,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  recTagText: { fontSize: 11, color: Editorial.textCaption, fontWeight: '500' },
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
  quickText: { fontSize: 13, lineHeight: 16, color: Editorial.textCaption, fontWeight: '500' },

  // 입력 바
  inputSafe: { backgroundColor: Editorial.surface, borderTopWidth: 1, borderTopColor: ink(0.08) },
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
    backgroundColor: Editorial.surface,
    borderWidth: 1, borderColor: Editorial.line,
    borderRadius: 21,
    paddingHorizontal: 16,
    paddingTop: 11,
    paddingBottom: 11,
    fontSize: 14,
    color: Editorial.ink,
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    // 보낼 내용이 없을 땐 면이 아니라 테두리로만 존재한다. 채워지는 건 활성일 때뿐.
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnOn: { backgroundColor: Editorial.cta },
});
