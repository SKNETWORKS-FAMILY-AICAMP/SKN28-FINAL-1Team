import { Icon } from '@/components/icon';
import { useRef, useState, type ReactNode } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;
const PAD = 20;
const DROP_W = 140;

type SearchFilterBarProps = {
  query: string;
  onQueryChange: (value: string) => void;
  searchPlaceholder: string;
  options: string[];
  onToggle: (option: string) => void;
  isActive: (option: string) => boolean;
  /** 검색행 오른쪽에 붙는 컨트롤 (예: 내 옷/공유 드롭다운) */
  trailing?: ReactNode;
  /** false면 검색·칩을 숨기고 trailing만 표시 */
  showFilters?: boolean;
  /** 카테고리 편집 시트 열기 */
  onEditCategories?: () => void;
};

export function SearchFilterBar({
  query,
  onQueryChange,
  searchPlaceholder,
  options,
  onToggle,
  isActive,
  trailing,
  showFilters = true,
  onEditCategories,
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

      {showFilters ? (
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
                <Text style={[styles.chipText, on && styles.chipTextOn]}>{c}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
    </>
  );
}

type DropdownOption<T extends string> = { value: T; label: string };

type InlineDropdownProps<T extends string> = {
  value: T;
  options: DropdownOption<T>[];
  onChange: (value: T) => void;
  /** 긴 라벨용 — 작은 글씨·좁은 패딩 */
  compact?: boolean;
};

/** 검색행 오른쪽에 붙는 단일 선택 드롭다운 */
export function InlineDropdown<T extends string>({
  value,
  options,
  onChange,
  compact = false,
}: InlineDropdownProps<T>) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState({ x: 0, y: 0, w: 0, h: 0 });
  const btnRef = useRef<View>(null);

  const selected = options.find((o) => o.value === value);

  const openMenu = () => {
    btnRef.current?.measureInWindow((x, y, w, h) => {
      setAnchor({ x, y, w, h });
      setOpen(true);
    });
  };

  const pick = (next: T) => {
    onChange(next);
    setOpen(false);
  };

  return (
    <>
      <Pressable
        ref={btnRef}
        style={[styles.dropBtn, compact && styles.dropBtnCompact]}
        onPress={openMenu}>
        <Text
          style={[styles.dropValue, compact && styles.dropValueCompact]}
          numberOfLines={1}>
          {selected?.label ?? value}
        </Text>
        <Icon name="chevron.down" tintColor={ink(0.45)} size={compact ? 12 : 14} />
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.dropBackdrop} onPress={() => setOpen(false)}>
          <View
            style={[
              styles.dropList,
              {
                top: anchor.y + anchor.h + 6,
                left: Math.max(anchor.x + anchor.w - DROP_W, PAD),
                width: compact ? 128 : DROP_W,
              },
            ]}>
            {options.map((o) => {
              const on = o.value === value;
              return (
                <Pressable key={o.value} style={styles.dropItem} onPress={() => pick(o.value)}>
                  <Text style={[styles.dropItemText, compact && styles.dropItemTextCompact, on && styles.dropItemTextOn]}>
                    {o.label}
                  </Text>
                  {on ? <Icon name="checkmark" tintColor={INK} size={15} /> : null}
                </Pressable>
              );
            })}
          </View>
        </Pressable>
      </Modal>
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
    backgroundColor: '#f3ece2',
  },
  searchBarSpacer: { flex: 1 },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: INK,
    padding: 0,
  },

  dropBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.14),
    backgroundColor: '#ffffff',
    flexShrink: 0,
  },
  dropBtnCompact: {
    gap: 4,
    paddingHorizontal: 10,
  },
  dropValue: { fontSize: 14, fontWeight: '600', color: INK },
  dropValueCompact: { fontSize: 11.5, fontWeight: '600', letterSpacing: -0.3 },

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
  dropItemTextCompact: { fontSize: 13 },
  dropItemTextOn: { color: INK, fontWeight: '600' },

  chipScroll: { flexGrow: 0, height: 60 },
  chipRow: { paddingHorizontal: PAD, gap: 8, paddingBottom: 20, alignItems: 'center' },
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
  editChip: {
    width: 36,
    height: 36,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.12),
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f3ece2',
  },
});
