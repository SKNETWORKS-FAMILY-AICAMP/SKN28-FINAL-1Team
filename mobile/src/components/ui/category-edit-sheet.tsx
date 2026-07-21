import { Icon } from '@/components/icon';
import { useEffect, useState } from 'react';
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

type CategoryEditSheetProps = {
  visible: boolean;
  title: string;
  /** 첫 항목은 항상 '전체' (고정) */
  categories: string[];
  onClose: () => void;
  onSave: (categories: string[]) => void;
  addPlaceholder?: string;
};

export function CategoryEditSheet({
  visible,
  title,
  categories,
  onClose,
  onSave,
  addPlaceholder = '새 카테고리',
}: CategoryEditSheetProps) {
  const [draft, setDraft] = useState<string[]>(categories);
  const [newName, setNewName] = useState('');

  useEffect(() => {
    if (visible) {
      setDraft(categories);
      setNewName('');
    }
  }, [visible, categories]);

  const editable = draft.slice(1);

  const addCategory = () => {
    const name = newName.trim();
    if (!name || draft.includes(name)) return;
    setDraft((prev) => [...prev, name]);
    setNewName('');
  };

  const removeCategory = (name: string) => {
    setDraft((prev) => prev.filter((c) => c !== name));
  };

  const handleSave = () => {
    onSave(draft);
    onClose();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.handle} />
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.hint}>'전체'는 항상 맨 앞에 유지돼요.</Text>

          <ScrollView style={styles.list} showsVerticalScrollIndicator={false}>
            <View style={styles.fixedRow}>
              <Text style={styles.fixedLabel}>전체</Text>
              <Text style={styles.fixedBadge}>고정</Text>
            </View>
            {editable.map((name) => (
              <View key={name} style={styles.row}>
                <Text style={styles.rowLabel}>{name}</Text>
                <Pressable
                  hitSlop={8}
                  onPress={() => removeCategory(name)}
                  style={styles.removeBtn}>
                  <Icon name="trash" tintColor={ink(0.4)} size={16} />
                </Pressable>
              </View>
            ))}
          </ScrollView>

          <View style={styles.addRow}>
            <TextInput
              value={newName}
              onChangeText={setNewName}
              placeholder={addPlaceholder}
              placeholderTextColor={ink(0.35)}
              style={styles.addInput}
              returnKeyType="done"
              onSubmitEditing={addCategory}
            />
            <Pressable
              style={[styles.addBtn, !newName.trim() && styles.addBtnDisabled]}
              onPress={addCategory}
              disabled={!newName.trim()}>
              <Icon name="plus" tintColor="#fff" size={18} />
            </Pressable>
          </View>

          <View style={styles.actions}>
            <Pressable style={styles.cancelBtn} onPress={onClose}>
              <Text style={styles.cancelText}>취소</Text>
            </Pressable>
            <Pressable style={styles.saveBtn} onPress={handleSave}>
              <Text style={styles.saveText}>저장</Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(28,25,23,0.35)',
  },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingBottom: 32,
    maxHeight: '72%',
  },
  handle: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: ink(0.12),
    marginTop: 10,
    marginBottom: 16,
  },
  title: { fontSize: 17, fontWeight: '700', color: INK },
  hint: { fontSize: 12, color: ink(0.45), marginTop: 6, marginBottom: 16 },
  list: { flexGrow: 0, maxHeight: 280 },
  fixedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: ink(0.08),
  },
  fixedLabel: { fontSize: 15, fontWeight: '600', color: ink(0.5) },
  fixedBadge: {
    fontSize: 11,
    fontWeight: '600',
    color: ink(0.4),
    backgroundColor: '#f3ece2',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: ink(0.06),
  },
  rowLabel: { fontSize: 15, color: INK },
  removeBtn: { padding: 4 },
  addRow: { flexDirection: 'row', gap: 10, marginTop: 16 },
  addInput: {
    flex: 1,
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#f3ece2',
    fontSize: 14,
    color: INK,
  },
  addBtn: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addBtnDisabled: { opacity: 0.35 },
  actions: { flexDirection: 'row', gap: 10, marginTop: 20 },
  cancelBtn: {
    flex: 1,
    height: 48,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelText: { fontSize: 15, fontWeight: '600', color: ink(0.55) },
  saveBtn: {
    flex: 1,
    height: 48,
    borderRadius: 12,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveText: { fontSize: 15, fontWeight: '600', color: '#fff' },
});
