import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View, ActivityIndicator } from 'react-native';
import { Image } from 'expo-image';
import { Icon } from '@/components/icon';
import { listWardrobeItems, getMySharedRooms, listSharedRoomItems } from '@/lib/wardrobeApi';
import { Editorial, ink } from '@/constants/theme';

export function ClosetItemSelectSheet({
  visible,
  onClose,
  onSelect,
}: {
  visible: boolean;
  onClose: () => void;
  onSelect: (selected: { id: string; image: string; name: string }[]) => void;
}) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'mine' | 'shared'>('mine');
  const [sharedItems, setSharedItems] = useState<any[]>([]);

  useEffect(() => {
    if (visible) {
      setLoading(true);
      setSelectedIds([]);
      
      Promise.all([
        listWardrobeItems().catch(() => []),
        getMySharedRooms()
          .then(async (rooms) => {
            const allShared: any[] = [];
            for (const r of rooms || []) {
              try {
                const sItems = await listSharedRoomItems(r.id);
                sItems.forEach((si) => {
                  allShared.push({
                    id: si.id,
                    image: si.wardrobe_item.image_url || si.wardrobe_item.image,
                    name: si.wardrobe_item.item_name || si.wardrobe_item.category_large,
                    owner: si.registered_by?.nickname || '멤버',
                  });
                });
              } catch (e) {
                console.error(e);
              }
            }
            return allShared;
          })
          .catch(() => []),
      ])
        .then(([mine, shared]) => {
          setItems(
            mine.map((it: any) => ({
              id: it.id,
              image: it.image_url || it.image,
              name: it.item_name || it.category_large,
            }))
          );
          setSharedItems(shared);
        })
        .finally(() => setLoading(false));
    }
  }, [visible]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleConfirm = () => {
    const list = activeTab === 'mine' ? items : sharedItems;
    const selected = list
      .filter((it) => selectedIds.includes(it.id))
      .map((it) => ({
        id: it.id,
        image: it.image,
        name: it.name,
      }));
    onSelect(selected);
    onClose();
  };

  const displayList = activeTab === 'mine' ? items : sharedItems;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.handle} />
          
          <View style={styles.header}>
            <Text style={styles.title}>옷장에서 가져오기</Text>
            <Pressable hitSlop={12} onPress={onClose}>
              <Icon name="xmark" tintColor={ink(0.5)} size={16} />
            </Pressable>
          </View>

          {/* 탭 전환 */}
          <View style={styles.tabRow}>
            <Pressable
              style={[styles.tab, activeTab === 'mine' && styles.tabActive]}
              onPress={() => {
                setActiveTab('mine');
                setSelectedIds([]);
              }}
            >
              <Text style={[styles.tabText, activeTab === 'mine' && styles.tabTextActive]}>
                내 옷장 ({items.length})
              </Text>
            </Pressable>
            <Pressable
              style={[styles.tab, activeTab === 'shared' && styles.tabActive]}
              onPress={() => {
                setActiveTab('shared');
                setSelectedIds([]);
              }}
            >
              <Text style={[styles.tabText, activeTab === 'shared' && styles.tabTextActive]}>
                공유 옷장 ({sharedItems.length})
              </Text>
            </Pressable>
          </View>

          {loading ? (
            <ActivityIndicator style={styles.loader} color={Editorial.cta} />
          ) : displayList.length === 0 ? (
            <Text style={styles.emptyText}>등록된 옷이 없거나 불러오지 못했어요.</Text>
          ) : (
            <ScrollView contentContainerStyle={styles.grid} showsVerticalScrollIndicator={false}>
              {displayList.map((it) => {
                const isSelected = selectedIds.includes(it.id);
                return (
                  <Pressable
                    key={it.id}
                    style={[styles.card, isSelected && styles.cardSelected]}
                    onPress={() => toggleSelect(it.id)}
                  >
                    <Image source={{ uri: it.image }} style={styles.thumb} contentFit="cover" />
                    {isSelected && (
                      <View style={styles.checkedBadge}>
                        <Icon name="checkmark" tintColor="#FFFFFF" size={10} />
                      </View>
                    )}
                    <View style={styles.meta}>
                      <Text style={styles.cardName} numberOfLines={1}>
                        {it.name}
                      </Text>
                      {it.owner && (
                        <Text style={styles.cardOwner} numberOfLines={1}>
                          {it.owner}
                        </Text>
                      )}
                    </View>
                  </Pressable>
                );
              })}
            </ScrollView>
          )}

          <View style={styles.footer}>
            <Pressable
              style={[styles.confirmBtn, selectedIds.length === 0 && styles.confirmBtnDisabled]}
              disabled={selectedIds.length === 0}
              onPress={handleConfirm}
            >
              <Text style={styles.confirmText}>
                {selectedIds.length > 0 ? `${selectedIds.length}개 옷 선택 완료` : '선택 완료'}
              </Text>
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
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: Editorial.page,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '80%',
    minHeight: '50%',
    paddingBottom: 24,
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
    color: ink(0.9),
  },
  tabRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: Editorial.line,
    paddingHorizontal: 20,
    marginBottom: 14,
  },
  tab: {
    paddingVertical: 10,
    marginRight: 20,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: Editorial.cta,
  },
  tabText: {
    fontSize: 13,
    color: Editorial.textCaption,
    fontWeight: '600',
  },
  tabTextActive: {
    color: Editorial.cta,
  },
  loader: {
    marginVertical: 40,
  },
  emptyText: {
    fontSize: 13,
    color: Editorial.textCaption,
    textAlign: 'center',
    marginVertical: 40,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  card: {
    width: '31%',
    aspectRatio: 0.8,
    borderRadius: 10,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1,
    borderColor: Editorial.line,
    overflow: 'hidden',
    position: 'relative',
  },
  cardSelected: {
    borderColor: Editorial.cta,
    borderWidth: 2,
  },
  thumb: {
    width: '100%',
    height: '70%',
    backgroundColor: '#fff',
  },
  checkedBadge: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  meta: {
    paddingHorizontal: 6,
    paddingVertical: 4,
    height: '30%',
    justifyContent: 'center',
  },
  cardName: {
    fontSize: 10,
    fontWeight: '600',
    color: Editorial.ink,
  },
  cardOwner: {
    fontSize: 8,
    color: Editorial.textCaption,
    marginTop: 1,
  },
  footer: {
    paddingHorizontal: 20,
    marginTop: 10,
  },
  confirmBtn: {
    height: 48,
    borderRadius: 12,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  confirmBtnDisabled: {
    opacity: 0.5,
  },
  confirmText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});
