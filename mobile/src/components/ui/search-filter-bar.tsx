import { Editorial, ink } from '@/constants/theme';
import { Icon, type IconName } from '@/components/icon';
import { type ReactNode } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

const INK = Editorial.ink;
const PAD = 20;

type SearchFilterBarProps = {
  query: string;
  onQueryChange: (value: string) => void;
  searchPlaceholder: string;
  options: string[];
  onToggle: (option: string) => void;
  isActive: (option: string) => boolean;
  /** 검색행 오른쪽에 붙는 컨트롤 (예: 내 옷/공유 드롭다운) */
  trailing?: ReactNode;
  /** 검색행과 카테고리 칩 사이에 끼우는 영역 (예: 둘러보기/저장됨 세그먼트) */
  middle?: ReactNode;
  /** false면 검색·칩을 숨기고 trailing만 표시 */
  showFilters?: boolean;
  /** 카테고리 칩 줄만 숨긴다(검색·middle은 유지) */
  showChips?: boolean;
  /** 카테고리 편집 시트 열기 */
  onEditCategories?: () => void;
  /**
   * 칩에 아이콘을 달고 싶을 때 (옵션 이름 → 아이콘).
   * 해시태그 칩들 사이에서 성격이 다른 칩(예: '위시')을 글자만으로 가르기 어려워,
   * 그 칩에만 표식을 준다.
   */
  chipIcons?: Partial<Record<string, IconName>>;
};

export function SearchFilterBar({
  query,
  onQueryChange,
  searchPlaceholder,
  options,
  onToggle,
  isActive,
  trailing,
  middle,
  showFilters = true,
  showChips = true,
  onEditCategories,
  chipIcons,
}: SearchFilterBarProps) {
  return (
    <>
      <View style={styles.searchRow}>
        {showFilters ? (
          <View style={styles.searchBar}>
            <Icon name="magnifyingglass" tintColor={ink(0.35)} size={16} />
            <TextInput
              value={query}
              onChangeText={onQueryChange}
              placeholder={searchPlaceholder}
              placeholderTextColor={ink(0.35)}
              style={styles.searchInput}
              returnKeyType="search"
              clearButtonMode="while-editing"
            />
          </View>
        ) : (
          <View style={styles.searchBarSpacer} />
        )}
        {trailing}
      </View>

      {middle}

      {showFilters && showChips ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.chipScroll}
          contentContainerStyle={styles.chipRow}>
          {onEditCategories ? (
            <Pressable
              style={styles.editChip}
              onPress={onEditCategories}
              accessibilityLabel="카테고리 수정">
              <Icon name="slider.horizontal.3" tintColor={ink(0.45)} size={16} />
            </Pressable>
          ) : null}
          {options.map((c) => {
            const on = isActive(c);
            return (
              <Pressable
                key={c}
                onPress={() => onToggle(c)}
                style={[styles.chip, on && styles.chipOn]}>
                {chipIcons?.[c] ? (
                  <Icon
                    name={chipIcons[c]!}
                    tintColor={on ? '#fff' : Editorial.textCaption}
                    size={13}
                  />
                ) : null}
                <Text style={[styles.chipText, on && styles.chipTextOn]}>{c}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  searchRow: { flexDirection: 'row', gap: 10, paddingHorizontal: PAD, marginBottom: 18 },
  searchBar: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: Editorial.control,
    borderWidth: 1, borderColor: Editorial.line,
  },
  searchBarSpacer: { flex: 1 },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: INK,
    padding: 0,
  },

  chipScroll: { flexGrow: 0, height: 60 },
  chipRow: { paddingHorizontal: PAD, gap: 8, paddingBottom: 20, alignItems: 'center' },
  chip: {
    height: 36,
    paddingHorizontal: 15,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.12),
    /* 아이콘이 붙는 칩이 있어 가로로 세운다 — 아이콘이 없으면 글자만 남아 종전과 같다. */
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
  },
  chipOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  chipText: { fontSize: 13, lineHeight: 18, color: Editorial.textCaption, fontWeight: '500' },
  chipTextOn: { color: '#fff' },
  editChip: {
    width: 36,
    height: 36,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.12),
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Editorial.control,
  },
});
