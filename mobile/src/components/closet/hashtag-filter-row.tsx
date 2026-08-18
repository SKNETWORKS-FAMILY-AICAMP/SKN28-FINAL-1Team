import { Icon } from '@/components/icon';
import { Editorial, Type, ink } from '@/constants/theme';
import type { WardrobeHashtag } from '@/lib/wardrobeApi';
import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';

type Props = {
  hashtags: WardrobeHashtag[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onAdd: () => void;
  onManage: (id: string) => void;
};

export function HashtagFilterRow({ hashtags, selectedIds, onToggle, onAdd, onManage }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}>
      <Pressable style={styles.add} onPress={onAdd} accessibilityLabel="해시태그 추가">
        <Icon name="plus" tintColor={Editorial.textCaption} size={16} />
      </Pressable>
      {hashtags.map((hashtag) => {
        const active = selectedIds.includes(hashtag.id);
        return (
          <Pressable
            key={hashtag.id}
            style={[styles.chip, active && styles.chipActive]}
            onPress={() => onToggle(hashtag.id)}
            onLongPress={() => onManage(hashtag.id)}
            accessibilityLabel={`해시태그 ${hashtag.name}`}>
            <Text style={[styles.text, active && styles.textActive]}>#{hashtag.name}</Text>
          </Pressable>
        );
      })}
      {hashtags.length === 0 ? <Text style={styles.empty}>옷을 선택해 첫 해시태그를 만들어 보세요</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { minHeight: 44, alignItems: 'center', gap: 7, paddingHorizontal: 20, paddingBottom: 10 },
  add: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: ink(0.13), borderRadius: 16, backgroundColor: Editorial.control },
  chip: { height: 32, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 13, borderWidth: 1, borderColor: ink(0.11), borderRadius: 16, backgroundColor: Editorial.surface },
  chipActive: { borderColor: Editorial.selected, backgroundColor: Editorial.selected },
  text: { fontSize: Type.micro, fontWeight: '600', color: Editorial.textCaption },
  textActive: { color: Editorial.white },
  empty: { fontSize: Type.micro, color: Editorial.textMuted },
});
