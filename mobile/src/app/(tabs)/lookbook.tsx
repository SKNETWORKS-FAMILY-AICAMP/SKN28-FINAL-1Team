import { CategoryEditSheet, SearchFilterBar, SmartImage } from '@/components/ui';
import { Icon } from '@/components/icon';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import {
  LOOKBOOK_FILTER_OPTIONS,
  type LookPost,
  useLookbook,
} from '@/state/lookbook';
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

import { BottomTabInset, GridCard, gridCardImageHeight, gridCardWidth } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

/* 카드 크기는 창 폭에서 파생 → 컴포넌트 안에서 useBreakpoint() 로 구한다. */
const PAD = GridCard.pad;
const DEFAULT_TAGS = [...LOOKBOOK_FILTER_OPTIONS];

function matchesQuery(look: LookPost, query: string): boolean {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return true;
  return look.tags.some((tag) => tag.toLocaleLowerCase().includes(q));
}

function matchesTags(look: LookPost, selected: string[]): boolean {
  if (selected.length === 0) return true;
  return look.tags.some((tag) => selected.includes(tag));
}

export default function LookbookScreen() {
  const { frameWidth } = useBreakpoint();
  const cardW = gridCardWidth(frameWidth);
  const cardH = gridCardImageHeight(cardW);

  const allLooks = useLookbook();
  const [query, setQuery] = useState('');
  const [tags, setTags] = useState(DEFAULT_TAGS);
  const [editOpen, setEditOpen] = useState(false);
  const { toggle, isActive, selected, label, prune } = useMultiSelectFilter();

  const looks = useMemo(
    () => allLooks.filter((l) => matchesTags(l, selected) && matchesQuery(l, query)),
    [allLooks, selected, query],
  );

  const emptyText = useMemo(() => {
    if (query.trim()) return `'${query.trim()}' 검색 결과가 없어요`;
    if (label !== '전체') return `'${label}' 태그 룩이 없어요`;
    return '아직 올린 룩이 없어요';
  }, [query, label]);

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
            onEditCategories={() => setEditOpen(true)}
          />
        </View>

        <ScrollView
          style={styles.gridScroll}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.grid}>
          {looks.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>{emptyText}</Text>
              <Pressable style={styles.emptyBtn} onPress={() => router.push('/look-add')}>
                <Text style={styles.emptyBtnText}>첫 룩 올리기</Text>
              </Pressable>
            </View>
          ) : (
            looks.map((lk) => (
              <Pressable
                key={lk.id}
                style={[styles.card, { width: cardW }]}
                onPress={() => router.push('/saved-look')}>
                <View style={[styles.cardImage, { height: cardH }]}>
                  <SmartImage
                    uri={lk.image}
                    width="100%"
                    height={cardH}
                    radius={GridCard.radius}
                    contentFit="cover"
                  />
                  {lk.price ? (
                    <View style={styles.priceBadge}>
                      <Text style={styles.priceText}>{lk.price}</Text>
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

        <Pressable
          style={styles.addFab}
          onPress={() => router.push('/look-add')}
          accessibilityLabel="룩 올리기">
          <Icon name="plus" tintColor={INK} size={22} />
        </Pressable>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },

  filterArea: { marginTop: 30 },

  gridScroll: { flex: 1, marginTop: 8 },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
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
