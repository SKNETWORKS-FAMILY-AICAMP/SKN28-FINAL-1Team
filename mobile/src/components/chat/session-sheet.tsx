import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Icon } from '@/components/icon';
import { useConfirm, useToast } from '@/components/ui';
import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { chatStore, type ChatSession } from '@/state/chat';

const INK = Editorial.ink;

type ChatSessionSheetProps = {
  visible: boolean;
  session: ChatSession | undefined;
  onClose: () => void;
  /** 삭제된 뒤 할 일 — 대화 화면은 목록으로 돌아가야 한다. */
  onDeleted?: () => void;
};

/**
 * 대화 하나를 관리하는 시트 — 이름 변경과 삭제.
 * 이름은 입력창에 바로 담아 둔다(따로 '이름 변경' 단계를 거치지 않게).
 */
export function ChatSessionSheet({
  visible,
  session,
  onClose,
  onDeleted,
}: ChatSessionSheetProps) {
  const [draft, setDraft] = useState(session?.title ?? '');
  const { isDesktop } = useBreakpoint();
  const confirm = useConfirm();
  const toast = useToast();

  /* 시트를 열 때(또는 다른 대화로 바꿔 열 때) 입력값을 그 대화의 이름으로 되돌린다.
     effect 가 아니라 렌더 중에 맞추므로, 여는 순간 한 프레임 옛 이름이 스치지 않는다. */
  const openedFor = visible ? session?.id ?? null : null;
  const [shownFor, setShownFor] = useState(openedFor);
  if (openedFor !== shownFor) {
    setShownFor(openedFor);
    setDraft(session?.title ?? '');
  }

  if (!session) return null;

  const trimmed = draft.trim();
  const canSave = trimmed.length > 0 && trimmed !== session.title;

  const handleSave = () => {
    chatStore.renameSession(session.id, trimmed);
    toast('대화 이름을 바꿨어요', { variant: 'success' });
    onClose();
  };

  const handleDelete = async () => {
    /* 시트를 먼저 닫는다 — 모달 위에 모달을 띄우면 iOS 에서 확인창이 나타나지 않는다. */
    onClose();
    const ok = await confirm({
      title: '이 대화를 삭제할까요?',
      message: '주고받은 대화가 모두 사라져요.',
      confirmLabel: '삭제',
      destructive: true,
    });
    if (!ok) return;
    chatStore.removeSession(session.id);
    toast('대화를 삭제했어요', { variant: 'success' });
    onDeleted?.();
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable
          style={[styles.sheet, isDesktop && styles.sheetDesktop]}
          onPress={(e) => e.stopPropagation()}>
          <View style={styles.handle} />
          <Text style={styles.title}>대화 관리</Text>

          <Text style={styles.fieldLabel}>이름</Text>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="대화 이름"
            placeholderTextColor={ink(0.35)}
            style={styles.input}
            returnKeyType="done"
            onSubmitEditing={() => canSave && handleSave()}
          />

          <Pressable style={styles.deleteRow} onPress={handleDelete}>
            <Icon name="trash" tintColor={Editorial.danger} size={17} />
            <Text style={styles.deleteText}>대화 삭제</Text>
          </Pressable>

          <View style={styles.actions}>
            <Pressable style={styles.cancelBtn} onPress={onClose}>
              <Text style={styles.cancelText}>취소</Text>
            </Pressable>
            <Pressable
              style={[styles.saveBtn, !canSave && styles.saveBtnDisabled]}
              onPress={handleSave}
              disabled={!canSave}>
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
    backgroundColor: Editorial.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingBottom: 32,
  },
  /* 데스크톱에선 창 폭을 다 쓰지 않는다 — 모드 카드가 놓이는 열과 같은 폭으로 맞춘다. */
  sheetDesktop: {
    width: '100%',
    maxWidth: ContentMax.narrow,
    marginHorizontal: 'auto',
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    marginBottom: 24,
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
  title: { fontSize: Type.lead, fontWeight: '700', color: INK },

  fieldLabel: { fontSize: Type.caption, color: Editorial.textCaption, marginTop: 20, marginBottom: 8 },
  input: {
    height: 46,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: Editorial.line,
    fontSize: Type.body,
    color: INK,
  },

  deleteRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    marginTop: 20,
    paddingVertical: 14,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  deleteText: { fontSize: Type.body, fontWeight: '600', color: Editorial.danger },

  actions: { flexDirection: 'row', gap: 10, marginTop: 12 },
  cancelBtn: {
    flex: 1,
    height: 48,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelText: { fontSize: Type.body, fontWeight: '600', color: Editorial.textCaption },
  saveBtn: {
    flex: 1,
    height: 48,
    borderRadius: 12,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnDisabled: { opacity: 0.35 },
  saveText: { fontSize: Type.body, fontWeight: '600', color: '#fff' },
});
