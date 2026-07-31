import { CategoryEditSheet, SearchFilterBar, SegmentedToggle, SmartImage, useToast } from '@/components/ui';
import { Icon } from '@/components/icon';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import {
  LOOKBOOK_FILTER_OPTIONS,
  useLookbook,
  type LookPost,
} from '@/state/lookbook';
import { likesStore, matchScore, tagScores, topKeys, useLikedLooks } from '@/state/likes';
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

/** 상단 세그먼트: 둘러보기(남들이 올린 피드) / 저장됨(내가 저장한 룩) */
type Mode = 'browse' | 'saved';
const MODE_OPTIONS: { value: Mode; label: string }[] = [
  { value: 'browse', label: '둘러보기' },
  { value: 'saved', label: '저장됨' },
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
const RAIL_CARD_W = 116;

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
  const toast = useToast();

  // 홈 '저장' 등에서 ?tab=saved 로 진입하면 저장됨 탭이 열린다.
  // 모드는 URL 파라미터에서 파생하고, 세그먼트 전환은 setParams 로 파라미터를 바꾼다
  // (useState+useEffect 동기화는 불필요한 리렌더를 만들어 지양).
  const { tab } = useLocalSearchParams<{ tab?: string }>();
  const mode: Mode = tab === 'saved' ? 'saved' : 'browse';
  const setMode = (m: Mode) => router.setParams({ tab: m });

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

  const cards: CardData[] =
    mode === 'browse'
      ? feedLooks.map((l) => ({ id: l.id, uri: l.image, price: l.price, tags: l.tags, variantId: l.variantId }))
      : savedFiltered.map((l) => ({ id: l.id, uri: l.image, asset: l.asset }));

  /* ── 취향 추천 ──
     좋아요한 룩의 태그와 겹치는 **아직 안 누른** 룩을 골라 목록 위에 따로 보여준다.
     본 그리드를 재정렬하지 않는 이유: 하트를 누를 때마다 카드가 자리를 옮기면
     방금 뭘 눌렀는지 놓친다. 추천은 추천대로 한 줄에 모아 두고 그리드는 그대로 둔다. */
  const likedIds = useMemo(() => new Set(likedLooks.map((l) => l.id)), [likedLooks]);
  const scores = useMemo(() => tagScores(likedLooks), [likedLooks]);
  const likedTags = useMemo(() => topKeys(scores, 2), [scores]);
  const picks: LookPost[] = useMemo(() => {
    if (likedTags.length === 0) return [];
    return allLooks
      .filter((l) => !likedIds.has(l.id))
      .map((l) => ({ look: l, score: matchScore(l.tags, scores) }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map((x) => x.look);
  }, [allLooks, scores, likedTags, likedIds]);
  /* 검색·필터 중에는 숨긴다. 사용자가 직접 좁혀 놓은 결과 위에 우리가 고른 것을 얹으면
     필터가 안 먹은 것처럼 보인다. */
  const showPicks = mode === 'browse' && picks.length > 0 && !query.trim() && selected.length === 0;

  const toggleLike = (look: { id: string; image?: string; tags?: string[] }) => {
    const liked = likesStore.toggleLook(look);
    toast(liked ? '좋아요 — 비슷한 룩을 더 보여드릴게요' : '좋아요를 취소했어요');
  };

  const emptyText = useMemo(() => {
    if (query.trim()) return `'${query.trim()}' 검색 결과가 없어요`;
    if (mode === 'saved') return '아직 저장한 룩이 없어요';
    if (label !== '전체') return `'${label}' 태그 룩이 없어요`;
    return '아직 올린 룩이 없어요';
  }, [mode, query, label]);

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
        </View>

        <ScrollView
          style={styles.gridScroll}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.grid, { paddingBottom: tabInset + 24 }, contentStyle(ContentMax.wide)]}>
          {showPicks ? (
            <View style={styles.rail}>
              <Text style={styles.railTitle}>취향 추천</Text>
              <Text style={styles.railHint}>
                {likedTags.map((t) => `#${t}`).join(' ')} 좋아요를 눌러서 골랐어요
              </Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.railRow}>
                {picks.map((p) => (
                  <Pressable
                    key={p.id}
                    style={styles.railCard}
                    onPress={() => router.push(`/look-detail?id=${p.variantId ?? 'daily'}`)}>
                    <SmartImage
                      uri={p.image}
                      width={RAIL_CARD_W}
                      height={RAIL_CARD_W * 1.25}
                      radius={12}
                      contentFit="cover"
                    />
                    <Text style={styles.railTags} numberOfLines={1}>
                      {p.tags.map((t) => `#${t}`).join(' ')}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          ) : null}

          {cards.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>{emptyText}</Text>
              {mode === 'browse' ? (
                <Pressable style={styles.emptyBtn} onPress={() => router.push('/look-add')}>
                  <Text style={styles.emptyBtnText}>첫 룩 올리기</Text>
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
                    mode === 'saved'
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
  rail: { width: '100%', marginBottom: 18 },
  railTitle: { fontSize: 14, fontWeight: '600', color: INK },
  railHint: { fontSize: 12, color: Editorial.textCaption, marginTop: 3 },
  railRow: { gap: 10, paddingTop: 10, paddingRight: PAD },
  railCard: { width: RAIL_CARD_W, gap: 6 },
  railTags: { fontSize: 11, color: Editorial.textCaption },

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
