import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { ChatSessionSheet } from '@/components/chat/session-sheet';
import { Icon } from '@/components/icon';
import { EmptyState } from '@/components/ui';
import { ContentMax, Editorial, ink } from '@/constants/theme';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
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
  active,
  onOpen,
  onManage,
}: {
  session: ChatSession;
  query: string;
  active: boolean;
  onOpen: () => void;
  onManage: () => void;
}) {
  const { tint } = CHAT_MODE_META[session.mode];
  /* 목록에선 제목만 보여준다 — 미리보기 한 줄은 대화를 고르는 데 도움이 안 되고 줄만 길어졌다.
     검색 중에는 남긴다: 제목이 아니라 대화 내용이 걸린 경우 왜 걸렸는지 보여야 하기 때문. */
  const preview = query.trim() ? searchPreview(session, query) : null;
  return (
    <Pressable style={[styles.session, active && styles.sessionOn]} onPress={onOpen}>
      <View style={[styles.thumb, { backgroundColor: `${tint}14` }]}>
        <Icon name="bubble.left.and.bubble.right" tintColor={tint} size={16} />
      </View>
      <View style={styles.sessionBody}>
        <View style={styles.sessionTop}>
          <Text style={styles.sessionTitle} numberOfLines={1}>{session.title}</Text>
          <Text style={styles.sessionTime}>{formatRelativeTime(session.updatedAt)}</Text>
          <Pressable
            hitSlop={10}
            style={styles.sessionMore}
            onPress={onManage}
            accessibilityLabel={`${session.title} 관리`}>
            <Icon name="ellipsis" tintColor={ink(0.4)} size={16} />
          </Pressable>
        </View>
        {preview ? (
          <Text style={styles.sessionLast} numberOfLines={1}>
            {preview}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

/**
 * 지난 대화 목록 (검색 · 모드별 묶음 · 이름변경/삭제).
 *
 * 세 자리에서 같은 목록을 쓴다:
 *   - variant="screen" : 좁은 화면의 채팅 목록 화면
 *   - variant="panel"  : 넓은 화면에서 대화 오른쪽에 상주하는 패널
 *   - 좁은 화면의 햄버거 오버레이 안 (panel 을 그대로 씀)
 *
 * onOpened 는 오버레이처럼 목록이 떠 있는 자리에서 '골랐으니 닫아라'를 알리는 용도다.
 */
export function SessionList({
  variant = 'screen',
  activeId,
  onOpened,
}: {
  variant?: 'screen' | 'panel';
  /** 지금 보고 있는 대화 — 패널에서 어느 줄이 열려 있는지 표시한다 */
  activeId?: string;
  onOpened?: () => void;
}) {
  const isPanel = variant === 'panel';
  const { contentStyle } = useBreakpoint();
  const tabInset = useBottomTabInset();
  // 패널은 폭이 이미 고정이라 최대 폭 제한이 필요 없다.
  const widthStyle = isPanel ? null : contentStyle(ContentMax.wide);

  const groups = useChatGroups();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const toggle = (mode: string) => setCollapsed((c) => ({ ...c, [mode]: !c[mode] }));

  /* 관리 시트는 id 로 열어 둔다 — 세션 객체를 담아두면 이름을 바꾼 뒤 옛 값이 남는다. */
  const [managingId, setManagingId] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const searching = query.trim().length > 0;
  const results = useSearchedSessions(query);

  const isEmpty = groups.every((g) => g.sessions.length === 0);

  const open = (id: string) => {
    router.push({ pathname: '/chat-room', params: { id } });
    onOpened?.();
  };

  const startNew = () => {
    router.push('/chat-mode');
    onOpened?.();
  };

  const row = (session: ChatSession, q: string) => (
    <SessionRow
      key={session.id}
      session={session}
      query={q}
      active={session.id === activeId}
      onOpen={() => open(session.id)}
      onManage={() => setManagingId(session.id)}
    />
  );

  return (
    <>
      {/* 검색 + 새 채팅 한 줄. 화면 이름은 탭·패널 머리에 이미 있어 제목을 따로 두지 않는다. */}
      <View style={[styles.topRow, isPanel && styles.topRowPanel, widthStyle]}>
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
        {/* 패널에는 두지 않는다 — 새 대화는 왼쪽 대화 헤더의 ＋ 로 시작한다(자리 하나에만). */}
        {isPanel ? null : (
          <Pressable style={styles.newBtn} onPress={startNew} accessibilityLabel="새 채팅">
            <Icon name="plus" tintColor="#fff" size={15} />
            <Text style={styles.newText}>새 채팅</Text>
          </Pressable>
        )}
      </View>

      <ScrollView
        style={styles.scroll}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={[
          styles.content,
          { paddingBottom: isPanel ? 24 : tabInset + 24 },
          isPanel && styles.contentPanel,
          widthStyle,
        ]}>
        {isEmpty ? (
          <EmptyState
            icon="bubble.left.and.bubble.right"
            title="아직 대화가 없어요"
            description="무엇을 입을지 물어보면 코지가 룩을 골라드려요."
            actionLabel="새 채팅 시작하기"
            onAction={startNew}
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
              {results.map((s) => row(s, query))}
            </View>
          )
        ) : (
          /* 대화가 하나도 없는 모드는 머리만 남으므로 그룹째 감춘다 */
          groups
            .filter((g) => g.sessions.length > 0)
            .map((g) => {
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
                  {!isCollapsed && g.sessions.map((s) => row(s, ''))}
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
    </>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 20,
    paddingTop: 14,
  },
  topRowPanel: { paddingHorizontal: 14, paddingTop: 12, gap: 8 },

  searchBar: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    height: 42,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: Editorial.control,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  searchInput: { flex: 1, fontSize: 13.5, color: INK, paddingVertical: 0 },

  newBtn: {
    flexShrink: 0,
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

  scroll: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 8 },
  contentPanel: { paddingHorizontal: 14, paddingBottom: 24 },
  empty: { paddingTop: 60 },

  group: { marginTop: 20 },
  groupHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginBottom: 8,
    paddingVertical: 4,
  },
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
  resultCount: { fontSize: 13, fontWeight: '600', color: Editorial.textCaption, marginBottom: 4 },

  session: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 8,
    marginHorizontal: -8,
    borderRadius: 12,
  },
  /* 패널에서 지금 열려 있는 대화 */
  sessionOn: { backgroundColor: Editorial.control },
  thumb: {
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sessionBody: { flex: 1, gap: 3 },
  /* 제목·시간·점세개가 한 줄 — 제목만 늘어나고 나머지는 오른쪽에 붙는다 */
  sessionTop: { flexDirection: 'row', alignItems: 'center' },
  sessionTitle: { flex: 1, fontSize: 14.5, fontWeight: '500', color: Editorial.ink },
  sessionTime: { fontSize: 11, color: Editorial.textCaption, marginLeft: 8 },
  sessionLast: { fontSize: 12.5, color: Editorial.textCaption },
  sessionMore: { paddingLeft: 6, paddingVertical: 4 },
});
