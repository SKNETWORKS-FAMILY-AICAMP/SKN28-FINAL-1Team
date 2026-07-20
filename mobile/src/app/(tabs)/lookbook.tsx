import { SearchFilterBar, SmartImage } from '@/components/ui';
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
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BottomTabInset, GridCard, gridCardImageHeight, gridCardWidth } from '@/constants/theme';

const INK = '#1c1917';
const BONE = '#ecebe7';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const CARD_W = gridCardWidth(Dimensions.get('window').width);
const CARD_H = gridCardImageHeight(CARD_W);
const PAD = GridCard.pad;

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
  const allLooks = useLookbook();
  const [query, setQuery] = useState('');
  const { toggle, isActive, selected, label } = useMultiSelectFilter();

  const looks = useMemo(
    () => allLooks.filter((l) => matchesTags(l, selected) && matchesQuery(l, query)),
    [allLooks, selected, query],
  );

  const emptyText = useMemo(() => {
    if (query.trim()) return `'${query.trim()}' 검색 결과가 없어요`;
    if (label !== '전체') return `'${label}' 태그 룩이 없어요`;
    return '아직 올린 룩이 없어요';
  }, [query, label]);

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={styles.filterArea}>
          <SearchFilterBar
            query={query}
            onQueryChange={setQuery}
            searchPlaceholder="해시태그 검색"
            options={LOOKBOOK_FILTER_OPTIONS}
            onToggle={toggle}
            isActive={isActive}
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
                style={styles.card}
                onPress={() => router.push('/saved-look')}>
                <View style={styles.cardImage}>
                  <SmartImage uri={lk.image} width="100%" height={CARD_H} radius={GridCard.radius} />
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
  card: { width: CARD_W, marginBottom: 12 },
  cardImage: {
    width: '100%',
    height: CARD_H,
    borderRadius: GridCard.radius,
    backgroundColor: BONE,
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
