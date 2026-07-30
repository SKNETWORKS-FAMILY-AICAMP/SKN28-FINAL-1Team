import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatSessionSheet } from '@/components/chat/session-sheet';
import { EmptyState } from '@/components/ui';
import { Editorial, ink, BottomTabInset, Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import {
  CHAT_MODE_META,
  chatStore,
  formatRelativeTime,
  searchPreview,
  useChatGroups,
  useSearchedSessions,
  type ChatSession,
} from '@/state/chat';

const INK = Editorial.ink;

/** 목록의 한 줄. 그룹 목록과 검색 결과가 같은 모양을 써야 하므로 뽑아 뒀다. */
function SessionRow({
  session,
  query,
  onManage,
}: {
  session: ChatSession;
  query: string;
  onManage: () => void;
}) {
  const { tint } = CHAT_MODE_META[session.mode];
  return (
    <Pressable
      style={styles.session}
      onPress={() => router.push({ pathname: '/chat-room', params: { id: session.id } })}>
      <View style={[styles.thumb, { backgroundColor: `${tint}14` }]}>
        <Icon name="bubble.left.and.bubble.right" tintColor={tint} size={18} />
      </View>
      <View style={styles.sessionBody}>
        <View style={styles.sessionTop}>
          <Text style={styles.sessionTitle} numberOfLines={1}>{session.title}</Text>
          <Text style={styles.sessionTime}>{formatRelativeTime(session.updatedAt)}</Text>
        </View>
        <Text style={styles.sessionLast} numberOfLines={1}>
          {searchPreview(session, query)}
        </Text>
      </View>
      <Pressable
        hitSlop={10}
        style={styles.sessionMore}
        onPress={onManage}
        accessibilityLabel={`${session.title} 관리`}>
        <Icon name="ellipsis" tintColor={ink(0.4)} size={16} />
      </Pressable>
    </Pressable>
  );
}

// C1 채팅 탭 — 모드별 세션 목록 (그룹 접기 지원) · 검색 시엔 최근 순 한 줄로
export default function ChatScreen() {
  const { contentStyle } = useBreakpoint();
  const groups = useChatGroups();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const toggle = (mode: string) => setCollapsed((c) => ({ ...c, [mode]: !c[mode] }));

  /* 관리 시트는 id 로 열어 둔다 — 세션 객체를 담아두면 이름을 바꾼 뒤 옛 값이 남는다. */
  const [managingId, setManagingId] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const searching = query.trim().length > 0;
  const results = useSearchedSessions(query);

  const isEmpty = groups.every((g) => g.sessions.length === 0);

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        {/* 헤더 */}
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Text style={styles.title}>채팅</Text>
          <Pressable
            style={styles.newBtn}
            onPress={() => router.push('/chat-mode')}>
            <Icon name="plus" tintColor="#fff" size={15} />
            <Text style={styles.newText}>새 채팅</Text>
          </Pressable>
        </View>

        {/* 검색 — 제목과 대화 내용을 함께 훑는다 */}
        <View style={[styles.searchWrap, contentStyle(ContentMax.narrow)]}>
        <View style={styles.searchBar}>
          <Icon name="magnifyingglass" tintColor={ink(0.35)} size={16} />
          <TextInput
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
            placeholder="대화 검색"
            placeholderTextColor={Editorial.textCaption}
            returnKeyType="search"
            clearButtonMode="while-editing"
          />
          {/* iOS 는 clearButtonMode 가 지우기 버튼을 그려주지만 안드로이드·웹은 없다 */}
          {searching ? (
            <Pressable hitSlop={10} onPress={() => setQuery('')} accessibilityLabel="검색어 지우기">
              <Icon name="xmark" tintColor={ink(0.35)} size={14} />
            </Pressable>
          ) : null}
        </View>
        </View>

        <ScrollView
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
          {isEmpty ? (
            <EmptyState
              icon="bubble.left.and.bubble.right"
              title="아직 대화가 없어요"
              description="무엇을 입을지 물어보면 코지가 룩을 골라드려요."
              actionLabel="새 채팅 시작하기"
              onAction={() => router.push('/chat-mode')}
              style={styles.empty}
            />
          ) : searching ? (
            results.length === 0 ? (
              <EmptyState
                icon="magnifyingglass"
                title={`'${query.trim()}' 검색 결과가 없어요`}
                description="대화 제목과 주고받은 내용에서 찾아요."
                style={styles.empty}
              />
            ) : (
              <View style={styles.group}>
                <Text style={styles.resultCount}>{results.length}개의 대화</Text>
                {results.map((s) => (
                  <SessionRow
                    key={s.id}
                    session={s}
                    query={query}
                    onManage={() => setManagingId(s.id)}
                  />
                ))}
              </View>
            )
          ) : (
            /* 대화가 하나도 없는 모드는 머리만 남으므로 그룹째 감춘다 */
            groups.filter((g) => g.sessions.length > 0).map((g) => {
              const isCollapsed = collapsed[g.mode];
              return (
                <View key={g.mode} style={styles.group}>
                  <Pressable style={styles.groupHead} onPress={() => toggle(g.mode)} hitSlop={8}>
                    <View style={[styles.modeDot, { backgroundColor: g.tint }]} />
                    <Text style={styles.groupTitle}>{g.label}</Text>
                    <Text style={styles.groupCount}>{g.sessions.length}</Text>
                    <View style={styles.groupSpacer} />
                    <Icon
                      name={isCollapsed ? 'chevron.right' : 'chevron.down'}
                      tintColor={ink(0.35)}
                      size={14}
                    />
                  </Pressable>
                  {!isCollapsed &&
                    g.sessions.map((s) => (
                      <SessionRow
                        key={s.id}
                        session={s}
                        query=""
                        onManage={() => setManagingId(s.id)}
                      />
                    ))}
                </View>
              );
            })
          )}
        </ScrollView>

        <ChatSessionSheet
          visible={managingId !== null}
          session={chatStore.getSession(managingId ?? undefined)}
          onClose={() => setManagingId(null)}
        />
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },

  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 12,
  },
  title: { fontFamily: Fonts.serif, fontSize: 26, fontWeight: '500', color: INK },
  newBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Editorial.cta,
    paddingLeft: 12,
    paddingRight: 16,
    height: 38,
    borderRadius: 999,
  },
  newText: { color: '#fff', fontSize: 13, fontWeight: '500' },

  /* 검색 바는 헤더와 같은 열에 맞춘다 — 감싸는 쪽이 폭을, 안쪽이 높이·테두리를 맡는다 */
  searchWrap: { paddingHorizontal: 20 },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    height: 42,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: Editorial.control,
    borderWidth: 1, borderColor: Editorial.line,
  },
  searchInput: { flex: 1, fontSize: 13.5, color: INK, paddingVertical: 0 },
  resultCount: { fontSize: 13, fontWeight: '600', color: Editorial.textCaption, marginBottom: 4 },

  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: BottomTabInset + 24 },
  empty: { paddingTop: 60 },
  group: { marginTop: 20 },
  groupHead: { flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 8, paddingVertical: 4 },
  modeDot: { width: 7, height: 7, borderRadius: 3.5 },
  groupTitle: { fontSize: 13, fontWeight: '600', color: Editorial.textCaption },
  groupCount: {
    fontSize: 11,
    fontWeight: '600',
    color: Editorial.textCaption,
    minWidth: 18,
    height: 18,
    lineHeight: 18,
    textAlign: 'center',
    backgroundColor: Editorial.surfaceTag,
    borderRadius: 9,
    overflow: 'hidden',
  },
  groupSpacer: { flex: 1 },

  session: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  thumb: {
    width: 46,
    height: 46,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sessionBody: { flex: 1, gap: 3 },
  sessionTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  sessionTitle: { flex: 1, fontSize: 14.5, fontWeight: '500', color: Editorial.ink },
  sessionTime: { fontSize: 11, color: Editorial.textCaption, marginLeft: 8 },
  sessionLast: { fontSize: 12.5, color: Editorial.textCaption },
  sessionMore: { paddingLeft: 4, paddingVertical: 6 },
});
