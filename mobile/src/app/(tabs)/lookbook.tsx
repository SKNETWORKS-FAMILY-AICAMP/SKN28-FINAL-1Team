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

import { BottomTabInset, Fonts } from '@/constants/theme';

const INK = '#1c1917';
const BONE = '#ecebe7';
const ink = (a: number) => `rgba(28,25,23,${a})`;

// 웹 데스크톱에선 브라우저 전체 폭이 잡혀 그리드가 깨지므로 폰 프레임 폭으로 캡 (global.css와 동일: 440)
const width = Math.min(Dimensions.get('window').width, 440);
const GAP = 12;
const PAD = 20;
const CARD_W = (width - PAD * 2 - GAP) / 2;

const FILTERS = ['전체', '출근', '데이트', '나들이', '여행'];

type Look = {
  id: string;
  title: string;
  brand: string; // "COS 외 2 브랜드"
  price: string; // "₩189,000"
  tpo: string;
  tone: number;
};
const LOOKS: Look[] = [
  { id: '1', title: '미니멀 오피스 룩', brand: 'COS 외 2 브랜드', price: '₩189,000', tpo: '출근', tone: 0.08 },
  { id: '2', title: '포근한 니트 데이트', brand: '유니클로 외 1', price: '₩97,000', tpo: '데이트', tone: 0.16 },
  { id: '3', title: '단정한 면접 룩', brand: '로가디스 외 2', price: '₩245,000', tpo: '출근', tone: 0.22 },
  { id: '4', title: '캐주얼 주말 룩', brand: '무신사 외 3', price: '₩132,000', tpo: '나들이', tone: 0.12 },
  { id: '5', title: '여행 데일리 룩', brand: '스파오 외 2', price: '₩88,000', tpo: '여행', tone: 0.06 },
  { id: '6', title: '러블리 데이트 룩', brand: '자라 외 1', price: '₩156,000', tpo: '데이트', tone: 0.26 },
];

// E1 룩북 탭 — 저장 룩 그리드 (가격·브랜드 표시)
export default function LookbookScreen() {
  const [filter, setFilter] = useState('전체');

  const looks = useMemo(
    () => (filter === '전체' ? LOOKS : LOOKS.filter((l) => l.tpo === filter)),
    [filter],
  );

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={styles.header}>
          <Text style={styles.title}>룩북</Text>
          <Text style={styles.count}>저장한 {LOOKS.length}개의 룩</Text>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.filterScroll}
          contentContainerStyle={styles.filterRow}>
          {FILTERS.map((c) => {
            const on = c === filter;
            return (
              <Pressable
                key={c}
                onPress={() => setFilter(c)}
                style={[styles.filterChip, on && styles.filterChipOn]}>
                <Text style={[styles.filterText, on && styles.filterTextOn]}>{c}</Text>
              </Pressable>
            );
          })}
        </ScrollView>

        <ScrollView
          style={styles.gridScroll}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.grid}>
          {looks.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>아직 이 필터의 룩이 없어요</Text>
            </View>
          ) : (
            looks.map((lk) => (
              <Pressable
                key={lk.id}
                style={styles.card}
                onPress={() => router.push('/saved-look')}>
                <View style={[styles.cardImage, { backgroundColor: `rgba(28,25,23,${lk.tone})` }]}>
                  <View style={styles.priceBadge}>
                    <Text style={styles.priceText}>{lk.price}</Text>
                  </View>
                </View>
                <Text style={styles.cardTitle} numberOfLines={1}>{lk.title}</Text>
                <Text style={styles.cardBrand} numberOfLines={1}>{lk.brand}</Text>
              </Pressable>
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },

  header: {
    paddingHorizontal: PAD,
    paddingTop: 12,
    paddingBottom: 14,
  },
  title: { fontFamily: Fonts.serif, fontSize: 26, fontWeight: '500', color: INK },
  count: { fontSize: 12, color: ink(0.45), marginTop: 3 },

  filterScroll: { flexGrow: 0, height: 54 },
  filterRow: { paddingHorizontal: PAD, gap: 8, paddingBottom: 14 },
  filterChip: {
    height: 36,
    paddingHorizontal: 15,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.12),
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterChipOn: { backgroundColor: INK, borderColor: INK },
  filterText: { fontSize: 12.5, lineHeight: 18, color: ink(0.55), fontWeight: '500' },
  filterTextOn: { color: '#fff' },

  gridScroll: { flex: 1 },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    paddingHorizontal: PAD,
    paddingBottom: BottomTabInset + 24,
  },
  card: { width: CARD_W, marginBottom: 20 },
  cardImage: {
    width: '100%',
    height: CARD_W * 1.4,
    borderRadius: 18,
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
  cardTitle: { fontSize: 13.5, fontWeight: '600', color: ink(0.9), marginTop: 10 },
  cardBrand: { fontSize: 11.5, color: ink(0.4), marginTop: 3 },

  empty: { width: '100%', alignItems: 'center', paddingTop: 60 },
  emptyText: { fontSize: 13, color: ink(0.4) },
});
