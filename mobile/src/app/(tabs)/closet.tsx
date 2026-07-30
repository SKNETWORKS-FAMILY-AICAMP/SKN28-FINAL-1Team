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
import { CategoryEditSheet, EmptyState, LoginGate, SearchFilterBar, SegmentedToggle, SmartImage, useToast } from '@/components/ui';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, BottomTabInset, GridCard, gridCardImageHeight, gridCardWidth , ContentMax} from '@/constants/theme';
import { CLOSET_ITEMS, SHARED_CLOSET_ITEMS, type WardrobeItem } from '@/constants/wardrobe';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { Icon } from '@/components/icon';
import { useAuth } from '@/state/auth';

const INK = Editorial.ink;

/* 카드 크기는 창 폭에서 파생되므로 모듈 최상단이 아니라 컴포넌트 안에서 useBreakpoint() 로 구한다.
   (모듈 최상단에서 읽으면 리사이즈에 반응하지 않는다) */
const PAD = GridCard.pad;

const DEFAULT_CATEGORIES = ['전체', '상의', '하의', '아우터', '신발', '가방', '액세서리'];

/* 옷 목록은 캘린더의 '옷 고르기' 시트와 공유한다 → @/constants/wardrobe 가 단일 출처 */
type Item = WardrobeItem;
const MY_ITEMS = CLOSET_ITEMS;
const SHARED_ITEMS = SHARED_CLOSET_ITEMS;

function matchesQuery(item: Item, query: string): boolean {
  const q = query.trim();
  if (!q) return true;
  return item.name.includes(q) || item.category.includes(q);
}

export default function ClosetScreen() {
  const { isLoggedIn } = useAuth();
  const { frameWidth, contentStyle } = useBreakpoint();
  const cardW = gridCardWidth(frameWidth);
  const cardH = gridCardImageHeight(cardW);

  const toast = useToast();
  const [tab, setTab] = useState<'mine' | 'shared'>('mine');
  const [query, setQuery] = useState('');
  const [sharedSpace, setSharedSpace] = useState<SharedSpace | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);
  const [categories, setCategories] = useState(DEFAULT_CATEGORIES);
  const [editOpen, setEditOpen] = useState(false);
  const { toggle, reset, prune, isActive, matches, label } = useMultiSelectFilter();

  const sharedSource =
    sharedSpace && sharedSpace.members.length > 1 ? SHARED_ITEMS : [];
  const source = tab === 'mine' ? MY_ITEMS : sharedSource;
  const items = useMemo(
    () => source.filter((i) => matches(i.category) && matchesQuery(i, query)),
    [source, matches, query],
  );

  const handleCreateSpace = () => {
    const space = createSharedSpace();
    setSharedSpace(space);
    setInviteOpen(true);
    toast('공유 옷장을 만들었어요', { variant: 'success' });
  };

  const handleJoinSpace = (code: string) => {
    const space = joinSharedSpace(code);
    if (!space) return false;
    setSharedSpace(space);
    return true;
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
            contentContainerStyle={[styles.grid, contentStyle(ContentMax.wide)]}>
            {items.length === 0 ? (
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
                    ? () => router.push('/item-add-source')
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
                  onPress={() => router.push('/item-detail')}>
                  <View style={[styles.cardImage, { height: cardH }]}>
                    <SmartImage
                      uri={it.image}
                      width="100%"
                      height={cardH}
                      radius={GridCard.radius}
                      contentFit="cover"
                    />
                    {it.owner ? (
                      <View style={styles.ownerBadge}>
                        <Text style={styles.ownerText}>{it.owner}님</Text>
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
        <CategoryEditSheet
          visible={editOpen}
          title="카테고리 관리"
          categories={categories}
          onClose={() => setEditOpen(false)}
          onSave={handleSaveCategories}
        />

        {showAddFab ? (
          <Pressable
            style={styles.addFab}
            onPress={() => router.push('/item-add-source')}
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
    paddingBottom: BottomTabInset + 24,
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
    bottom: BottomTabInset + 12,
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
});
