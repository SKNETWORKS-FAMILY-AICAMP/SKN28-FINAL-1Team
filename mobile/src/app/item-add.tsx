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
  const [selectedRoomId, setSelectedRoomId] = useState('');
  const [roomPickerOpen, setRoomPickerOpen] = useState(false);

  useEffect(() => {
    getMySharedRooms()
      .then((rooms) => {
        setSharedRooms(rooms);
        setSelectedRoomId(rooms[0]?.id ?? '');
      })
      .catch(() => setSharedRooms([]));
  }, []);

  const close = () => {
    draftItem.setPhoto(null);
    router.replace('/(tabs)/closet');
  };

  const start = () => {
    if (!photo) {
      setSourceOpen(true);
      return;
    }
    uploadJobs.start(photo, { sharedRoomId: shareEnabled ? selectedRoomId : undefined });
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
              <View style={styles.shareRow}>
                <View style={styles.shareToggleWrap}>
                  <Text style={styles.shareLabel} numberOfLines={1}>공유 옷장에 공유</Text>
                  <Pressable
                    style={[styles.switch, shareEnabled && styles.switchOn]}
                    onPress={() => {
                      setShareEnabled((enabled) => !enabled);
                      setRoomPickerOpen(false);
                    }}>
                    <View style={[styles.switchKnob, shareEnabled && styles.switchKnobOn]} />
                  </Pressable>
                </View>
                <View style={styles.roomPickerWrap}>
                  <Pressable
                    style={[styles.roomPicker, !shareEnabled && styles.roomPickerDisabled]}
                    onPress={() => setRoomPickerOpen((open) => !open)}
                    disabled={!shareEnabled}>
                    <Text style={styles.roomPickerText} numberOfLines={1}>
                      {shareEnabled
                        ? sharedRooms.find((room) => room.id === selectedRoomId)?.title ?? '방 선택'
                        : '등록할 방 선택'}
                    </Text>
                    <Icon
                      name={roomPickerOpen ? 'chevron.up' : 'chevron.down'}
                      tintColor={shareEnabled ? Editorial.textCaption : ink(0.25)}
                      size={15}
                    />
                  </Pressable>
                  {shareEnabled && roomPickerOpen ? (
                    <ScrollView
                      style={styles.roomMenu}
                      nestedScrollEnabled
                      showsVerticalScrollIndicator={sharedRooms.length > 4}>
                      {sharedRooms.map((room) => (
                        <Pressable
                          key={room.id}
                          style={[styles.roomOption, selectedRoomId === room.id && styles.roomOptionSelected]}
                          onPress={() => {
                            setSelectedRoomId(room.id);
                            setRoomPickerOpen(false);
                          }}>
                          <Text style={[styles.roomOptionText, selectedRoomId === room.id && styles.roomOptionTextSelected]}>
                            {room.title}
                          </Text>
                        </Pressable>
                      ))}
                    </ScrollView>
                  ) : null}
                </View>
              </View>
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
  shareArea: { position: 'relative', zIndex: 20, elevation: 20, overflow: 'visible', borderWidth: 1, borderColor: Editorial.line, borderRadius: 14, padding: 14, gap: 12 },
  shareRow: { position: 'relative', zIndex: 20, flexDirection: 'row', alignItems: 'center', gap: 9 },
  shareToggleWrap: { flex: 4, minWidth: 0, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-start', gap: 8 },
  shareLabel: { flexShrink: 1, fontSize: Type.footnote, fontWeight: '600', color: INK },
  switch: { width: 42, height: 24, borderRadius: 12, backgroundColor: ink(0.16), padding: 2, justifyContent: 'center' },
  switchOn: { backgroundColor: '#34C759' },
  switchKnob: { width: 20, height: 20, borderRadius: 10, backgroundColor: '#fff' },
  switchKnobOn: { alignSelf: 'flex-end' },
  roomPickerWrap: { position: 'relative', zIndex: 30, flex: 6, minWidth: 0 },
  roomPicker: {
    height: 38,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 10,
    backgroundColor: Editorial.surfaceSoft,
  },
  roomPickerDisabled: { backgroundColor: ink(0.04) },
  roomPickerText: { flex: 1, marginRight: 8, fontSize: Type.footnote, color: INK },
  roomMenu: {
    position: 'absolute',
    zIndex: 40,
    elevation: 40,
    top: 42,
    right: 0,
    left: 0,
    maxHeight: 160,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 10,
    backgroundColor: Editorial.surface,
  },
  roomOption: { paddingHorizontal: 12, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: Editorial.lineSoft },
  roomOptionSelected: { backgroundColor: Editorial.surfaceSoft },
  roomOptionText: { fontSize: Type.footnote, color: Editorial.textSoft },
  roomOptionTextSelected: { fontWeight: '700', color: INK },
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
