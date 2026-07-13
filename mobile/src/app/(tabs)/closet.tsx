import { Icon } from '@/components/icon';
import { EmptyState } from '@/components/ui';
import { router } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import {
  Dimensions,
  Modal,
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
const DROP_W = 168; // 드롭다운 목록 폭

const CATEGORIES = ['전체', '상의', '하의', '아우터', '신발', '가방', '액세서리'];

type Item = {
  id: string;
  name: string;
  category: string;
  tone: number;
  owner?: string; // 공유 옷장일 때 공유한 사람
};

// 나의 옷장
const MY_ITEMS: Item[] = [
  { id: '1', name: '화이트 코튼 셔츠', category: '상의', tone: 0.05 },
  { id: '2', name: '네이비 블레이저', category: '아우터', tone: 0.22 },
  { id: '3', name: '그레이 울 슬랙스', category: '하의', tone: 0.16 },
  { id: '4', name: '브라운 페니 로퍼', category: '신발', tone: 0.24 },
  { id: '5', name: '크림 케이블 니트', category: '상의', tone: 0.08 },
  { id: '6', name: '인디고 데님 팬츠', category: '하의', tone: 0.28 },
  { id: '7', name: '블랙 레더 토트백', category: '가방', tone: 0.3 },
  { id: '8', name: '카멜 실크 스카프', category: '액세서리', tone: 0.13 },
];

// 공유 옷장 (친구·팀원이 공유한 아이템)
const SHARED_ITEMS: Item[] = [
  { id: 's1', name: '카멜 오버 코트', category: '아우터', tone: 0.12, owner: '지민' },
  { id: 's2', name: '플리츠 미디 스커트', category: '하의', tone: 0.07, owner: '서연' },
  { id: 's3', name: '체크 오버 셔츠', category: '상의', tone: 0.18, owner: '민준' },
  { id: 's4', name: '스웨이드 첼시 부츠', category: '신발', tone: 0.26, owner: '지민' },
];

// D1 옷장 탭 — 나의/공유 탭 + (검색+드롭다운 한 줄) + 카테고리 칩 + 2열 그리드
export default function ClosetScreen() {
  const [tab, setTab] = useState<'mine' | 'shared'>('mine');
  const [filter, setFilter] = useState('전체');
  const [catOpen, setCatOpen] = useState(false);
  const [anchor, setAnchor] = useState({ x: 0, y: 0, w: 0, h: 0 });
  const catBtnRef = useRef<View>(null);

  // 드롭다운 버튼 위치를 측정해서 그 아래에 목록을 띄운다
  const openCategory = () => {
    catBtnRef.current?.measureInWindow((x, y, w, h) => {
      setAnchor({ x, y, w, h });
      setCatOpen(true);
    });
  };

  const source = tab === 'mine' ? MY_ITEMS : SHARED_ITEMS;
  const items = useMemo(
    () => (filter === '전체' ? source : source.filter((i) => i.category === filter)),
    [filter, source],
  );

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        {/* 헤더 */}
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>옷장</Text>
            <Text style={styles.count}>
              {tab === 'mine' ? '42개의 아이템' : `${SHARED_ITEMS.length}개의 공유 아이템`}
            </Text>
          </View>
          <Pressable hitSlop={10} style={styles.addBtn} onPress={() => router.push('/item-add')}>
            <Icon name="plus" tintColor="#fff" size={18} />
          </Pressable>
        </View>

        {/* 나의 옷장 / 공유 옷장 탭 */}
        <View style={styles.tabs}>
          {([
            ['mine', '나의 옷장'],
            ['shared', '공유 옷장'],
          ] as const).map(([key, label]) => {
            const on = tab === key;
            return (
              <Pressable
                key={key}
                style={styles.tab}
                onPress={() => {
                  setTab(key);
                  setFilter('전체');
                }}>
                <Text style={[styles.tabText, on && styles.tabTextOn]}>{label}</Text>
                {on ? <View style={styles.tabUnderline} /> : null}
              </Pressable>
            );
          })}
        </View>
        <View style={styles.tabDivider} />

        {/* 검색 + 카테고리 드롭다운 (한 줄) */}
        <View style={styles.searchRow}>
          <View style={styles.searchBar}>
            <Icon name="magnifyingglass" tintColor={ink(0.35)} size={16} />
            <Text style={styles.searchPlaceholder}>옷장에서 검색</Text>
          </View>
          <Pressable ref={catBtnRef} style={styles.catBtn} onPress={openCategory}>
            <Text style={styles.catValue} numberOfLines={1}>{filter}</Text>
            <Icon name="chevron.down" tintColor={ink(0.45)} size={14} />
          </Pressable>
        </View>

        {/* 카테고리 칩 (넘겨서 선택) — 드롭다운과 같은 filter 상태 공유 */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.chipScroll}
          contentContainerStyle={styles.chipRow}>
          {CATEGORIES.map((c) => {
            const on = c === filter;
            return (
              <Pressable
                key={c}
                onPress={() => setFilter(c)}
                style={[styles.chip, on && styles.chipOn]}>
                <Text style={[styles.chipText, on && styles.chipTextOn]}>{c}</Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {/* 그리드 */}
        <ScrollView
          style={styles.gridScroll}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.grid}>
          {items.length === 0 ? (
            <EmptyState
              icon={tab === 'shared' ? 'person' : 'tshirt'}
              title={filter === '전체' ? '옷장이 비어있어요' : `'${filter}'가 비어있어요`}
              description={
                tab === 'shared'
                  ? '아직 공유받은 아이템이 없어요.'
                  : filter === '전체'
                    ? '첫 아이템을 추가해 옷장을 채워보세요.'
                    : '다른 카테고리를 골라보거나 새로 추가해 보세요.'
              }
              actionLabel={tab === 'mine' ? '아이템 추가하기' : undefined}
              onAction={tab === 'mine' ? () => router.push('/item-add') : undefined}
              style={styles.empty}
            />
          ) : (
            items.map((it) => (
              <Pressable
                key={it.id}
                style={styles.card}
                onPress={() => router.push('/item-detail')}>
                <View style={[styles.cardImage, { backgroundColor: `rgba(28,25,23,${it.tone})` }]}>
                  {it.owner ? (
                    <View style={styles.ownerBadge}>
                      <Text style={styles.ownerText}>{it.owner}님</Text>
                    </View>
                  ) : null}
                </View>
                <Text style={styles.cardCat}>{it.category}</Text>
                <Text style={styles.cardName} numberOfLines={1}>{it.name}</Text>
              </Pressable>
            ))
          )}
        </ScrollView>
      </SafeAreaView>

      {/* 카테고리 드롭다운 목록 (버튼 아래·오른쪽 정렬, 바깥 탭하면 닫힘) */}
      <Modal
        visible={catOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setCatOpen(false)}>
        <Pressable style={styles.dropBackdrop} onPress={() => setCatOpen(false)}>
          <View
            style={[
              styles.dropList,
              {
                top: anchor.y + anchor.h + 6,
                left: Math.max(anchor.x + anchor.w - DROP_W, PAD),
                width: DROP_W,
              },
            ]}>
            {CATEGORIES.map((c) => {
              const on = c === filter;
              return (
                <Pressable
                  key={c}
                  style={styles.dropItem}
                  onPress={() => {
                    setFilter(c);
                    setCatOpen(false);
                  }}>
                  <Text style={[styles.dropItemText, on && styles.dropItemTextOn]}>{c}</Text>
                  {on ? <Icon name="checkmark" tintColor={INK} size={15} /> : null}
                </Pressable>
              );
            })}
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },

  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingHorizontal: PAD,
    paddingTop: 12,
    paddingBottom: 12,
  },
  title: { fontFamily: Fonts.serif, fontSize: 26, fontWeight: '500', color: INK },
  count: { fontSize: 13, color: ink(0.45), marginTop: 3 },
  addBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // 탭
  tabs: { flexDirection: 'row', gap: 22, paddingHorizontal: PAD },
  tab: { paddingVertical: 8 },
  tabText: { fontSize: 15, color: ink(0.4), fontWeight: '500' },
  tabTextOn: { color: INK, fontWeight: '700' },
  tabUnderline: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 2,
    backgroundColor: INK,
    borderRadius: 1,
  },
  tabDivider: { height: 1, backgroundColor: ink(0.08), marginBottom: 14 },

  // 검색 + 드롭다운 한 줄
  searchRow: { flexDirection: 'row', gap: 10, paddingHorizontal: PAD, marginBottom: 12 },
  searchBar: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#f3f2ef',
  },
  searchPlaceholder: { fontSize: 14, color: ink(0.35) },
  catBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.14),
    backgroundColor: '#ffffff',
  },
  catValue: { fontSize: 14, fontWeight: '600', color: INK },

  // 드롭다운 목록
  dropBackdrop: { flex: 1, backgroundColor: 'rgba(28,25,23,0.08)' },
  dropList: {
    position: 'absolute',
    backgroundColor: '#ffffff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.1),
    paddingVertical: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.14,
    shadowRadius: 20,
    elevation: 8,
  },
  dropItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  dropItemText: { fontSize: 14, color: ink(0.6) },
  dropItemTextOn: { color: INK, fontWeight: '600' },

  // 카테고리 칩
  chipScroll: { flexGrow: 0, height: 54 },
  chipRow: { paddingHorizontal: PAD, gap: 8, paddingBottom: 14 },
  chip: {
    height: 36,
    paddingHorizontal: 15,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.12),
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipOn: { backgroundColor: INK, borderColor: INK },
  chipText: { fontSize: 13, lineHeight: 18, color: ink(0.55), fontWeight: '500' },
  chipTextOn: { color: '#fff' },

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
    height: CARD_W * 1.25,
    borderRadius: 16,
    backgroundColor: BONE,
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
  cardCat: { fontSize: 12, color: ink(0.4), marginTop: 10 },
  cardName: { fontSize: 14, fontWeight: '500', color: ink(0.9), marginTop: 3 },

  empty: { width: '100%', paddingTop: 40 },
});
