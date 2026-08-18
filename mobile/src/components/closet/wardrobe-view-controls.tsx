import { Editorial, Type } from '@/constants/theme';
import type { WardrobeGroupMode, WardrobeItemSort } from '@/lib/wardrobeSections';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

type WardrobeViewControlsProps = {
  groupMode: WardrobeGroupMode;
  itemSort: WardrobeItemSort;
  onGroupModeChange: (value: WardrobeGroupMode) => void;
  onItemSortChange: (value: WardrobeItemSort) => void;
};

const GROUP_OPTIONS: { value: WardrobeGroupMode; label: string }[] = [
  { value: 'SYSTEM_CATEGORY', label: '기본 카테고리별' },
  { value: 'CUSTOM_CATEGORY', label: '내 카테고리별' },
];

const SORT_OPTIONS: { value: WardrobeItemSort; label: string }[] = [
  { value: 'ADDED_DESC', label: '최근 추가순' },
  { value: 'COLOR_NAME_ASC', label: '색상·이름순' },
];

export function WardrobeViewControls({
  groupMode,
  itemSort,
  onGroupModeChange,
  onItemSortChange,
}: WardrobeViewControlsProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.content}>
      <View style={styles.optionGroup}>
        <Text style={styles.label}>묶기</Text>
        {GROUP_OPTIONS.map((option) => {
          const active = groupMode === option.value;
          return (
            <Pressable
              key={option.value}
              style={[styles.option, active && styles.optionActive]}
              onPress={() => onGroupModeChange(option.value)}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}>
              <Text style={[styles.optionText, active && styles.optionTextActive]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <View style={styles.optionGroup}>
        <Text style={styles.label}>정렬</Text>
        {SORT_OPTIONS.map((option) => {
          const active = itemSort === option.value;
          return (
            <Pressable
              key={option.value}
              style={[styles.option, active && styles.optionActive]}
              onPress={() => onItemSortChange(option.value)}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}>
              <Text style={[styles.optionText, active && styles.optionTextActive]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 20,
    paddingBottom: 12,
  },
  optionGroup: {
    height: 38,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 5,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 12,
    backgroundColor: Editorial.control,
  },
  label: {
    paddingHorizontal: 7,
    fontSize: Type.micro,
    fontWeight: '600',
    color: Editorial.textCaption,
  },
  option: {
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  optionActive: { backgroundColor: Editorial.selected },
  optionText: { fontSize: Type.micro, fontWeight: '600', color: Editorial.textCaption },
  optionTextActive: { color: Editorial.white },
});
