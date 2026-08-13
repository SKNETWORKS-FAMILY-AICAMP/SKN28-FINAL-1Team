/**
 * 공유 옷장에 내 옷 넣기 — 다중 선택 시트.
 *
 * 공유 옷장은 옷을 **소유하지 않는다.** `SharedWardrobeItem`은 내 `WardrobeItem`을
 * 가리키는 연결 레코드일 뿐이라(설계 명세 §2.3), 여기서 하는 일은 "새 옷 등록"이
 * 아니라 **이미 내 옷장에 있는 옷을 방에 연결**하는 것이다. 그래서 사진 업로드가
 * 아니라 목록에서 고르는 UI다.
 *
 * ⚠️ `confirmed=true` 인 옷만 보여준다.
 * 태깅 확정 전(`confirmed=false`) 옷은 추천 검색 대상에서 제외되기 때문에, 그대로
 * 공유하면 **방에는 보이는데 코디 추천에는 절대 안 잡히는 옷**이 된다.
 * (Confluence 'Shared Wardrobe' §4-3 — docstring에만 있고 코드엔 없던 가드)
 * 프론트만 막으면 API 로 뚫리므로 백엔드 가드도 함께 있어야 완결이다.
 */
import { Image } from 'expo-image';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { Editorial, ink, Type } from '@/constants/theme';
import {
  itemDisplayName,
  listWardrobeItems,
  registerItemToSharedRoom,
  type WardrobeApiItem,
} from '@/lib/wardrobeApi';

type Candidate = {
  id: string;
  name: string;
  image: string | null;
};

export function SharedItemAddSheet({
  visible,
  roomId,
  roomName,
  /** 이미 이 방에 올라가 있는 옷의 WardrobeItem id 목록 — 중복 노출을 막는다 */
  alreadySharedItemIds,
  onClose,
  onDone,
}: {
  visible: boolean;
  roomId: string;
  roomName: string;
  alreadySharedItemIds: string[];
  onClose: () => void;
  onDone: () => void | Promise<void>;
}) {
  const toast = useToast();
  const [items, setItems] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!visible) return;
    let alive = true;

    setLoading(true);
    setSelected([]);
    // confirmed=true 만 — 위 주석 참고
    listWardrobeItems({ confirmed: true })
      .then((list: WardrobeApiItem[]) => {
        if (!alive) return;
        const shared = new Set(alreadySharedItemIds);
        setItems(
          list
            .filter((it) => !shared.has(it.id))
            .map((it) => ({
              id: it.id,
              name: itemDisplayName(it),
              image: it.image_url ?? null,
            })),
        );
      })
      .catch(() => {
        if (alive) setItems([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [visible, alreadySharedItemIds]);

  const toggle = useCallback((id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }, []);

  const submit = async () => {
    if (!selected.length || saving) return;
    setSaving(true);

    /* 한 벌이 실패해도 나머지는 올린다 — 여러 벌 고른 사용자에게 전량 재시도를
       시키지 않는다 (일괄 등록 설계의 부분 실패 허용과 같은 판단). */
    const results = await Promise.allSettled(
      selected.map((itemId) => registerItemToSharedRoom(roomId, itemId)),
    );
    const failed = results.filter((r) => r.status === 'rejected').length;
    const ok = results.length - failed;

    setSaving(false);

    if (ok) toast(`${ok}벌을 ${roomName}에 공유했어요`, { variant: 'success' });
    if (failed) {
      toast(`${failed}벌은 공유하지 못했어요`, { variant: 'error' });
    }
    if (ok) {
      await onDone();
      onClose();
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.header}>
            <View style={styles.headerText}>
              <Text style={styles.title}>내 옷 공유하기</Text>
              <Text style={styles.subtitle}>{roomName}</Text>
            </View>
            <Pressable onPress={onClose} hitSlop={8}>
              <Icon name="xmark" tintColor={ink(0.5)} size={18} />
            </Pressable>
          </View>

          {loading ? (
            <View style={styles.center}>
              <ActivityIndicator />
            </View>
          ) : items.length === 0 ? (
            <View style={styles.center}>
              <Text style={styles.emptyText}>
                공유할 수 있는 옷이 없어요.{'\n'}
                태그를 확인한 옷만 공유할 수 있어요.
              </Text>
            </View>
          ) : (
            <ScrollView contentContainerStyle={styles.grid}>
              {items.map((it) => {
                const on = selected.includes(it.id);
                return (
                  <Pressable
                    key={it.id}
                    style={[styles.tile, on && styles.tileOn]}
                    onPress={() => toggle(it.id)}>
                    {it.image ? (
                      <Image source={{ uri: it.image }} style={styles.thumb} contentFit="cover" />
                    ) : (
                      <View style={[styles.thumb, styles.thumbEmpty]} />
                    )}
                    {on ? (
                      <View style={styles.check}>
                        <Icon name="checkmark" tintColor="#fff" size={12} />
                      </View>
                    ) : null}
                    <Text style={styles.tileName} numberOfLines={1}>
                      {it.name}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>
          )}

          <Pressable
            style={[styles.submitBtn, (!selected.length || saving) && styles.submitBtnOff]}
            onPress={submit}
            disabled={!selected.length || saving}>
            <Text style={styles.submitText}>
              {saving ? '공유하는 중…' : selected.length ? `${selected.length}벌 공유하기` : '옷을 선택해 주세요'}
            </Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: Editorial.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 28,
    maxHeight: '80%',
  },
  header: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 16 },
  headerText: { flex: 1 },
  title: { fontSize: Type.label, fontWeight: '600', color: Editorial.ink },
  subtitle: { fontSize: Type.footnote, color: Editorial.textCaption, marginTop: 4 },
  center: { paddingVertical: 48, alignItems: 'center' },
  emptyText: { fontSize: Type.footnote, color: Editorial.textCaption, textAlign: 'center', lineHeight: 20 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingBottom: 12 },
  tile: { width: '30%', borderRadius: 12, overflow: 'hidden' },
  tileOn: { opacity: 0.95 },
  thumb: { width: '100%', aspectRatio: 1, borderRadius: 12, backgroundColor: Editorial.surfaceSoft },
  thumbEmpty: { borderWidth: 1, borderColor: Editorial.line },
  check: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: Editorial.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tileName: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 6 },
  submitBtn: {
    marginTop: 8,
    height: 48,
    borderRadius: 12,
    backgroundColor: Editorial.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitBtnOff: { opacity: 0.4 },
  submitText: { fontSize: Type.footnote, fontWeight: '600', color: '#fff' },
});
