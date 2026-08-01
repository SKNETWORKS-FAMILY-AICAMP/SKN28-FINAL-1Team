import { CategoryEditSheet, SearchFilterBar, SegmentedToggle, SmartImage, useToast } from '@/components/ui';
import { Icon } from '@/components/icon';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import { LOOKBOOK_FILTER_OPTIONS, useLookbook } from '@/state/lookbook';
import { likesStore, useLikedLooks } from '@/state/likes';
import { useSavedLooks } from '@/state/saved';
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, GridCard, gridCardImageHeight, gridCardWidth , ContentMax} from '@/constants/theme';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = Editorial.ink;

/* 카드 크기는 창 폭에서 파생 → 컴포넌트 안에서 useBreakpoint() 로 구한다. */
const PAD = GridCard.pad;
const DEFAULT_TAGS = [...LOOKBOOK_FILTER_OPTIONS];

/**
 * 상단 세그먼트: 둘러보기(남들이 올린 피드) / 내 룩북(내가 모은 것).
 * 저장·좋아요를 세그먼트에 나란히 세우지 않는 이유: 갈림길은 '남의 룩이냐 내 것이냐' 하나이고,
 * 저장과 좋아요는 둘 다 내 것이라 그 아래 층이다. 셋을 한 줄에 두면 검색행도 좁아진다.
 */
type Mode = 'browse' | 'mine';
const MODE_OPTIONS: { value: Mode; label: string }[] = [
  { value: 'browse', label: '둘러보기' },
  { value: 'mine', label: '내 룩북' },
];

/** '내 룩북' 안의 갈래 — 저장(내가 담아둔 룩) / 좋아요(피드에서 하트 누른 룩) */
type MineTab = 'saved' | 'liked';
const MINE_TABS: { value: MineTab; label: string }[] = [
  { value: 'saved', label: '저장됨' },
  { value: 'liked', label: '좋아요' },
];

/** 그리드 카드 공통 형태 — 피드 룩(price 有)·저장 룩(asset 有) 모두 이 형태로 정규화 */
type CardData = {
  id: string;
  uri?: string;
  asset?: number;
  price?: string;
  /** 좋아요 대상은 피드 룩뿐이다. 저장 룩은 이미 내 것이라 하트를 달지 않는다. */
  tags?: string[];
  /** 피드 룩이 가리키는 룩 상세 */
  variantId?: string;
};

/** 취향 추천 가로 카드 크기 — 그리드보다 작게 잡아 본 목록을 밀어내지 않는다. */

function matchesQuery(look: { tags: string[] }, query: string): boolean {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return true;
  return look.tags.some((tag) => tag.toLocaleLowerCase().includes(q));
}

function matchesTags(look: { tags: string[] }, selected: string[]): boolean {
  if (selected.length === 0) return true;
  return look.tags.some((tag) => selected.includes(tag));
}

export default function LookbookScreen() {
  const { frameWidth, contentStyle } = useBreakpoint();
  const cardW = gridCardWidth(frameWidth);
  const cardH = gridCardImageHeight(cardW);
  const tabInset = useBottomTabInset();

  const allLooks = useLookbook();
  const savedLooks = useSavedLooks();
  const likedLooks = useLikedLooks();

  // 홈 '저장' 등에서 ?tab=saved 로 진입하면 저장됨 탭이 열린다.
  // 모드는 URL 파라미터에서 파생하고, 세그먼트 전환은 setParams 로 파라미터를 바꾼다
  // (useState+useEffect 동기화는 불필요한 리렌더를 만들어 지양).
  const { tab } = useLocalSearchParams<{ tab?: string }>();
  const mode: Mode = tab === 'saved' || tab === 'liked' ? 'mine' : 'browse';
  const mineTab: MineTab = tab === 'liked' ? 'liked' : 'saved';
  /* '내 룩북'으로 갈 때는 저장됨부터 연다. 홈의 ?tab=saved 링크도 그대로 살아 있다. */
  const setMode = (m: Mode) => router.setParams({ tab: m === 'mine' ? 'saved' : 'browse' });
  const setMineTab = (t: MineTab) => router.setParams({ tab: t });

  const [query, setQuery] = useState('');
  const [tags, setTags] = useState(DEFAULT_TAGS);
  const [editOpen, setEditOpen] = useState(false);
  const { toggle, isActive, selected, label, prune } = useMultiSelectFilter();

  const feedLooks = useMemo(
    () => allLooks.filter((l) => matchesTags(l, selected) && matchesQuery(l, query)),
    [allLooks, selected, query],
  );
  const savedFiltered = useMemo(
    () => savedLooks.filter((l) => matchesQuery(l, query)),
    [savedLooks, query],
  );

  /* 좋아요한 룩은 피드 룩이라 상세로 보내려면 variantId 가 필요하다 → 피드에서 다시 찾는다.
     피드에서 내려간 룩이면 기본 룩으로 떨어뜨린다. */
  const likedCards: CardData[] = useMemo(
    () =>
      likedLooks
        .filter((l) => matchesQuery({ tags: l.tags }, query))
        .map((l) => ({
          id: l.id,
          uri: l.image,
          tags: l.tags,
          variantId: allLooks.find((f) => f.id === l.id)?.variantId,
        })),
    [likedLooks, allLooks, query],
  );

  const cards: CardData[] =
    mode === 'browse'
      ? feedLooks.map((l) => ({ id: l.id, uri: l.image, price: l.price, tags: l.tags, variantId: l.variantId }))
      : mineTab === 'liked'
        ? likedCards
        : savedFiltered.map((l) => ({ id: l.id, uri: l.image, asset: l.asset }));

  const toast = useToast();
  const likedIds = useMemo(() => new Set(likedLooks.map((l) => l.id)), [likedLooks]);
  const toggleLike = (look: { id: string; image?: string; tags?: string[] }) => {
    const liked = likesStore.toggleLook(look);
    toast(liked ? '좋아요 — 취향에 반영할게요' : '좋아요를 취소했어요');
  };

  const emptyText = useMemo(() => {
    if (query.trim()) return `'${query.trim()}' 검색 결과가 없어요`;
    if (mode === 'mine') {
      return mineTab === 'liked' ? '아직 좋아요한 룩이 없어요' : '아직 저장한 룩이 없어요';
    }
    if (label !== '전체') return `'${label}' 태그 룩이 없어요`;
    return '아직 올린 룩이 없어요';
  }, [mode, mineTab, query, label]);

  const handleSaveTags = (next: string[]) => {
    setTags(next);
    prune(next.slice(1));
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={styles.filterArea}>
          <SearchFilterBar
            query={query}
            onQueryChange={setQuery}
            searchPlaceholder="해시태그 검색"
            options={tags}
            onToggle={toggle}
            isActive={isActive}
            showChips={mode === 'browse'}
            onEditCategories={mode === 'browse' ? () => setEditOpen(true) : undefined}
            trailing={
              <SegmentedToggle value={mode} options={MODE_OPTIONS} onChange={setMode} />
            }
          />
          {/* 해시태그 칩이 비는 자리에 '내 룩북'의 갈래를 놓는다 — 줄이 새로 생기지 않는다 */}
          {mode === 'mine' ? (
            <View style={styles.mineTabs}>
              {MINE_TABS.map((t) => {
                const on = t.value === mineTab;
                const count = t.value === 'liked' ? likedLooks.length : savedLooks.length;
                return (
                  <Pressable
                    key={t.value}
                    style={[styles.mineChip, on && styles.mineChipOn]}
                    onPress={() => setMineTab(t.value)}>
                    <Text style={[styles.mineChipText, on && styles.mineChipTextOn]}>
                      {t.label}
                      {count > 0 ? ` ${count}` : ''}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}
        </View>

        <ScrollView
          style={styles.gridScroll}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.grid, { paddingBottom: tabInset + 24 }, contentStyle(ContentMax.wide)]}>
          {cards.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>{emptyText}</Text>
              {mode === 'browse' ? (
                <Pressable style={styles.emptyBtn} onPress={() => router.push('/look-add')}>
                  <Text style={styles.emptyBtnText}>첫 룩 올리기</Text>
                </Pressable>
              ) : mineTab === 'liked' ? (
                <Pressable style={styles.emptyBtn} onPress={() => setMode('browse')}>
                  <Text style={styles.emptyBtnText}>둘러보며 마음에 드는 룩 찾기</Text>
                </Pressable>
              ) : (
                <Pressable style={styles.emptyBtn} onPress={() => router.push('/(tabs)/home')}>
                  <Text style={styles.emptyBtnText}>오늘의 룩 저장하러 가기</Text>
                </Pressable>
              )}
            </View>
          ) : (
            cards.map((c) => (
              <Pressable
                key={c.id}
                style={[styles.card, { width: cardW }]}
                /* 저장 룩은 저장 상세로, 피드 룩은 그 룩의 추천 상세로 보낸다.
                   둘 다 어느 것을 눌렀는지 id 로 넘긴다. */
                onPress={() =>
                  router.push(
                    mode === 'mine' && mineTab === 'saved'
                      ? `/saved-look?id=${c.id}`
                      : `/look-detail?id=${c.variantId ?? 'daily'}`,
                  )
                }>
                <View style={[styles.cardImage, { height: cardH }]}>
                  <SmartImage
                    uri={c.uri}
                    asset={c.uri ? undefined : c.asset}
                    width="100%"
                    height={cardH}
                    radius={GridCard.radius}
                    contentFit="cover"
                  />
                  {c.price ? (
                    <View style={styles.priceBadge}>
                      <Text style={styles.priceText}>{c.price}</Text>
                    </View>
                  ) : null}
                  {/* 좋아요 — 피드 룩에만. 저장 룩은 이미 내 것이라 누를 대상이 아니다. */}
                  {c.tags ? (
                    <Pressable
                      style={styles.likeBtn}
                      hitSlop={8}
                      accessibilityLabel={likedIds.has(c.id) ? '좋아요 취소' : '좋아요'}
                      onPress={() => toggleLike({ id: c.id, image: c.uri, tags: c.tags })}>
                      <Icon
                        name={likedIds.has(c.id) ? 'heart.fill' : 'heart'}
                        tintColor={likedIds.has(c.id) ? Editorial.wine : INK}
                        size={17}
                      />
                    </Pressable>
                  ) : null}
                </View>
              </Pressable>
            ))
          )}
        </ScrollView>

        <CategoryEditSheet
          visible={editOpen}
          title="태그 관리"
          categories={tags}
          addPlaceholder="새 태그"
          onClose={() => setEditOpen(false)}
          onSave={handleSaveTags}
        />

        {mode === 'browse' ? (
          <Pressable
            style={[styles.addFab, { bottom: tabInset + 12 }]}
            onPress={() => router.push('/look-add')}
            accessibilityLabel="룩 올리기">
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
  card: { marginBottom: 12 },
  cardImage: {
    width: '100%',
    borderRadius: GridCard.radius,
    overflow: 'hidden',
    justifyContent: 'flex-end',
  },
  priceBadge: {
    position: 'absolute',
    left: 12,
    bottom: 12,
    backgroundColor: 'rgba(255,255,255,0.95)',
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: 999,
  },
  priceText: { fontSize: 12, fontWeight: '700', color: INK },
  /* 검색행 바로 아래 — 해시태그 칩과 같은 크기·간격이라 자리가 튀지 않는다 */
  mineTabs: { flexDirection: 'row', gap: 8, paddingHorizontal: PAD, paddingBottom: 20 },
  mineChip: {
    height: 36,
    paddingHorizontal: 15,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.12),
    alignItems: 'center',
    justifyContent: 'center',
  },
  mineChipOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  mineChipText: { fontSize: 13, lineHeight: 18, color: Editorial.textCaption, fontWeight: '500' },
  mineChipTextOn: { color: '#fff' },

  likeBtn: {
    position: 'absolute',
    top: 10,
    right: 10,
    width: 30,
    height: 30,
    borderRadius: 15,
    /* 사진 위에 얹히므로 밝은 사진에서도 하트가 보이게 흰 판을 깐다. */
    backgroundColor: 'rgba(255,255,255,0.92)',
    alignItems: 'center',
    justifyContent: 'center',
  },

  // 취향 추천 — 그리드(row wrap) 안에 끼므로 한 줄을 통째로 차지하게 100% 로 둔다.

  empty: { width: '100%', alignItems: 'center', paddingTop: 60, gap: 16 },
  emptyText: { fontSize: 13, color: Editorial.textCaption },
  emptyBtn: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
  },
  emptyBtnText: { fontSize: 13, fontWeight: '600', color: '#fff' },

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
});
