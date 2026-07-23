import { CategoryEditSheet, SearchFilterBar, SmartImage } from '@/components/ui';
import { Icon } from '@/components/icon';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import {
  LOOKBOOK_FILTER_OPTIONS,
  useLookbook,
} from '@/state/lookbook';
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

import { Editorial, ink, BottomTabInset, GridCard, gridCardImageHeight, gridCardWidth , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = Editorial.ink;

/* 카드 크기는 창 폭에서 파생 → 컴포넌트 안에서 useBreakpoint() 로 구한다. */
const PAD = GridCard.pad;
const DEFAULT_TAGS = [...LOOKBOOK_FILTER_OPTIONS];

/** 상단 세그먼트: 둘러보기(남들이 올린 피드) / 저장됨(내가 저장한 룩) */
type Mode = 'browse' | 'saved';
const TABS: { key: Mode; label: string }[] = [
  { key: 'browse', label: '둘러보기' },
  { key: 'saved', label: '저장됨' },
];

/** 그리드 카드 공통 형태 — 피드 룩(price 有)·저장 룩(asset 有) 모두 이 형태로 정규화 */
type CardData = { id: string; uri?: string; asset?: number; price?: string };

function matchesQuery(look: { tags: string[] }, query: string): boolean {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return true;
  return look.tags.some((tag) => tag.toLocaleLowerCase().includes(q));
}

function matchesTags(look: { tags: string[] }, selected: string[]): boolean {
  if (selected.length === 0) return true;
  return look.tags.some((tag) => selected.includes(tag));
}

function LookbookTabs({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <View style={styles.tabs}>
      {TABS.map((t) => {
        const on = mode === t.key;
        return (
          <Pressable
            key={t.key}
            style={[styles.tab, on && styles.tabOn]}
            onPress={() => onChange(t.key)}>
            <Text style={[styles.tabText, on && styles.tabTextOn]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function LookbookScreen() {
  const { frameWidth, contentStyle } = useBreakpoint();
  const cardW = gridCardWidth(frameWidth);
  const cardH = gridCardImageHeight(cardW);

  const allLooks = useLookbook();
  const savedLooks = useSavedLooks();

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
      ? feedLooks.map((l) => ({ id: l.id, uri: l.image, price: l.price }))
      : savedFiltered.map((l) => ({ id: l.id, uri: l.image, asset: l.asset }));

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
            middle={<LookbookTabs mode={mode} onChange={setMode} />}
          />
        </View>

        <ScrollView
          style={styles.gridScroll}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.grid, contentStyle(ContentMax.wide)]}>
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
                onPress={() => router.push('/saved-look')}>
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
            style={styles.addFab}
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
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },

  filterArea: { marginTop: 30 },

  tabs: { flexDirection: 'row', gap: 8, paddingHorizontal: PAD, marginBottom: 16 },
  tab: {
    flex: 1,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Editorial.surface,
  },
  tabOn: { backgroundColor: INK },
  tabText: { fontSize: 14, fontWeight: '600', color: ink(0.5) },
  tabTextOn: { color: '#fff' },

  gridScroll: { flex: 1, marginTop: 8 },
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

  empty: { width: '100%', alignItems: 'center', paddingTop: 60, gap: 16 },
  emptyText: { fontSize: 13, color: ink(0.4) },
  emptyBtn: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: INK,
  },
  emptyBtnText: { fontSize: 13, fontWeight: '600', color: '#fff' },

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
