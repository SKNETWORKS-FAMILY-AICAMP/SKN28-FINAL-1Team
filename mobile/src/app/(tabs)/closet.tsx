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
import { CategoryEditSheet, EmptyState, InlineDropdown, SearchFilterBar, SmartImage, useToast } from '@/components/ui';
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

import { BottomTabInset, GridCard, gridCardImageHeight, gridCardWidth , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { Icon } from '@/components/icon';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

/* 카드 크기는 창 폭에서 파생되므로 모듈 최상단이 아니라 컴포넌트 안에서 useBreakpoint() 로 구한다.
   (모듈 최상단에서 읽으면 리사이즈에 반응하지 않는다) */
const PAD = GridCard.pad;

const DEFAULT_CATEGORIES = ['전체', '상의', '하의', '아우터', '신발', '가방', '액세서리'];

type Item = {
  id: string;
  name: string;
  category: string;
  tone: number;
  owner?: string;
  image?: string;
};

const MY_ITEMS: Item[] = [
  {
    id: '1',
    name: '니트 나시',
    category: '상의',
    tone: 0.05,
    image: 'https://i.pinimg.com/1200x/3e/04/ea/3e04eaa53146fd9bf93736707fffcb4f.jpg',
  },
  {
    id: '2',
    name: '아이보리 양털 후리스',
    category: '아우터',
    tone: 0.22,
    image: 'https://i.pinimg.com/736x/e1/d4/65/e1d465ce5c23d7bbe327e49748a00dfd.jpg',
  },
  {
    id: '3',
    name: '청바지',
    category: '하의',
    tone: 0.16,
    image: 'https://i.pinimg.com/1200x/94/f7/9c/94f79c0800d407561efe52cdcd9e9e7b.jpg',
  },
  {
    id: '4',
    name: '아디다스 스니커즈',
    category: '신발',
    tone: 0.24,
    image: 'https://i.pinimg.com/736x/6e/ce/fa/6ecefa13347d6487fc30c0fda287d4dd.jpg',
  },
  {
    id: '5',
    name: '치마',
    category: '하의',
    tone: 0.08,
    image: 'https://i.pinimg.com/736x/47/90/f8/4790f8a800508904136accba58a71984.jpg',
  },
  {
    id: '6',
    name: '블루 샤넬',
    category: '가방',
    tone: 0.3,
    image: 'https://i.pinimg.com/736x/7b/4c/a1/7b4ca14352231767be6da3369c8f406e.jpg',
  },
];

const SHARED_ITEMS: Item[] = [
  {
    id: 's1',
    name: '카멜 오버 코트',
    category: '아우터',
    tone: 0.12,
    owner: '지민',
    image: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400&h=500&fit=crop',
  },
  {
    id: 's2',
    name: '플리츠 미디 스커트',
    category: '하의',
    tone: 0.07,
    owner: '서연',
    image: 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=400&h=500&fit=crop',
  },
  {
    id: 's3',
    name: '체크 오버 셔츠',
    category: '상의',
    tone: 0.18,
    owner: '민준',
    image: 'https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=400&h=500&fit=crop',
  },
  {
    id: 's4',
    name: '스웨이드 첼시 부츠',
    category: '신발',
    tone: 0.26,
    owner: '지민',
    image: 'https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&h=500&fit=crop',
  },
  {
    id: 's5',
    name: '베이지 트렌치 코트',
    category: '아우터',
    tone: 0.1,
    owner: '서연',
    image: 'https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=400&h=500&fit=crop',
  },
  {
    id: 's6',
    name: '실버 체인 목걸이',
    category: '액세서리',
    tone: 0.14,
    owner: '민준',
    image: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400&h=500&fit=crop',
  },
];

function matchesQuery(item: Item, query: string): boolean {
  const q = query.trim();
  if (!q) return true;
  return item.name.includes(q) || item.category.includes(q);
}

export default function ClosetScreen() {
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

  const wardrobeDropdown = (
    <InlineDropdown
      compact
      value={tab}
      options={[
        { value: 'mine', label: '내 옷장' },
        { value: 'shared', label: '공유 옷장' },
      ]}
      onChange={handleTabChange}
    />
  );

  const showAddFab = tab === 'mine';

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={styles.filterArea}>
          <SearchFilterBar
            trailing={wardrobeDropdown}
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
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },

  filterArea: { marginTop: 30 },

  gridScroll: { flex: 1, marginTop: 8 },
  onboardingWrap: { flex: 1, paddingHorizontal: PAD, paddingTop: 8 },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
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
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    marginTop: 8,
  },
  cardName: { flex: 1, fontSize: 14, fontWeight: '500', color: ink(0.9) },
  cardCat: { fontSize: 12, color: ink(0.4), flexShrink: 0 },

  empty: { width: '100%', paddingTop: 40 },

  addFab: {
    position: 'absolute',
    right: PAD,
    bottom: BottomTabInset + 12,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#ffffff',
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
