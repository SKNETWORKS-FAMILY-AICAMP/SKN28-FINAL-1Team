import { ActivityIndicator, Modal, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { Editorial, ink, Type } from '@/constants/theme';
import { SHARED_ITEM_STATUSES, SHARED_ITEM_STATUS_META } from '@/constants/shared-wardrobe';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import type { SharedItemStatus } from '@/lib/wardrobeApi';

export function SharedItemStatusSheet({
  visible,
  itemName,
  value,
  saving,
  onChange,
  onClose,
}: {
  visible: boolean;
  itemName: string;
  value: SharedItemStatus;
  saving: boolean;
  onChange: (status: SharedItemStatus) => void | Promise<void>;
  onClose: () => void;
}) {
  const { isDesktop } = useBreakpoint();
  const asDialog = Platform.OS === 'web' && isDesktop;

  return (
    <Modal
      visible={visible}
      transparent
      animationType={asDialog ? 'fade' : 'slide'}
      onRequestClose={() => {
        if (!saving) onClose();
      }}>
      <Pressable
        style={[styles.backdrop, asDialog && styles.backdropDialog]}
        onPress={() => {
          if (!saving) onClose();
        }}>
        <Pressable style={[styles.sheet, asDialog && styles.dialog]} onPress={(event) => event.stopPropagation()}>
          {asDialog ? null : <View style={styles.handle} />}
          <View style={styles.header}>
            <View style={styles.headerText}>
              <Text style={styles.title}>공유 상태</Text>
              <Text style={styles.subtitle} numberOfLines={1}>
                {itemName}
              </Text>
            </View>
            <Pressable
              hitSlop={12}
              disabled={saving}
              onPress={onClose}
              accessibilityLabel="공유 상태 닫기">
              <Icon name="xmark" tintColor={ink(0.5)} size={17} />
            </Pressable>
          </View>

          <View style={styles.options}>
            {SHARED_ITEM_STATUSES.map((status) => {
              const selected = status === value;
              const meta = SHARED_ITEM_STATUS_META[status];
              return (
                <Pressable
                  key={status}
                  style={[styles.option, selected && styles.optionSelected]}
                  disabled={saving}
                  onPress={() => onChange(status)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected, disabled: saving }}
                  accessibilityLabel={`${meta.label}, ${meta.description}`}>
                  <View style={[styles.radio, selected && styles.radioSelected]}>
                    {selected ? <Icon name="checkmark" tintColor="#fff" size={10} /> : null}
                  </View>
                  <View style={styles.optionText}>
                    <Text style={styles.optionTitle}>{meta.label}</Text>
                    <Text style={styles.optionDescription}>{meta.description}</Text>
                  </View>
                  {saving && selected ? <ActivityIndicator size="small" color={Editorial.ink} /> : null}
                </Pressable>
              );
            })}
          </View>
          <Text style={styles.policyNote}>내 옷장의 원본과 공유방 등록 자체는 상태를 바꿔도 유지됩니다.</Text>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(28,25,23,0.35)' },
  backdropDialog: { justifyContent: 'center', alignItems: 'center', paddingHorizontal: 24 },
  sheet: {
    backgroundColor: Editorial.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingBottom: 28,
  },
  dialog: {
    width: '100%',
    maxWidth: 420,
    borderRadius: 20,
    paddingTop: 24,
    shadowColor: Editorial.ink,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.14,
    shadowRadius: 32,
    elevation: 12,
  },
  handle: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: ink(0.12),
    marginTop: 10,
    marginBottom: 14,
  },
  header: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  headerText: { flex: 1, gap: 5 },
  title: { fontSize: Type.lead, fontWeight: '600', color: Editorial.ink },
  subtitle: { fontSize: Type.caption, color: Editorial.textCaption },
  options: { gap: 8, marginTop: 20 },
  option: {
    minHeight: 70,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
    backgroundColor: Editorial.surface,
  },
  optionSelected: { borderColor: Editorial.lineStrong },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Editorial.lineStrong,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioSelected: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  optionText: { flex: 1, gap: 3 },
  optionTitle: { fontSize: Type.footnote, fontWeight: '600', color: Editorial.ink },
  optionDescription: { fontSize: Type.micro, color: Editorial.textCaption, lineHeight: 17 },
  policyNote: {
    marginTop: 16,
    fontSize: Type.micro,
    lineHeight: 17,
    color: Editorial.textCaption,
    textAlign: 'center',
  },
});
