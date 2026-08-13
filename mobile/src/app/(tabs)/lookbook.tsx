import {
  CategoryEditSheet,
  ErrorState,
  LoadingState,
  SearchFilterBar,
  SegmentedToggle,
  SmartImage,
} from '@/components/ui';
import { Icon, type IconName } from '@/components/icon';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import { useRefresh } from '@/hooks/use-refresh';
import { LOOKBOOK_FILTER_OPTIONS, lookbookStore, useLookbook } from '@/state/lookbook';
import { likesStore, useLikedLooks } from '@/state/likes';
import { savedLookStore, useSavedLooks, useSavedLooksState, type LookOrigin } from '@/state/saved';
import { router, useLocalSearchParams } from 'expo-router';
import { withReturn } from '@/lib/goBack';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, GridCard, gridCardImageHeight, gridCardWidth , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = Editorial.ink;

/* 카드 크기는 창 폭에서 파생 → 컴포넌트 안에서 useBreakpoint() 로 구한다. */
const PAD = GridCard.pad;
const DEFAULT_TAGS = [...LOOKBOOK_FILTER_OPTIONS];

/**
 * 상단 세그먼트: 둘러보기 / 내 룩북.
 *
 * - 둘러보기 = **모두가 보는 룩**. 앱이 기본으로 주는 룩과, 사용자가 전체공개한 룩이 여기 모인다.
 *   내가 담아둔 룩(위시)도 이 안의 카테고리 하나로 둔다 — 담는 대상이 결국 여기 있는 룩이라
 *   따로 떼어 두면 담으러 갔다가 보러 오는 왕복이 생긴다.
 * - 내 룩북 = **내가 올린 룩만**. 그래서 갈래도 카테고리도 없다. 목록이 곧 답이다.
 */
type Mode = 'browse' | 'mine';
const MODE_OPTIONS: { value: Mode; label: string }[] = [
  { value: 'browse', label: '둘러보기' },
  { value: 'mine', label: '내 룩북' },
];

/**
 * 둘러보기의 특별 카테고리 — 해시태그가 아니라 '내가 담아둔 것'이라는 갈래다.
 * 하트로 담은 룩과 추천에서 저장해 둔 룩이 여기서 한 목록이 된다.
 */
const WISH = '위시';
/* 위시 칩에만 하트를 단다 — 나머지는 해시태그라 성격이 다르고,
   카드 위 하트와 같은 표식이라 "하트 누른 것들"이라는 뜻이 바로 읽힌다. */
const CHIP_ICONS = { [WISH]: 'heart.fill' as const };

/** 그리드 카드 공통 형태 — 피드 룩(price 有)·저장 룩(asset 有) 모두 이 형태로 정규화 */
type CardData = {
  id: string;
  uri?: string;
  asset?: number;
  price?: string;
  /** 하트를 달 수 있는 룩(=피드 룩)에만 있다. 태그 검색의 대상이기도 하다. */
  tags?: string[];
  /** 피드 룩이 가리키는 룩 상세 */
  variantId?: string;
  /** 어느 상세로 보낼지 — 피드 룩은 추천 상세, 담아둔 룩은 저장 룩 상세 */
  kind: 'feed' | 'saved';
  /** 위시 목록에서만 쓰는 출처 표시. 추천에서 저장한 룩(✨)을 하트로 담은 룩과 가른다. */
  origin?: LookOrigin;
};

/** 출처 배지 — 아이콘만 둔다. 라벨을 붙이면 사진 위 면적을 그만큼 더 가린다. */
const ORIGIN_BADGE: Record<LookOrigin, { icon: IconName; label: string }> = {
  ai: { icon: 'sparkles', label: '앱이 추천한 룩' },
  closet: { icon: 'tshirt', label: '내가 기록한 룩' },
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

  const allLooks = useLookbook();
  const savedLooks = useSavedLooks();
  const likedLooks = useLikedLooks();

  /* 둘 다 서버에서 온다 — 내 룩북은 내 목록, 둘러보기는 공개 피드.
     세그먼트를 오갈 때마다 기다리게 하지 않으려고 화면에 들어올 때 함께 받는다. */
  const { loading, error, loaded } = useSavedLooksState();
  const loadAll = useCallback(
    () => Promise.all([savedLookStore.load(), lookbookStore.load()]).then(() => undefined),
    [],
  );
  const { refreshing, onRefresh } = useRefresh(loadAll);
  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  // 홈 '저장' 등에서 ?tab=saved 로 들어오던 링크가 아직 있어 'mine' 으로 함께 받는다.
  // 모드는 URL 파라미터에서 파생하고, 세그먼트 전환은 setParams 로 파라미터를 바꾼다
  // (useState+useEffect 동기화는 불필요한 리렌더를 만들어 지양).
  const { tab } = useLocalSearchParams<{ tab?: string }>();
  const mode: Mode = tab === 'mine' || tab === 'saved' ? 'mine' : 'browse';
  const setMode = (m: Mode) => router.setParams({ tab: m === 'mine' ? 'mine' : 'browse' });

  const [query, setQuery] = useState('');
  const [tags, setTags] = useState(DEFAULT_TAGS);
  const [editOpen, setEditOpen] = useState(false);
  const { toggle, isActive, selected, label, prune } = useMultiSelectFilter();

  /* 둘러보기 칩 = 전체 + 위시 + 해시태그. 위시는 사용자가 지울 수 없는 고정 칩이라
     태그 관리(tags)와 따로 두고 여기서만 끼워 넣는다. */
  const browseOptions = useMemo(() => [tags[0], WISH, ...tags.slice(1)], [tags]);
  const wishOn = selected.includes(WISH);
  /** 위시 칩을 뺀 해시태그 선택 — 위시 안에서도 태그로 더 좁힐 수 있다. */
  const tagSelection = useMemo(() => selected.filter((s) => s !== WISH), [selected]);

  /** 담아둔 룩 = 하트 누른 피드 룩 + 추천에서 저장해 둔 룩(✨). 최근에 담은 것이 앞에 온다. */
  const wishCards: CardData[] = useMemo(() => {
    const liked: CardData[] = likedLooks.map((l) => ({
      id: l.id,
      uri: l.image,
      tags: l.tags,
      /* 상세로 보내려면 variantId 가 필요하다 → 피드에서 다시 찾고, 내려간 룩이면 기본 룩으로. */
      variantId: allLooks.find((f) => f.id === l.id)?.variantId,
      kind: 'feed' as const,
    }));
    const savedAi: CardData[] = savedLooks
      .filter((l) => l.origin === 'ai')
      .map((l) => ({
        id: l.id,
        uri: l.image,
        asset: l.asset,
        tags: l.tags,
        origin: l.origin,
        kind: 'saved' as const,
      }));
    return [...liked, ...savedAi].filter(
      (c) => matchesTags({ tags: c.tags ?? [] }, tagSelection) && matchesQuery({ tags: c.tags ?? [] }, query),
    );
  }, [likedLooks, savedLooks, allLooks, tagSelection, query]);

  /** 내 룩북 = 내가 올린 룩만. 추천에서 저장한 룩(✨)은 위시로 갔다. */
  const mineCards: CardData[] = useMemo(
    () =>
      savedLooks
        .filter((l) => l.origin !== 'ai' && matchesQuery(l, query))
        .map((l) => ({ id: l.id, uri: l.image, asset: l.asset, kind: 'saved' as const })),
    [savedLooks, query],
  );

  const feedCards: CardData[] = useMemo(
    () =>
      allLooks
        .filter((l) => matchesTags(l, tagSelection) && matchesQuery(l, query))
        .map((l) => ({
          id: l.id,
          uri: l.image,
          price: l.price,
          tags: l.tags,
          variantId: l.variantId,
          kind: 'feed' as const,
        })),
    [allLooks, tagSelection, query],
  );

  const cards: CardData[] = mode === 'mine' ? mineCards : wishOn ? wishCards : feedCards;

  /** 서버에서 오는 목록을 보고 있는가 — 로딩·에러·당겨서 새로고침은 그때만 뜬다. */
  const usesServer = mode === 'mine' || wishOn;

  /* 상세에서 뒤로 왔을 때 보던 갈래로 돌아오게 한다(위시 칩은 화면 상태라 URL 에 없다 —
     여기서는 모드까지만 맞춰 준다). */
  const returnHere = mode === 'mine' ? '/(tabs)/lookbook?tab=mine' : '/(tabs)/lookbook';

  const likedIds = useMemo(() => new Set(likedLooks.map((l) => l.id)), [likedLooks]);
  /* 토스트를 띄우지 않는다 — 하트가 그 자리에서 바로 채워지고 비워져 결과가 이미 보인다. */
  const toggleLike = (look: { id: string; image?: string; tags?: string[] }) =>
    likesStore.toggleLook(look);

  const emptyText = useMemo(() => {
    if (query.trim()) return `'${query.trim()}' 검색 결과가 없어요`;
    if (mode === 'mine') return '아직 올린 룩이 없어요';
    if (wishOn) return tagSelection.length ? `'${label}' 담아둔 룩이 없어요` : '아직 담아둔 룩이 없어요';
    if (tagSelection.length) return `'${label}' 태그 룩이 없어요`;
    return '아직 올라온 룩이 없어요';
  }, [mode, wishOn, tagSelection, query, label]);

  const handleSaveTags = (next: string[]) => {
    setTags(next);
    /* 위시는 태그 목록에 없는 고정 칩이라, 태그를 정리해도 선택이 풀리면 안 된다. */
    prune([WISH, ...next.slice(1)]);
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={styles.filterArea}>
          {/* 내 룩북은 내가 올린 룩만 있어 카테고리가 필요 없다 — 칩 줄을 통째로 감춘다. */}
          <SearchFilterBar
            query={query}
            onQueryChange={setQuery}
            searchPlaceholder="해시태그 검색"
            options={browseOptions}
            chipIcons={CHIP_ICONS}
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
          refreshControl={
            usesServer ? (
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={INK} />
            ) : undefined
          }
          contentContainerStyle={[styles.grid, { paddingBottom: 24 }, contentStyle(ContentMax.wide)]}>
          {usesServer && loading && !loaded ? (
            <LoadingState message="룩북을 불러오는 중…" style={styles.empty} />
          ) : usesServer && error && savedLooks.length === 0 ? (
            <ErrorState
              title="룩북을 불러오지 못했어요"
              description={error}
              onRetry={() => void loadAll()}
              style={styles.empty}
            />
          ) : cards.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>{emptyText}</Text>
              {mode === 'mine' ? (
                <Pressable style={styles.emptyBtn} onPress={() => router.push('/look-add')}>
                  <Text style={styles.emptyBtnText}>첫 룩 올리기</Text>
                </Pressable>
              ) : wishOn ? (
                /* 담을 것이 없으면 담으러 갈 곳으로 — 위시 칩을 끄면 그 자리가 둘러보기다. */
                <Pressable style={styles.emptyBtn} onPress={() => toggle(WISH)}>
                  <Text style={styles.emptyBtnText}>둘러보며 마음에 드는 룩 찾기</Text>
                </Pressable>
              ) : (
                <Pressable style={styles.emptyBtn} onPress={() => router.push('/look-add')}>
                  <Text style={styles.emptyBtnText}>내 룩 올리기</Text>
                </Pressable>
              )}
            </View>
          ) : (
            cards.map((c) => (
              <Pressable
                key={c.id}
                style={[styles.card, { width: cardW }]}
                /* 담아둔 룩은 저장 상세로, 피드 룩은 그 룩의 추천 상세로 보낸다.
                   돌아올 자리는 지금 보고 있던 갈래 그대로여야 한다. */
                onPress={() =>
                  router.push(
                    c.kind === 'saved'
                      ? withReturn(`/saved-look?id=${c.id}`, returnHere)
                      : withReturn(`/look-detail?id=${c.variantId ?? 'daily'}`, returnHere),
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
                  {/* 출처 — 하트가 오른쪽 위를 쓰고 있어 왼쪽 위에 둔다 */}
                  {c.origin ? (
                    <View
                      style={styles.originBadge}
                      accessibilityLabel={ORIGIN_BADGE[c.origin].label}>
                      <Icon name={ORIGIN_BADGE[c.origin].icon} tintColor={INK} size={15} />
                    </View>
                  ) : null}
                  {/* 하트는 피드 룩에만 단다. 저장 룩(✨)에 달면 저장 룩 id 로 좋아요가 따로 생겨
                      같은 룩이 위시 목록에 두 번 서게 된다 — 빼는 길은 저장 룩 상세에 있다. */}
                  {c.kind === 'feed' && c.tags ? (
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

        {/* 올리기는 어느 갈래에서든 같은 자리에 있다 — 결과는 늘 내 룩북에 쌓인다. */}
        <Pressable
          style={[styles.addFab, { bottom: 12 }]}
          onPress={() => router.push('/look-add')}
          accessibilityLabel="룩 올리기">
          <Icon name="plus" tintColor={INK} size={22} />
        </Pressable>
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
  originBadge: {
    position: 'absolute',
    top: 10,
    left: 10,
    width: 28,
    height: 28,
    borderRadius: 14,
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
