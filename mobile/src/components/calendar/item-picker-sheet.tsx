import { useMemo, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { SmartImage } from '@/components/ui';
import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { WARDROBE_SOURCES, type WardrobeSource } from '@/constants/wardrobe';
import { entryItemKey, toEntryItem, type EntryItem } from '@/state/calendar';

const INK = Editorial.ink;
const GAP = 10;
const COLUMNS = 3;

/**
 * 옷 고르기 — 소스(내 옷장 / 앱 추천 / 친구 옷장)를 탭으로 전환하는 단일 시트.
 *
 * 소스를 화면 분기로 두지 않는 이유: 한 착장에 여러 소스의 옷이 섞이는 게 정상이라
 * 소스마다 화면을 나가고 들어오면 한 벌을 꾸리는 데 왕복이 너무 많아진다.
 */
export function ItemPickerSheet({
  visible,
  selected,
  onClose,
  onConfirm,
}: {
  visible: boolean;
  /** 현재 기록에 담긴 옷 — 다시 열었을 때 체크 상태로 복원된다 */
  selected: EntryItem[];
  onClose: () => void;
  onConfirm: (items: EntryItem[]) => void;
}) {
  const [tab, setTab] = useState<WardrobeSource>('closet');
  const [draft, setDraft] = useState<EntryItem[]>(selected);
  const [gridWidth, setGridWidth] = useState(0);
  const [wasVisible, setWasVisible] = useState(visible);

  // 시트를 열 때마다 바깥 상태로 초기화 — 취소하고 닫으면 아무것도 반영되지 않아야 한다.
  // (effect 가 아니라 렌더 중 조정: 열자마자 옛 선택이 한 프레임 비치지 않는다)
  if (visible !== wasVisible) {
    setWasVisible(visible);
    if (visible) setDraft(selected);
  }

  const source = WARDROBE_SOURCES.find((s) => s.key === tab)!;
  const selectedKeys = useMemo(() => new Set(draft.map(entryItemKey)), [draft]);
  const cellWidth = gridWidth > 0 ? (gridWidth - GAP * (COLUMNS - 1)) / COLUMNS : 0;

  const toggle = (itemId: string) => {
    const item = source.items.find((i) => i.id === itemId)!;
    const key = entryItemKey({ source: tab, id: itemId });
    setDraft((prev) =>
      prev.some((p) => entryItemKey(p) === key)
        ? prev.filter((p) => entryItemKey(p) !== key)
        : [...prev, toEntryItem(item, tab)],
    );
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.handle} />
          <Text style={styles.title}>옷 고르기</Text>

          <View style={styles.tabs}>
            {WARDROBE_SOURCES.map((s) => {
              const on = s.key === tab;
              return (
                <Pressable
                  key={s.key}
                  style={[styles.tab, on && styles.tabOn]}
                  onPress={() => setTab(s.key)}>
                  <Text style={[styles.tabText, on && styles.tabTextOn]}>{s.label}</Text>
                </Pressable>
              );
            })}
          </View>

          <ScrollView showsVerticalScrollIndicator={false} style={styles.scroll}>
            <View
              style={styles.grid}
              onLayout={(e) => setGridWidth(e.nativeEvent.layout.width)}>
              {cellWidth > 0
                ? source.items.map((item) => {
                    const on = selectedKeys.has(entryItemKey({ source: tab, id: item.id }));
                    return (
                      <Pressable
                        key={item.id}
                        style={{ width: cellWidth }}
                        onPress={() => toggle(item.id)}>
                        <View style={[styles.thumbWrap, on && styles.thumbWrapOn]}>
                          <SmartImage uri={item.image} width="100%" aspectRatio={1} radius={12} />
                          {on ? (
                            <View style={styles.check}>
                              <Icon name="checkmark" tintColor="#fff" size={13} />
                            </View>
                          ) : null}
                        </View>
                        <Text style={styles.itemName} numberOfLines={1}>
                          {item.name}
                        </Text>
                        <Text style={styles.itemMeta} numberOfLines={1}>
                          {item.owner ? `${item.owner}님` : (item.brand ?? item.category)}
                        </Text>
                      </Pressable>
                    );
                  })
                : null}
            </View>
          </ScrollView>

          <Pressable
            style={styles.confirmBtn}
            onPress={() => {
              onConfirm(draft);
              onClose();
            }}>
            <Text style={styles.confirmText}>
              {draft.length > 0 ? `${draft.length}개 담기` : '닫기'}
            </Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: ink(0.35) },
  sheet: {
    width: '100%',
    maxWidth: ContentMax.narrow,
    alignSelf: 'center',
    backgroundColor: Editorial.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingBottom: 28,
    maxHeight: '82%',
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

  tabs: { flexDirection: 'row', gap: 8, marginTop: 16, marginBottom: 14 },
  tab: {
    paddingHorizontal: 14,
    height: 34,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  tabText: { fontSize: Type.caption, fontWeight: '600', color: Editorial.textCaption },
  tabTextOn: { color: '#fff' },

  scroll: { flexGrow: 0 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: GAP, paddingBottom: 8 },
  thumbWrap: { borderRadius: 12, borderWidth: 1, borderColor: Editorial.lineSoft, overflow: 'hidden' },
  thumbWrapOn: { borderWidth: 2, borderColor: Editorial.selected },
  check: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: Editorial.selected,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemName: { fontSize: Type.micro, color: INK, marginTop: 6 },
  itemMeta: { fontSize: Type.micro, color: Editorial.textMuted, marginTop: 1 },

  confirmBtn: {
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
  },
  confirmText: { fontSize: Type.body, fontWeight: '600', color: '#fff' },
});
