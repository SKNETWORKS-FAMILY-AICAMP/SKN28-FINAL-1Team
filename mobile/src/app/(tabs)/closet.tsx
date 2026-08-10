import {
  createSharedSpace,
  joinSharedSpace,
  SharedSpaceInviteBanner,
  SharedSpaceInviteSheet,
  SharedSpaceJoinSheet,
  SharedSpaceMembers,
  SharedSpaceOnboarding,
  type SharedSpace,
} from '@/components/closet/shared-space-flow';
import { PhotoSourceSheet } from '@/components/closet/photo-source-sheet';
import { CategoryEditSheet, EmptyState, ErrorState, LoadingState, LoginGate, SearchFilterBar, SegmentedToggle, SmartImage, useToast } from '@/components/ui';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, GridCard, gridCardImageHeight, gridCardWidth , ContentMax} from '@/constants/theme';
import { SHARED_CLOSET_ITEMS } from '@/constants/wardrobe';
import { WARDROBE_FILTER_OPTIONS } from '@/constants/wardrobe-taxonomy';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useRefresh } from '@/hooks/use-refresh';
import { useWardrobeItems } from '@/hooks/use-wardrobe';
import { itemDisplayName, getMySharedRooms, createSharedRoom, joinSharedRoom, listSharedRoomMembers, listSharedRoomItems, renameSharedRoom } from '@/lib/wardrobeApi';
import { Icon } from '@/components/icon';
import { useAuth } from '@/state/auth';
import { uploadJobs, useUploadCompleted, useUploadJobs, useBatchTotal, useBatchCompletedCount } from '@/state/upload-jobs';

const INK = Editorial.ink;

const MEMBER_COLORS = [
  '#FFD54F', // 노랑
  '#4FC3F7', // 하늘
  '#81C784', // 연두
  '#F06292', // 핑크
  '#BA68C8', // 보라
  '#FFB74D', // 주황
];

/* 카드 크기는 창 폭에서 파생되므로 모듈 최상단이 아니라 컴포넌트 안에서 useBreakpoint() 로 구한다.
   (모듈 최상단에서 읽으면 리사이즈에 반응하지 않는다) */
const PAD = GridCard.pad;

/* 카테고리는 백엔드 taxonomy(대분류 8종)를 따른다 — 프론트가 임의 목록을 쓰면 필터가 서버와 어긋난다. */
const DEFAULT_CATEGORIES = WARDROBE_FILTER_OPTIONS;

/** 그리드 카드가 쓰는 최소 형태 — 내 옷장(API)과 공유 옷장(목업)을 한 모양으로 맞춘다. */
type Card = {
  id: string;
  name: string;
  category: string;
  image?: string;
  owner?: string;
};

/* 공유 옷장은 아직 백엔드가 없어 목업을 그대로 쓴다. */
const SHARED_ITEMS: Card[] = SHARED_CLOSET_ITEMS.map((i) => ({
  id: i.id,
  name: i.name,
  category: i.category,
  image: i.image,
  owner: i.owner,
}));

function matchesQuery(item: Card, query: string): boolean {
  const q = query.trim();
  if (!q) return true;
  return item.name.includes(q) || item.category.includes(q);
}

export default function ClosetScreen() {
  const { isLoggedIn } = useAuth();
  const { frameWidth, contentStyle } = useBreakpoint();
  const cardW = gridCardWidth(frameWidth);
  const cardH = gridCardImageHeight(cardW);
  const tabInset = useBottomTabInset();

  const toast = useToast();
  const params = useLocalSearchParams<{ tab?: 'mine' | 'shared' }>();
  const [tab, setTab] = useState<'mine' | 'shared'>('mine');

  // URL 탭 파라미터 감지 및 자동 전환
  useEffect(() => {
    if (params.tab && (params.tab === 'mine' || params.tab === 'shared')) {
      setTab(params.tab);
    }
  }, [params.tab]);

  const [query, setQuery] = useState('');
  const [sharedSpace, setSharedSpace] = useState<SharedSpace | null>(null);
  const [sharedRooms, setSharedRooms] = useState<any[]>([]);
  const [sharedItems, setSharedItems] = useState<Card[]>([]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);
  const [categories, setCategories] = useState<string[]>(DEFAULT_CATEGORIES);
  const [editOpen, setEditOpen] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const { toggle, reset, prune, isActive, matches, label } = useMultiSelectFilter();

  /* 내 옷장은 서버가 출처. 카테고리 필터는 여러 개를 고를 수 있어(멀티) 서버 파라미터로
     넘기지 않고 전체를 받아 프론트에서 걸러낸다 — 서버는 단일 category_large 만 받는다.

     확정 여부로 거르지 않는다. 예전엔 confirmed=true 만 받았는데, 그러면 백엔드에서
     직접 넣은 옷처럼 확인 단계를 거치지 않은 아이템이 옷장에 영영 안 보인다.
     대신 미확인 아이템에는 배지를 달아 구분한다. */
  const { items: apiItems, loading, error, reload } = useWardrobeItems({}, isLoggedIn);
  const { refreshing, onRefresh } = useRefresh(reload);

  /* 등록은 이 화면을 떠나도 계속 돈다(state/upload-jobs.ts). 진행 중인 것을 위에 보여주고,
     하나 끝날 때마다 목록을 다시 불러와 새 옷이 바로 보이게 한다. */
  const jobs = useUploadJobs();
  const completed = useUploadCompleted();
  const running = jobs.filter((j) => j.phase !== 'failed');
  const failed = jobs.filter((j) => j.phase === 'failed');

  const batchTotal = useBatchTotal();
  const batchCompleted = useBatchCompletedCount();

  const seenCompleted = useRef(completed);
  useEffect(() => {
    if (completed === seenCompleted.current) return;
    seenCompleted.current = completed;
    reload();
    toast('옷장에 추가됐어요', { variant: 'success' });
  }, [completed, reload, toast]);

  const myItems = useMemo<Card[]>(
    () =>
      apiItems.map((i) => ({
        id: i.id,
        name: itemDisplayName(i),
        category: i.category_large,
        image: i.image_url,
      })),
    [apiItems],
  );

  const sharedSource = sharedSpace ? sharedItems : [];
  const source = tab === 'mine' ? myItems : sharedSource;
  const items = useMemo(
    () => source.filter((i) => matches(i.category) && matchesQuery(i, query)),
    [source, matches, query],
  );

  const loadRoomData = async (roomId: string, currentRoomsList?: any[]) => {
    try {
      const [membersList, itemsList] = await Promise.all([
        listSharedRoomMembers(roomId),
        listSharedRoomItems(roomId),
      ]);
      const memberNames = membersList.map((m) =>
        m.user.username === 'dev_autologin' ? '나' : m.user.username
      );
      const targetRoom = (currentRoomsList || sharedRooms).find((r) => r.id === roomId);
      setSharedSpace({
        id: roomId,
        name: targetRoom?.title || '공유 옷장',
        inviteCode: targetRoom?.invite_code || '',
        members: memberNames,
      });
      setSharedItems(
        itemsList.map((si) => ({
          id: si.id,
          name: si.wardrobe_item.item_name || '옷',
          category: si.wardrobe_item.category_large,
          image: si.wardrobe_item.image_url,
          owner: si.registered_by?.username === 'dev_autologin' ? '나' : si.registered_by?.username || undefined,
        }))
      );
    } catch (err) {
      console.error('공유방 세부 정보 로드 실패:', err);
    }
  };

  // 첫 마운트 또는 로그인 상태 변경 시 내 공유 옷장 방 로드
  useEffect(() => {
    if (isLoggedIn && tab === 'shared') {
      getMySharedRooms()
        .then(async (rooms) => {
          setSharedRooms(rooms || []);
          if (rooms && rooms.length > 0) {
            const selectedId =
              sharedSpace?.id && rooms.some((r) => r.id === sharedSpace.id)
                ? sharedSpace.id
                : rooms[0].id;
            await loadRoomData(selectedId, rooms);
          } else {
            setSharedSpace(null);
            setSharedItems([]);
          }
        })
        .catch(() => {
          setSharedRooms([]);
          setSharedSpace(null);
          setSharedItems([]);
        });
    }
  }, [isLoggedIn, tab]);

  const handleCreateSpace = async () => {
    let title = '공유 옷장';
    if (Platform.OS === 'web') {
      const input = window.prompt('새로운 공유 옷장의 이름을 입력해주세요:', '공유 옷장');
      if (input === null) return; // 취소 누른 경우
      if (input.trim()) {
        title = input.trim();
      }
    }
    try {
      const room = await createSharedRoom(title);
      toast(`'${title}'을 만들었어요`, { variant: 'success' });
      const rooms = await getMySharedRooms();
      setSharedRooms(rooms || []);
      await loadRoomData(room.id, rooms);
      setInviteOpen(true);
    } catch (err) {
      console.error('공유 옷장 개설 실패:', err);
      toast(err instanceof Error ? err.message : '공유 옷장 개설에 실패했습니다', { variant: 'error' });
    }
  };

  const handleRenameSpace = async (roomId: string, currentTitle: string) => {
    if (Platform.OS === 'web') {
      const input = window.prompt('수정할 공유 옷장의 이름을 입력해주세요:', currentTitle);
      if (input === null) return; // 취소 누른 경우
      const newTitle = input.trim();
      if (newTitle && newTitle !== currentTitle) {
        try {
          await renameSharedRoom(roomId, newTitle);
          toast('옷장 이름을 수정했어요', { variant: 'success' });
          const rooms = await getMySharedRooms();
          setSharedRooms(rooms || []);
          if (sharedSpace?.id === roomId) {
            setSharedSpace((prev) => (prev ? { ...prev, name: newTitle } : null));
          }
        } catch (err) {
          console.error('공유 옷장 이름 수정 실패:', err);
          toast('이름을 수정하지 못했습니다.', { variant: 'error' });
        }
      }
    }
  };

  const handleJoinSpace = async (code: string) => {
    try {
      const res = await joinSharedRoom(code);
      toast('공유 옷장에 참여했어요', { variant: 'success' });
      const rooms = await getMySharedRooms();
      setSharedRooms(rooms || []);
      await loadRoomData(res.room_id, rooms);
      return true;
    } catch (err) {
      console.error('공유 옷장 참여 실패:', err);
      toast(err instanceof Error ? err.message : '유효하지 않거나 만료된 초대 코드입니다', { variant: 'error' });
      return false;
    }
  };

  const emptyTitle = useMemo(() => {
    if (query.trim()) return `'${query.trim()}' 검색 결과가 없어요`;
    if (label !== '전체') return `'${label}' 결과가 없어요`;
    return tab === 'shared' ? '공유 옷장이 비어있어요' : '옷장이 비어있어요';
  }, [query, label, tab]);

  const emptyDescription = useMemo(() => {
    if (query.trim() || label !== '전체') {
      return '다른 검색어나 카테고리를 선택해 보세요.';
    }
    return tab === 'shared'
      ? '멤버가 옷을 추가하면 여기에 표시돼요.'
      : '첫 아이템을 추가해 옷장을 채워보세요.';
  }, [query, label, tab]);

  const handleTabChange = (key: 'mine' | 'shared') => {
    setTab(key);
    reset();
    setQuery('');
  };

  const handleSaveCategories = (next: string[]) => {
    setCategories(next);
    prune(next.slice(1));
  };

  const wardrobeToggle = (
    <SegmentedToggle
      value={tab}
      options={[
        { value: 'mine', label: '내 옷장' },
        { value: 'shared', label: '공유 옷장' },
      ]}
      onChange={handleTabChange}
    />
  );

  const showAddFab = tab === 'mine';

  // 옷장은 내 데이터라 비회원에게 보여줄 것이 없다. (훅 순서 유지를 위해 전부 호출한 뒤 분기)
  if (!isLoggedIn) {
    return (
      <LoginGate
        title="옷장은 로그인하고 쓸 수 있어요"
        body="내 옷을 등록해 두면 가진 옷 안에서 추천을 만들어요."
      />
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={styles.filterArea}>
          <SearchFilterBar
            trailing={wardrobeToggle}
            showFilters={!(tab === 'shared' && !sharedSpace)}
            query={query}
            onQueryChange={setQuery}
            searchPlaceholder="옷장에서 검색"
            options={categories}
            onToggle={toggle}
            isActive={isActive}
            onEditCategories={() => setEditOpen(true)}
          />
        </View>

        {/* 등록 진행 — 화면을 닫아도 계속 도는 작업의 상태 */}
        {tab === 'mine' && running.length > 0 ? (
          <View style={[styles.jobStrip, contentStyle(ContentMax.wide)]}>
            <ActivityIndicator color={INK} size="small" />
            <Text style={styles.jobText}>
              {batchTotal > 0
                ? `옷장 분석중 (${batchCompleted}/${batchTotal})`
                : `옷 등록 중 · ${running.length}장`}
            </Text>
          </View>
        ) : null}
        {tab === 'mine'
          ? failed.map((j) => (
              <View key={j.key} style={[styles.jobStrip, styles.jobStripFail, contentStyle(ContentMax.wide)]}>
                <Icon name="exclamationmark.triangle" tintColor={Editorial.danger} size={15} />
                <Text style={[styles.jobText, styles.jobTextFail]} numberOfLines={2}>
                  {j.error}
                </Text>
                <Pressable hitSlop={10} onPress={() => uploadJobs.dismiss(j.key)} accessibilityLabel="닫기">
                  <Icon name="xmark" tintColor={ink(0.45)} size={14} />
                </Pressable>
              </View>
            ))
          : null}

        {tab === 'shared' && sharedRooms.length > 0 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.roomTabsScroll}
            contentContainerStyle={styles.roomTabsContainer}
          >
            {sharedRooms.map((room) => {
              const isSelected = room.id === sharedSpace?.id;
              return (
                <Pressable
                  key={room.id}
                  style={[
                    styles.roomTab,
                    isSelected && styles.roomTabActive,
                    { flexDirection: 'row', alignItems: 'center' }
                  ]}
                  onPress={() => loadRoomData(room.id)}
                  onLongPress={() => handleRenameSpace(room.id, room.title)}
                >
                  <Text style={[styles.roomTabText, isSelected && styles.roomTabTextActive]}>
                    {room.title}
                  </Text>
                  {isSelected && (
                    <Pressable
                      hitSlop={8}
                      style={{ marginLeft: 6 }}
                      onPress={() => handleRenameSpace(room.id, room.title)}
                    >
                      <Icon name="pencil" tintColor="#FFFFFF" size={12} />
                    </Pressable>
                  )}
                </Pressable>
              );
            })}
            <Pressable
              style={[styles.roomTab, styles.roomTabAdd]}
              onPress={handleCreateSpace}
            >
              <Icon name="plus" tintColor={ink(0.6)} size={12} />
              <Text style={[styles.roomTabText, { marginLeft: 4, color: ink(0.6) }]}>
                새 옷장
              </Text>
            </Pressable>
          </ScrollView>
        ) : null}

        {tab === 'shared' && sharedSpace ? (
          <>
            <SharedSpaceMembers space={sharedSpace} onInvite={() => setInviteOpen(true)} />
            {sharedSpace.members.length <= 1 ? (
              <SharedSpaceInviteBanner onInvite={() => setInviteOpen(true)} />
            ) : null}
          </>
        ) : null}

        {tab === 'shared' && !sharedSpace ? (
          <View style={styles.onboardingWrap}>
            <SharedSpaceOnboarding
              onCreate={handleCreateSpace}
              onJoin={() => setJoinOpen(true)}
            />
          </View>
        ) : (
          <ScrollView
            style={styles.gridScroll}
            showsVerticalScrollIndicator={false}
            /* 공유 옷장은 아직 목업이라 다시 불러올 것이 없다 — 내 옷장에서만 당길 수 있게 둔다. */
            refreshControl={
              tab === 'mine' && isLoggedIn ? (
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={INK} />
              ) : undefined
            }
            contentContainerStyle={[styles.grid, { paddingBottom: tabInset + 24 }, contentStyle(ContentMax.wide)]}>
            {/* 내 옷장만 서버에서 온다 — 공유 옷장은 아직 목업이라 로딩·에러가 없다. */}
            {tab === 'mine' && loading ? (
              <LoadingState message="옷장을 불러오는 중…" style={styles.empty} />
            ) : tab === 'mine' && error ? (
              <ErrorState
                title="옷장을 불러오지 못했어요"
                description={error}
                onRetry={reload}
                style={styles.empty}
              />
            ) : items.length === 0 ? (
              <EmptyState
                icon={tab === 'shared' ? 'person' : 'tshirt'}
                title={emptyTitle}
                description={emptyDescription}
                actionLabel={
                  tab === 'mine' && !query.trim() && label === '전체'
                    ? '아이템 추가하기'
                    : tab === 'shared' && sharedSpace && !query.trim() && label === '전체'
                      ? '친구 초대하기'
                      : undefined
                }
                onAction={
                  tab === 'mine' && !query.trim() && label === '전체'
                    ? () => setSourceOpen(true)
                    : tab === 'shared' && sharedSpace && !query.trim() && label === '전체'
                      ? () => setInviteOpen(true)
                      : undefined
                }
                style={styles.empty}
              />
            ) : (
              items.map((it) => (
                <Pressable
                  key={it.id}
                  style={[styles.card, { width: cardW }]}
                  onPress={() =>
                    router.push({ pathname: '/item-detail', params: { id: it.id } })
                  }
                  // Web HTML5 Drag and drop
                  draggable={true}
                  onDragStart={(e: any) => {
                    if (Platform.OS === 'web') {
                      e.dataTransfer.setData('text/plain', JSON.stringify({
                        id: it.id,
                        name: it.name || it.category_large,
                        image: it.image
                      }));
                    }
                  }}>
                  <View style={[styles.cardImage, { height: cardH }]}>
                    <SmartImage
                      uri={it.image}
                      width="100%"
                      height={cardH}
                      radius={GridCard.radius}
                      contentFit="cover"
                    />
                     {it.owner ? (
                      <View style={[
                        styles.ownerBadge,
                        {
                          backgroundColor:
                            sharedSpace
                              ? MEMBER_COLORS[sharedSpace.members.indexOf(it.owner) % MEMBER_COLORS.length] || Editorial.ink
                              : Editorial.ink
                        }
                      ]}>
                        <Text style={[
                          styles.ownerText,
                          sharedSpace && sharedSpace.members.indexOf(it.owner) === 0 && { color: '#1C1917' }
                        ]}>{it.owner}님</Text>
                      </View>
                    ) : null}
                  </View>
                  <View style={styles.cardMeta}>
                    <Text style={styles.cardName} numberOfLines={1}>{it.name}</Text>
                    <Text style={styles.cardCat}>{it.category}</Text>
                  </View>
                </Pressable>
              ))
            )}
          </ScrollView>
        )}

        {sharedSpace ? (
          <SharedSpaceInviteSheet
            space={sharedSpace}
            visible={inviteOpen}
            onClose={() => setInviteOpen(false)}
          />
        ) : null}
        <SharedSpaceJoinSheet
          visible={joinOpen}
          onClose={() => setJoinOpen(false)}
          onJoin={handleJoinSpace}
        />
        <PhotoSourceSheet visible={sourceOpen} onClose={() => setSourceOpen(false)} />

        <CategoryEditSheet
          visible={editOpen}
          title="카테고리 관리"
          categories={categories}
          onClose={() => setEditOpen(false)}
          onSave={handleSaveCategories}
        />

        {showAddFab ? (
          <Pressable
            style={[styles.addFab, { bottom: tabInset + 12 }]}
            onPress={() => setSourceOpen(true)}
            accessibilityLabel="아이템 추가">
            <Icon name="plus" tintColor={INK} size={22} />
          </Pressable>
        ) : null}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },

  filterArea: { marginTop: 30 },

  jobStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginHorizontal: PAD,
    marginBottom: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: Editorial.control,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  jobStripFail: { backgroundColor: Editorial.surface },
  jobText: { flex: 1, fontSize: 13, color: Editorial.textCaption, fontWeight: '500' },
  jobTextFail: { color: Editorial.ink },

  gridScroll: { flex: 1, marginTop: 8 },
  onboardingWrap: { flex: 1, paddingHorizontal: PAD, paddingTop: 8 },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    /* space-between 으로 두면 마지막 줄의 카드가 양 끝으로 밀려 가운데가 빈다.
       왼쪽부터 차례로 채우고 간격은 columnGap 으로 준다. */
    justifyContent: 'flex-start',
    columnGap: GridCard.gap,
    paddingHorizontal: PAD,
  },
  // width/height 는 창 폭에서 파생되므로 컴포넌트에서 인라인으로 덧붙인다.
  card: { marginBottom: 16 },
  cardImage: {
    width: '100%',
    borderRadius: GridCard.radius,
    overflow: 'hidden',
  },
  ownerBadge: {
    position: 'absolute',
    top: 10,
    left: 10,
    backgroundColor: INK,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 999,
  },
  ownerText: { fontSize: 11, fontWeight: '600', color: '#fff' },
  cardMeta: {
    flexDirection: 'row',
    alignItems: 'baseline',
    /* 분류는 이름에 이어 붙인다. space-between 으로 두면 카드 오른쪽 끝으로 밀려
       이름과 멀어져 한 덩어리로 읽히지 않는다. */
    justifyContent: 'flex-start',
    gap: 6,
    marginTop: 8,
  },
  // flex:1 이면 이름이 남는 폭을 다 차지해 분류를 끝으로 밀어낸다 → 글자 길이만큼만.
  cardName: { flexShrink: 1, fontSize: 14, fontWeight: '500', color: Editorial.ink },
  cardCat: { fontSize: 12, color: Editorial.textCaption, flexShrink: 0 },

  empty: { width: '100%', paddingTop: 40 },

  addFab: {
    position: 'absolute',
    right: PAD,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Editorial.surface,
    borderWidth: 1.5,
    borderColor: ink(0.16),
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: INK,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.12,
    shadowRadius: 14,
    elevation: 8,
  },

  // ── 공유방 가로 탭 스타일 ──
  roomTabsScroll: {
    marginVertical: 12,
    maxHeight: 40,
    minHeight: 40,
  },
  roomTabsContainer: {
    paddingHorizontal: PAD,
    gap: 8,
    alignItems: 'center',
  },
  roomTab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: '#F3F4F6',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  roomTabActive: {
    backgroundColor: INK,
    borderColor: INK,
  },
  roomTabAdd: {
    flexDirection: 'row',
    alignItems: 'center',
    borderStyle: 'dashed',
    borderColor: ink(0.3),
    backgroundColor: 'transparent',
  },
  roomTabText: {
    fontSize: 13,
    fontWeight: '600',
    color: ink(0.6),
  },
  roomTabTextActive: {
    color: '#FFFFFF',
  },
});
