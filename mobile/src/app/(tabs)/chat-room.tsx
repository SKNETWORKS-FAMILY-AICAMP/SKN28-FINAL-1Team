import { goBack } from '@/lib/goBack';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatConversation } from '@/components/chat/chat-conversation';
import { ChatSessionSheet } from '@/components/chat/session-sheet';
import { Icon } from '@/components/icon';
import { EmptyState } from '@/components/ui';
import { ContentMax, Editorial, ink } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { CHAT_MODE_META, useChatSession, useLatestSession } from '@/state/chat';

const INK = Editorial.ink;

/**
 * C2 채팅 대화 화면.
 * 대화 본문은 ChatConversation 이 담당한다 — 넓은 화면에서 우측 패널로도 같은 컴포넌트를 쓴다.
 */
export default function ChatRoom() {
  const { contentStyle } = useBreakpoint();
  const { id } = useLocalSearchParams<{ id?: string }>();

  /* 옷 상세·저장한 룩처럼 id 없이 들어오는 입구가 있다 → 가장 최근 대화로 이어 붙인다. */
  const requested = useChatSession(id);
  const latest = useLatestSession();
  const session = requested ?? latest;
  const [managing, setManaging] = useState(false);

  /* 이어 붙일 대화가 없으면(전부 삭제했거나 처음이거나) 모드부터 고르게 한다.
     여기서 대화를 몰래 만들면, 마지막 대화를 지우고 나온 직후 빈 '새 대화'가 되살아난다. */
  if (!session) {
    return (
      <View style={styles.container}>
        <SafeAreaView edges={['top']} style={styles.headerSafe}>
          <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
            <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/chat')}>
              <Icon name="chevron.left" tintColor={INK} size={20} />
            </Pressable>
          </View>
        </SafeAreaView>
        <EmptyState
          icon="bubble.left.and.bubble.right"
          title="이어갈 대화가 없어요"
          description="추천 방식을 고르면 새 대화를 시작해요."
          actionLabel="새 채팅 시작하기"
          onAction={() => router.replace('/chat-mode')}
        />
      </View>
    );
  }

  const mode = CHAT_MODE_META[session.mode];

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/chat')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <View style={styles.headerCenter}>
            <Text style={styles.headerTitle} numberOfLines={1}>{session.title}</Text>
            <View style={styles.modeBadge}>
              <View style={[styles.modeDot, { backgroundColor: mode.tint }]} />
              <Text style={styles.modeText}>{mode.label}</Text>
            </View>
          </View>
          <Pressable hitSlop={12} onPress={() => setManaging(true)} accessibilityLabel="대화 관리">
            <Icon name="ellipsis" tintColor={ink(0.5)} size={18} />
          </Pressable>
        </View>
      </SafeAreaView>
      <View style={styles.divider} />

      <ChatConversation variant="screen" sessionId={session.id} />

      <ChatSessionSheet
        visible={managing}
        session={session}
        onClose={() => setManaging(false)}
        onDeleted={() => goBack('/(tabs)/chat')}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },

  headerSafe: { backgroundColor: Editorial.page },
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
  modeDot: { width: 5, height: 5, borderRadius: 2.5 },
  modeText: { fontSize: 11, color: Editorial.textCaption },
  divider: { height: 1, backgroundColor: ink(0.08) },
});
