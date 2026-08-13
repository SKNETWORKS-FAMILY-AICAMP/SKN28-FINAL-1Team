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
import { SmartImage, useToast } from '@/components/ui';
import { ContentMax, Editorial, Fonts, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { pickChatPhoto } from '@/lib/pickItemPhoto';
import { chatStore, useChatSession, type ChatMessage } from '@/state/chat';

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
 *   - variant="panel"  : 넓은 화면(≥1280)에서 우측에 상주하는 패널. 들어올 때는 세션이 없고,
 *                        **첫 질문을 보낼 때 대화를 하나 만든다.** 옷장을 보며 묻는 자리라
 *                        옷장 기반 모드로 연다.
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
  /* 패널이 첫 질문에서 만들어 낸 대화. 화면 변형은 항상 sessionId 를 받으므로 쓰이지 않는다. */
  const [panelSessionId, setPanelSessionId] = useState<string | undefined>(undefined);
  const activeId = sessionId ?? panelSessionId;
  const session = useChatSession(activeId);
  /* 아직 대화가 없는 패널에는 시작 인사만 보여준다. 대화가 생기면 서버가 넣어 둔
     인사 메시지가 그 자리를 대신한다. */
  const messages = session?.messages ?? PANEL_SEED;
  /* 타이핑 표시는 답변을 기다리는 '지금'만의 상태라 저장하지 않는다 (state/chat.ts 참고). */
  const [typing, setTyping] = useState(false);
  /* 승인·거절을 보내는 중인 무드 카드. 두 번 눌러 409(번복 금지)를 만나지 않게 잠근다. */
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const toast = useToast();

  const scrollRef = useRef<ScrollView>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const scrollToEnd = () => {
    const t = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 60);
    timers.current.push(t);
  };

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  /* 대화를 열면 내용을 받아온다. 이미 받아 둔 대화는 스토어가 알아서 건너뛴다.
     목록에서 넘어온 세션은 제목·시각만 있고 말풍선이 비어 있어 이 호출이 채운다. */
  useEffect(() => {
    if (!activeId) return;
    chatStore.loadMessages(activeId).catch(() => {
      toast('대화를 불러오지 못했어요', { variant: 'error' });
    });
  }, [activeId, toast]);

  /* 패널은 대화 없이 열리므로 첫 입력에서 하나 만든다. 옷장을 보며 묻는 자리라 옷장 기반. */
  const ensureSession = async (): Promise<string> => {
    if (activeId) return activeId;
    const created = await chatStore.createSession('closet');
    setPanelSessionId(created.id);
    return created.id;
  };

  /**
   * 질문 보내기.
   *
   * 답변은 서버가 바로 주지 않는다 — 질문이 접수되면 실행(run)이 하나 생기고, 별도 워커가
   * 답을 만들 때까지 기다려야 한다(state/chat.ts 의 sendText). 그 동안 타이핑 표시를 띄운다.
   *
   * 입력창은 **보내기 전에** 비운다. 기다리는 동안 글자가 남아 있으면 다시 눌러 같은 질문이
   * 두 번 가기 쉽다. 실패하면 되돌려 다시 보낼 수 있게 한다.
   */
  const send = async () => {
    const t = text.trim();
    if (!t || typing) return;

    setText('');
    setTyping(true);
    scrollToEnd();
    try {
      /* 실패해도 토스트를 띄우지 않는다 — 사유는 대화 안에 한 줄로 남고, 토스트까지 겹치면
         같은 말을 두 번 하면서 정작 사라지는 쪽(토스트)만 눈에 띈다. */
      await chatStore.sendText(await ensureSession(), t);
    } catch (e) {
      setText(t);
      toast(e instanceof Error ? e.message : '메시지를 보내지 못했어요', { variant: 'error' });
    } finally {
      setTyping(false);
      scrollToEnd();
    }
  };

  /**
   * 사진 넣기 — 고른 사진을 올리고 무드 분석을 기다린다(state/chat.ts 의 sendPhoto).
   *
   * 글은 함께 보내지 않는다. 서버는 첨부가 있는 메시지를 무드 분석 전용으로 처리해서 같이
   * 보낸 글이 답변에 반영되지 않기 때문이다 — 그래서 입력창의 글도 건드리지 않고 남겨 둔다.
   */
  const attachPhoto = async () => {
    if (typing) return;
    const uri = await pickChatPhoto();
    if (!uri) return;

    setTyping(true);
    scrollToEnd();
    try {
      await chatStore.sendPhoto(await ensureSession(), uri);
    } catch (e) {
      toast(e instanceof Error ? e.message : '사진을 보내지 못했어요', { variant: 'error' });
    } finally {
      setTyping(false);
      scrollToEnd();
    }
  };

  /**
   * 무드 카드의 두 버튼 — /mood-decision/ 의 APPROVE·REJECT.
   * 승인하면 사진에서 읽은 스타일·색·핏이 이 대화의 추천 조건에 들어가고, 다음 질문부터
   * 자동으로 섞인다. 서버가 첫 결정만 받으므로 되돌릴 수 없다.
   */
  const decideMood = async (attachmentId: string, decision: 'APPROVE' | 'REJECT') => {
    if (!activeId || decidingId) return;
    setDecidingId(attachmentId);
    try {
      await chatStore.decideMood(activeId, attachmentId, decision);
      if (decision === 'APPROVE') toast('이 무드로 추천할게요');
    } catch (e) {
      toast(e instanceof Error ? e.message : '무드를 반영하지 못했어요', { variant: 'error' });
    } finally {
      setDecidingId(null);
    }
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
                    {m.uri ? (
                      <SmartImage
                        uri={m.uri}
                        width="100%"
                        radius={0}
                        contentFit="cover"
                        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
                      />
                    ) : (
                      <Icon name="photo" tintColor={ink(0.3)} size={30} />
                    )}
                  </View>
                ) : (
                  <View style={styles.userBubble}>
                    <Text style={styles.userText}>{m.text}</Text>
                  </View>
                )}
              </View>
            );
          }
          /* 오류는 코지가 한 말이 아니므로 말풍선·아바타를 주지 않는다 —
             답변인 척하면 실패한 것을 답으로 읽게 된다. */
          if (m.kind === 'error') {
            return (
              <View key={m.id} style={styles.errorRow}>
                <Icon name="exclamationmark.triangle" tintColor={Editorial.wine} size={13} />
                <Text style={styles.errorText}>{m.text}</Text>
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
                  /* 카드를 눌러 들어갈 자리는 아직 없다 — /look-detail 은 목업이라 여기서
                     연결하면 방금 받은 추천과 상관없는 룩이 열린다. 카드 안에서 다 보여준다. */
                  <View style={styles.recCard}>
                    <View style={styles.recBody}>
                      <Text style={styles.recTitle}>{m.title}</Text>

                      {/* 아이템 한 줄 — 사진이 있는 것만 그리고, 없으면 이름으로 대신한다 */}
                      <View style={styles.recItems}>
                        {m.items.map((item) => (
                          <View key={item.id} style={styles.recItem}>
                            <SmartImage
                              uri={item.imageUrl}
                              width={64}
                              height={64}
                              radius={10}
                              style={styles.recItemImage}
                            />
                            <Text style={styles.recItemName} numberOfLines={2}>
                              {item.name}
                            </Text>
                            {/* 옷장 옷은 살 필요가 없다는 것이 가격보다 중요한 정보다 */}
                            <Text style={styles.recItemMeta}>
                              {item.fromWardrobe
                                ? '내 옷장'
                                : item.price != null
                                  ? `${item.price.toLocaleString()}원`
                                  : '새 상품'}
                            </Text>
                          </View>
                        ))}
                      </View>

                      {m.totalPrice ? (
                        <Text style={styles.recTotal}>
                          새로 사면 {m.totalPrice.toLocaleString()}원
                        </Text>
                      ) : null}

                      {m.warnings.map((w) => (
                        <Text key={w} style={styles.recWarning}>
                          {w}
                        </Text>
                      ))}
                    </View>
                  </View>
                ) : m.kind === 'mood' ? (
                  <View style={styles.moodCard}>
                    <Text style={styles.moodLead}>사진에서 이런 무드가 보여요</Text>
                    <View style={styles.recTags}>
                      {m.tags.map((t) => (
                        <View key={t} style={styles.recTag}>
                          <Text style={styles.recTagText}>{t}</Text>
                        </View>
                      ))}
                    </View>
                    {/* 한 번 정하면 되돌릴 수 없어(서버가 409) 고른 뒤에는 버튼을 걷는다. */}
                    {m.decision === 'UNDECIDED' ? (
                      <View style={styles.moodBtns}>
                        <Pressable
                          style={[
                            styles.moodPrimary,
                            decidingId === m.attachmentId && styles.moodBusy,
                          ]}
                          disabled={decidingId !== null}
                          onPress={() => decideMood(m.attachmentId, 'APPROVE')}>
                          <Text style={styles.moodPrimaryText}>이걸로 추천받기</Text>
                        </Pressable>
                        <Pressable
                          style={styles.moodGhost}
                          disabled={decidingId !== null}
                          onPress={() => decideMood(m.attachmentId, 'REJECT')}>
                          <Text style={styles.moodGhostText}>아니에요</Text>
                        </Pressable>
                      </View>
                    ) : (
                      <Text style={styles.moodDone}>
                        {m.decision === 'APPROVED'
                          ? '이 무드를 추천 조건에 넣었어요'
                          : '이 무드는 반영하지 않았어요'}
                      </Text>
                    )}
                  </View>
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
          <Pressable style={styles.photoBtn} onPress={attachPhoto} disabled={typing} hitSlop={8}>
            <Icon name="photo" tintColor={ink(typing ? 0.25 : 0.55)} size={22} />
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

  /* 아바타 자리(30) + 간격(8)만큼 들여 코지 말풍선과 왼쪽 선을 맞춘다. */
  errorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingLeft: 38,
    maxWidth: '90%',
  },
  errorText: { flex: 1, fontSize: Type.caption, color: Editorial.wine, lineHeight: 18 },
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
    /* 사진이 모서리 밖으로 넘치지 않게 — 말풍선 모양이 사진에도 그대로 적용돼야 한다. */
    overflow: 'hidden',
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
  recBody: { padding: 14, gap: 10 },
  recTitle: { fontSize: 14, fontWeight: '600', color: INK },

  /* 아이템을 가로로 늘어놓는다. 개수가 적어(보통 3~5) 가로 스크롤 없이 줄바꿈으로 받는다. */
  recItems: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  recItem: { width: 64, gap: 4 },
  recItemImage: { backgroundColor: BONE },
  recItemName: { fontSize: Type.micro, color: INK, lineHeight: 15 },
  recItemMeta: { fontSize: Type.micro, color: Editorial.textCaption },

  recTotal: { fontSize: Type.caption, fontWeight: '600', color: INK },
  /* 서버가 붙이는 주의 문구(예: 예산 초과). 경고색은 쓰되 문장은 서버 말을 그대로 보여준다. */
  recWarning: { fontSize: Type.caption, color: Editorial.wine },
  /* 무드 태그는 최대 5개라 한 줄을 넘길 수 있다 — 넘치면 잘리지 않고 줄바꿈으로 받는다. */
  recTags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  recTag: {
    backgroundColor: Editorial.control,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  recTagText: { fontSize: 11, color: Editorial.textCaption, fontWeight: '500' },
  recCta: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 2 },
  moodCard: {
    borderWidth: 1,
    borderColor: ink(0.12),
    borderRadius: 16,
    padding: 14,
    gap: 10,
    backgroundColor: Editorial.surface,
  },
  moodLead: { fontSize: 13, color: Editorial.textSoft },
  moodBtns: { flexDirection: 'row', gap: 8, marginTop: 2 },
  moodPrimary: {
    height: 36,
    paddingHorizontal: 14,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  moodPrimaryText: { fontSize: 12.5, fontWeight: '600', color: '#fff' },
  moodGhost: {
    height: 36,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  moodGhostText: { fontSize: 12.5, color: Editorial.textCaption },
  moodBusy: { opacity: 0.5 },
  /* 고른 뒤 남는 한 줄. 버튼이 사라진 자리에 결과가 보여야 무엇을 골랐는지 알 수 있다. */
  moodDone: { fontSize: Type.caption, color: Editorial.textCaption, marginTop: 2 },
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
