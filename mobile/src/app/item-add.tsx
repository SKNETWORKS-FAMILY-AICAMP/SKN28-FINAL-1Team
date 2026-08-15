import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PhotoSourceSheet } from '@/components/closet/photo-source-sheet';
import { Icon } from '@/components/icon';
import { ModalShell, useToast } from '@/components/ui';
import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { getMySharedRooms, type SharedRoom } from '@/lib/wardrobeApi';
import { draftItem, useDraftPhoto } from '@/state/draft-item';
import { uploadJobs } from '@/state/upload-jobs';

const INK = Editorial.ink;

export default function ItemAddScreen() {
  const { contentStyle } = useBreakpoint();
  const photo = useDraftPhoto();
  const toast = useToast();
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sharedRooms, setSharedRooms] = useState<SharedRoom[]>([]);
  const [shareEnabled, setShareEnabled] = useState(false);
  const [selectedRoomIds, setSelectedRoomIds] = useState<string[]>([]);
  const [roomPickerOpen, setRoomPickerOpen] = useState(false);

  useEffect(() => {
    getMySharedRooms()
      .then((rooms) => {
        setSharedRooms(rooms);
        if (rooms.length > 0) {
          setSelectedRoomIds([rooms[0].id]);
        }
      })
      .catch(() => setSharedRooms([]));
  }, []);

  const handleToggleRoom = (roomId: string) => {
    setSelectedRoomIds((prev) =>
      prev.includes(roomId) ? prev.filter((id) => id !== roomId) : [...prev, roomId]
    );
  };

  const close = () => {
    draftItem.setPhoto(null);
    router.replace('/(tabs)/closet');
  };

  const start = () => {
    if (!photo) {
      setSourceOpen(true);
      return;
    }
    const libraryItem = draftItem.getLibraryItem();
    /* 카탈로그에서 고른 옷은 이미 상품컷이라 누끼·태깅을 돌릴 게 없다 →
       skipProcessing 으로 서버가 그 자리에서 confirmed=True 아이템을 만든다.
       ⚠️ 이름 키는 `name` 이다. 예전엔 `itemName` 으로 넘겨서 — 스프레드라
       타입 검사도 안 걸리고 — 옷 이름이 조용히 버려졌다. */
    uploadJobs.start(photo, {
      sharedRoomIds: shareEnabled ? selectedRoomIds : undefined,
      sharedRoomId: shareEnabled ? selectedRoomIds[0] : undefined,
      ...(libraryItem
        ? { skipProcessing: true, name: libraryItem.name, category: libraryItem.category }
        : {}),
    });
    toast('등록을 시작했어요');
    close();
  };

  return (
    <ModalShell maxWidth={ContentMax.narrow}>
      <View style={styles.container}>
        <SafeAreaView edges={['top']} style={styles.headerSafe}>
          <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
            <View style={styles.headerText}>
              <Text style={styles.title}>아이템 등록</Text>
              <Text style={styles.subtitle}>등록을 시작하면 옷장에서 진행 상황을 볼 수 있어요</Text>
            </View>
            <Pressable hitSlop={12} onPress={close} accessibilityLabel="닫기">
              <Icon name="xmark" tintColor={ink(0.5)} size={18} />
            </Pressable>
          </View>
        </SafeAreaView>
        <View style={styles.divider} />

        <ScrollView contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
          {sharedRooms.length > 0 ? (
            <View style={styles.shareArea}>
              <View style={styles.shareHeader}>
                <Text style={styles.shareLabel}>공유 옷장</Text>
                <Pressable
                  style={[styles.switchContainer, shareEnabled && styles.switchContainerActive]}
                  onPress={() => setShareEnabled(!shareEnabled)}
                >
                  <View style={[styles.switchCircle, shareEnabled && styles.switchCircleActive]} />
                </Pressable>
              </View>

              {shareEnabled && (
                <View style={styles.dropdownWrapper}>
                  <Pressable
                    style={styles.dropdownHeader}
                    onPress={() => setRoomPickerOpen(!roomPickerOpen)}
                  >
                    <Text style={styles.dropdownSelectedText} numberOfLines={1}>
                      등록할 방 선택
                    </Text>
                    <Icon
                      name={roomPickerOpen ? 'chevron.up' : 'chevron.down'}
                      tintColor={Editorial.textCaption}
                      size={14}
                    />
                  </Pressable>
                  {roomPickerOpen && (
                    <View style={styles.dropdownList}>
                      {sharedRooms.map((room) => {
                        const checked = selectedRoomIds.includes(room.id);
                        return (
                          <Pressable
                            key={room.id}
                            style={[
                              styles.dropdownItem,
                              checked && styles.dropdownItemActive,
                            ]}
                            onPress={() => handleToggleRoom(room.id)}
                            accessibilityRole="checkbox"
                            accessibilityState={{ checked }}
                          >
                            <Text
                              style={[
                                styles.dropdownItemText,
                                checked && styles.dropdownItemTextActive,
                              ]}
                              numberOfLines={1}
                            >
                              {room.title}
                            </Text>
                            {checked ? (
                              <Icon name="checkmark" tintColor={Editorial.ink} size={13} />
                            ) : null}
                          </Pressable>
                        );
                      })}
                    </View>
                  )}
                </View>
              )}
            </View>
          ) : null}

          <Pressable style={styles.photo} onPress={() => setSourceOpen(true)}>
            {photo ? (
              <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} contentFit="cover" />
            ) : (
              <View style={styles.photoEmpty}>
                <Text style={styles.photoEmptyIcon}>＋</Text>
                <Text style={styles.photoEmptyText}>사진 추가하기</Text>
              </View>
            )}
          </Pressable>

          <Text style={styles.hint}>사진 한 장에 여러 벌이 있어도 괜찮아요. AI가 옷을 나눠 각각 등록해요.</Text>
        </ScrollView>

        <View style={styles.bottomDivider} />
        <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
          <Pressable style={[styles.primaryBtn, !photo && styles.primaryBtnOff]} onPress={start} disabled={!photo}>
            <Text style={styles.primaryText}>등록 시작</Text>
          </Pressable>
        </SafeAreaView>

        <PhotoSourceSheet visible={sourceOpen} onClose={() => setSourceOpen(false)} />
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  headerSafe: { backgroundColor: Editorial.page },
  header: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 14, paddingBottom: 12 },
  headerText: { flex: 1, gap: 4 },
  title: { fontSize: Type.lead, fontWeight: '700', color: INK },
  subtitle: { fontSize: Type.caption, color: Editorial.textCaption },
  divider: { height: 1, backgroundColor: ink(0.08) },
  content: { paddingHorizontal: 20, paddingTop: 18, paddingBottom: 24, gap: 14 },
  shareArea: {
    position: 'relative',
    zIndex: 100,
    elevation: 20,
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
  },
  shareHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  shareLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: INK,
  },
  switchContainer: {
    width: 44,
    height: 24,
    borderRadius: 999,
    backgroundColor: ink(0.12),
    padding: 2,
    justifyContent: 'center',
  },
  switchContainerActive: {
    backgroundColor: Editorial.ink,
  },
  switchCircle: {
    width: 20,
    height: 20,
    borderRadius: 999,
    backgroundColor: '#fff',
  },
  switchCircleActive: {
    alignSelf: 'flex-end',
  },
  dropdownWrapper: {
    position: 'relative',
    zIndex: 101,
  },
  dropdownHeader: {
    height: 38,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  dropdownSelectedText: {
    fontSize: 12,
    color: Editorial.ink,
    flex: 1,
  },
  dropdownList: {
    position: 'absolute',
    top: 44,
    left: 0,
    right: 0,
    borderRadius: 8,
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: Editorial.line,
    zIndex: 102,
    elevation: 24,
    maxHeight: 160,
    overflow: 'scroll',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
  },
  dropdownItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: Editorial.lineSoft,
    backgroundColor: Editorial.surface,
  },
  dropdownItemActive: {
    backgroundColor: Editorial.surfaceSoft,
  },
  dropdownItemText: {
    flex: 1,
    fontSize: 12,
    color: Editorial.textSoft,
  },
  dropdownItemTextActive: {
    fontWeight: '600',
    color: Editorial.ink,
  },
  photo: { zIndex: 0, height: 300, borderRadius: 16, overflow: 'hidden', backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  photoEmpty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 6 },
  photoEmptyIcon: { fontSize: 26, color: ink(0.35) },
  photoEmptyText: { fontSize: Type.footnote, color: Editorial.textCaption },
  hint: { fontSize: Type.caption, color: Editorial.textCaption, lineHeight: 19 },
  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { paddingHorizontal: 20, paddingTop: 12 },
  primaryBtn: { height: 52, borderRadius: 14, backgroundColor: Editorial.cta, alignItems: 'center', justifyContent: 'center' },
  primaryBtnOff: { opacity: 0.35 },
  primaryText: { fontSize: Type.label, fontWeight: '600', color: '#fff' },
});
