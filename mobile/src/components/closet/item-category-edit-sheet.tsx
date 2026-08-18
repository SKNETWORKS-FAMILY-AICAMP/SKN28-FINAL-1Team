import { Icon } from '@/components/icon';
import { Editorial, Type } from '@/constants/theme';
import type {
  WardrobeCategorySummary,
  WardrobeCustomCategory,
} from '@/lib/wardrobeApi';
import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

type ItemCategoryEditSheetProps = {
  visible: boolean;
  categories: WardrobeCustomCategory[];
  selectedCategories: WardrobeCategorySummary[];
  loading: boolean;
  onClose: () => void;
  onSave: (categoryIds: string[]) => Promise<boolean>;
};

function sameIds(left: Set<string>, right: Set<string>): boolean {
  return left.size === right.size && [...left].every((id) => right.has(id));
}

export function ItemCategoryEditSheet({
  visible,
  categories,
  selectedCategories,
  loading,
  onClose,
  onSave,
}: ItemCategoryEditSheetProps) {
  const [initialSelected, setInitialSelected] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!visible) return;
    const next = new Set(selectedCategories.map((category) => category.id));
    // 상세 응답의 현재 소속을 열 때마다 편집 초안의 기준으로 삼는다.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInitialSelected(next);
    setSelected(new Set(next));
  }, [selectedCategories, visible]);

  const changed = useMemo(
    () => !sameIds(initialSelected, selected),
    [initialSelected, selected],
  );

  const toggle = (categoryId: string) => {
    if (saving) return;
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(categoryId)) next.delete(categoryId);
      else next.add(categoryId);
      return next;
    });
  };

  const close = () => {
    if (!saving) onClose();
  };

  const save = async () => {
    if (!changed || loading) return;
    setSaving(true);
    try {
      const saved = await onSave(
        categories.filter((category) => selected.has(category.id)).map((category) => category.id),
      );
      if (saved) onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
      <Pressable style={styles.backdrop} onPress={close}>
        <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
          <View style={styles.handle} />
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <Text style={styles.eyebrow}>아이템 상세</Text>
              <Text style={styles.title}>내 카테고리 편집</Text>
              <Text style={styles.description}>
                여러 카테고리에 동시에 넣을 수 있어요.
              </Text>
            </View>
            <Pressable
              style={styles.closeButton}
              hitSlop={8}
              onPress={close}
              accessibilityLabel="카테고리 편집 닫기">
              <Icon name="xmark" tintColor={Editorial.textCaption} size={16} />
            </Pressable>
          </View>

          <ScrollView
            style={styles.list}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}>
            {loading ? (
              <View style={styles.state}>
                <ActivityIndicator color={Editorial.ink} />
                <Text style={styles.stateText}>카테고리를 불러오는 중…</Text>
              </View>
            ) : categories.length === 0 ? (
              <View style={styles.state}>
                <Icon name="archivebox" tintColor={Editorial.textMuted} size={28} />
                <Text style={styles.emptyTitle}>만든 카테고리가 아직 없어요</Text>
                <Text style={styles.stateText}>
                  옷장 필터의 카테고리 관리에서 먼저 만들어 주세요.
                </Text>
              </View>
            ) : (
              categories.map((category) => {
                const active = selected.has(category.id);
                return (
                  <Pressable
                    key={category.id}
                    style={[styles.row, active && styles.rowSelected]}
                    onPress={() => toggle(category.id)}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: active }}
                    accessibilityLabel={`${category.name} ${active ? '선택됨' : '선택 안 됨'}`}>
                    <View style={styles.rowCopy}>
                      <Text style={[styles.rowName, active && styles.rowNameSelected]}>
                        {category.name}
                      </Text>
                      <Text style={styles.rowMeta}>{category.item_count}벌</Text>
                    </View>
                    <View style={[styles.checkbox, active && styles.checkboxSelected]}>
                      {active ? (
                        <Icon name="checkmark" tintColor={Editorial.white} size={13} />
                      ) : null}
                    </View>
                  </Pressable>
                );
              })
            )}
          </ScrollView>

          <View style={styles.actions}>
            <Pressable style={styles.cancelButton} onPress={close} disabled={saving}>
              <Text style={styles.cancelText}>취소</Text>
            </Pressable>
            <Pressable
              style={[
                styles.saveButton,
                (!changed || loading || saving) && styles.saveButtonDisabled,
              ]}
              onPress={save}
              disabled={!changed || loading || saving}>
              {saving ? (
                <ActivityIndicator color={Editorial.white} size="small" />
              ) : (
                <Text style={styles.saveText}>선택 저장</Text>
              )}
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
    alignItems: 'center',
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(28,25,23,0.35)',
  },
  sheet: {
    width: '100%',
    maxWidth: 440,
    maxHeight: '82%',
    paddingHorizontal: 20,
    paddingBottom: 28,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    backgroundColor: Editorial.surface,
  },
  handle: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    marginTop: 10,
    marginBottom: 16,
    borderRadius: 2,
    backgroundColor: Editorial.line,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 16,
  },
  headerCopy: { flex: 1 },
  eyebrow: {
    marginBottom: 3,
    fontSize: Type.micro,
    fontWeight: '600',
    color: Editorial.textCaption,
  },
  title: { fontSize: 20, fontWeight: '700', color: Editorial.ink },
  description: { marginTop: 6, fontSize: Type.caption, color: Editorial.textSoft },
  closeButton: {
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 10,
    backgroundColor: Editorial.control,
  },
  list: { flexGrow: 0 },
  listContent: { gap: 8, paddingBottom: 8 },
  row: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 14,
    backgroundColor: Editorial.surface,
  },
  rowSelected: { borderColor: Editorial.lineStrong },
  rowCopy: { flex: 1 },
  rowName: { fontSize: Type.body, fontWeight: '500', color: Editorial.textSoft },
  rowNameSelected: { fontWeight: '600', color: Editorial.ink },
  rowMeta: { marginTop: 3, fontSize: Type.micro, color: Editorial.textCaption },
  checkbox: {
    width: 24,
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: Editorial.lineStrong,
    borderRadius: 12,
  },
  checkboxSelected: {
    borderColor: Editorial.selected,
    backgroundColor: Editorial.selected,
  },
  state: {
    minHeight: 180,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  emptyTitle: {
    marginTop: 12,
    fontSize: Type.label,
    fontWeight: '600',
    color: Editorial.ink,
  },
  stateText: {
    marginTop: 6,
    fontSize: Type.caption,
    lineHeight: 19,
    textAlign: 'center',
    color: Editorial.textCaption,
  },
  actions: {
    flexDirection: 'row',
    gap: 10,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: Editorial.lineSoft,
  },
  cancelButton: {
    flex: 1,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 12,
  },
  cancelText: { fontSize: Type.body, fontWeight: '600', color: Editorial.textCaption },
  saveButton: {
    flex: 1,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: Editorial.cta,
  },
  saveButtonDisabled: { opacity: 0.35 },
  saveText: { fontSize: Type.body, fontWeight: '600', color: Editorial.white },
});
