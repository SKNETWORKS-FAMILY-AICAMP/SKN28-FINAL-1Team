import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PhotoSourceSheet } from '@/components/closet/photo-source-sheet';
import { Icon } from '@/components/icon';
import { ModalShell, useToast } from '@/components/ui';
import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { draftItem, useDraftPhotos } from '@/state/draft-item';
import { uploadJobs } from '@/state/upload-jobs';
import { getMySharedRooms, type SharedRoom } from '@/lib/wardrobeApi';

const INK = Editorial.ink;

export default function ItemAddScreen() {
  const { contentStyle } = useBreakpoint();
  const draftPhotos = useDraftPhotos();
  const toast = useToast();
  const [sourceOpen, setSourceOpen] = useState(false);

  // 멀티 갤러리 이미지 상태 (최대 3장)
  const [photos, setPhotos] = useState<string[]>([]);

  // 공유 옷장 방 상태
  const [sharedRooms, setSharedRooms] = useState<SharedRoom[]>([]);
  const [shareEnabled, setShareEnabled] = useState(false);
  const [selectedRoomId, setSelectedRoomId] = useState<string>('');
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // 드래프트 포토 어레이가 업데이트되면 동기화
  useEffect(() => {
    if (draftPhotos && draftPhotos.length > 0) {
      setPhotos((prev) => {
        const merged = [...prev];
        draftPhotos.forEach((dp) => {
          if (!merged.includes(dp) && merged.length < 3) {
            merged.push(dp);
          }
        });
        return merged;
      });
      // 동기화 후 드래프트 비우기
      draftItem.clear();
    }
  }, [draftPhotos]);

  useEffect(() => {
    getMySharedRooms()
      .then((rooms) => {
        setSharedRooms(rooms || []);
        if (rooms && rooms.length > 0) {
          setSelectedRoomId(rooms[0].id);
        }
      })
      .catch(() => {});
  }, []);

  const close = () => {
    draftItem.clear();
    router.replace('/(tabs)/closet');
  };

  const removePhoto = (index: number) => {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
  };

  const start = () => {
    if (photos.length === 0) {
      setSourceOpen(true);
      return;
    }
    // 배치 프로그레스 등록
    uploadJobs.startBatch(photos.length);
    toast(`${photos.length}장의 옷 등록을 시작했어요`);
    close();

    // 백그라운드에서 하나가 완전히 끝난 후 다음 등록을 시작하도록 순차 큐 제어
    (async () => {
      for (let i = 0; i < photos.length; i++) {
        await uploadJobs.start(photos[i], {
          sharedRoomId: shareEnabled ? selectedRoomId : undefined,
        });
      }
    })();
  };

  return (
    <ModalShell maxWidth={ContentMax.narrow}>
      <View style={styles.container}>
        <SafeAreaView edges={['top']} style={styles.headerSafe}>
          <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
            <View style={styles.headerText}>
              <Text style={styles.title}>아이템 등록 ({photos.length}/3)</Text>
              <Text style={styles.subtitle}>
                등록 완료 시 옷장 위쪽 진행 바가 채워집니다
              </Text>
            </View>
            <View style={styles.headerRight}>
              <Pressable
                style={[styles.headerBtn, photos.length === 0 && styles.headerBtnOff]}
                onPress={start}
                disabled={photos.length === 0}
              >
                <Text style={styles.headerBtnText}>등록 시작</Text>
              </Pressable>
              <Pressable hitSlop={12} onPress={close} accessibilityLabel="닫기">
                <Icon name="xmark" tintColor={ink(0.5)} size={18} />
              </Pressable>
            </View>
          </View>
        </SafeAreaView>
        <View style={styles.divider} />

        {/* 안내 텍스트: 상단 고정으로 겹침 완벽 방지 */}
        <View style={styles.hintBanner}>
          <Icon name="questionmark.circle" tintColor={Editorial.textCaption} size={14} />
          <Text style={styles.hintText}>
            사진 한 장에 여러 벌이 있어도 괜찮아요. AI가 옷을 나눠 각각 등록해요.
          </Text>
        </View>
        <View style={styles.divider} />

        <ScrollView
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}
          style={styles.scrollContainer}
        >
          {/* 공유 제어 영역 */}
          {sharedRooms.length > 0 ? (
            <View style={styles.shareControls}>
              <View style={styles.controlRow}>
                <View style={styles.toggleField}>
                  <Text style={styles.sectionLabel}>공유 옷장에 공유</Text>
                  <View style={styles.toggleRow}>
                    <Text style={styles.toggleText}>
                      {shareEnabled ? '공유 ON' : '공유 OFF'}
                    </Text>
                    <Pressable
                      style={[styles.switchContainer, shareEnabled && styles.switchContainerActive]}
                      onPress={() => {
                        setShareEnabled(!shareEnabled);
                        if (shareEnabled) {
                          setDropdownOpen(false);
                        }
                      }}
                    >
                      <View style={[styles.switchCircle, shareEnabled && styles.switchCircleActive]} />
                    </Pressable>
                  </View>
                </View>

                <View style={styles.dropdownField}>
                  <Text style={[styles.sectionLabel, !shareEnabled && { opacity: 0.5 }]}>등록할 방 선택</Text>
                  <View style={styles.dropdownWrapper}>
                    <Pressable
                      style={[styles.dropdownHeader, !shareEnabled && styles.dropdownHeaderDisabled]}
                      onPress={() => shareEnabled && setDropdownOpen(!dropdownOpen)}
                      disabled={!shareEnabled}
                    >
                      <Text style={[styles.dropdownSelectedText, !shareEnabled && styles.dropdownTextDisabled]} numberOfLines={1}>
                        {selectedRoomId
                          ? sharedRooms.find((r) => r.id === selectedRoomId)?.title
                          : '선택'}
                      </Text>
                      <Icon
                        name={dropdownOpen ? 'chevron.up' : 'chevron.down'}
                        tintColor={shareEnabled ? Editorial.textCaption : ink(0.25)}
                        size={14}
                      />
                    </Pressable>
                    {shareEnabled && dropdownOpen && (
                      <View style={styles.dropdownList}>
                        {sharedRooms.map((room) => (
                          <Pressable
                            key={room.id}
                            style={[
                              styles.dropdownItem,
                              selectedRoomId === room.id && styles.dropdownItemActive,
                            ]}
                            onPress={() => {
                              setSelectedRoomId(room.id);
                              setDropdownOpen(false);
                            }}
                          >
                            <Text
                              style={[
                                styles.dropdownItemText,
                                selectedRoomId === room.id && styles.dropdownItemTextActive,
                              ]}
                              numberOfLines={1}
                            >
                              {room.title}
                            </Text>
                          </Pressable>
                        ))}
                      </View>
                    )}
                  </View>
                </View>
              </View>
            </View>
          ) : (
            <Text style={styles.noRoomText}>가입된 공유 옷장이 없습니다.</Text>
          )}

          {/* 3x3 앨범 스타일 그리드 슬롯 (창 너비를 채우는 108x108 대형 3개 슬롯) */}
          <Text style={[styles.sectionLabel, { marginTop: 20, marginBottom: 8 }]}>
            등록할 옷 사진 (최대 3장)
          </Text>
          <View style={styles.albumGrid}>
            {[0, 1, 2].map((idx) => {
              const uri = photos[idx];
              return (
                <View key={idx} style={styles.albumSlot}>
                  {uri ? (
                    <View style={styles.photoWrapper}>
                      <Image source={{ uri }} style={styles.photoThumb} contentFit="cover" />
                      <Pressable
                        style={styles.deleteBadge}
                        onPress={() => removePhoto(idx)}
                        hitSlop={8}
                      >
                        <Icon name="xmark" tintColor="#FFFFFF" size={10} />
                      </Pressable>
                    </View>
                  ) : (
                    <Pressable
                      style={styles.photoAddBtn}
                      onPress={() => setSourceOpen(true)}
                    >
                      <Text style={styles.photoAddIcon}>＋</Text>
                      <Text style={styles.photoAddText}>사진 추가</Text>
                    </Pressable>
                  )}
                </View>
              );
            })}
          </View>

          <Text style={styles.guideText}>
            ※ 최대 3개까지 동시 선택하여 옷장에 넣을 수 있습니다. (빈 슬롯을 터치하여 사진 추가)
          </Text>
        </ScrollView>

        <PhotoSourceSheet visible={sourceOpen} onClose={() => setSourceOpen(false)} />
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },

  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 12,
  },
  headerText: { flex: 1, gap: 2, paddingRight: 8 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  title: { fontSize: Type.body, fontWeight: '700', color: INK },
  subtitle: { fontSize: Type.micro, color: Editorial.textCaption },
  divider: { height: 1, backgroundColor: ink(0.08) },

  headerBtn: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    backgroundColor: Editorial.cta,
  },
  headerBtnOff: { opacity: 0.35 },
  headerBtnText: { fontSize: 12, fontWeight: '600', color: '#fff' },

  hintBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Editorial.surfaceSoft,
    paddingHorizontal: 20,
    paddingVertical: 10,
    gap: 8,
  },
  hintText: {
    fontSize: 11,
    color: Editorial.textCaption,
    lineHeight: 15,
    flex: 1,
  },

  scrollContainer: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 24,
  },

  shareControls: {
    marginBottom: 16,
  },
  controlRow: {
    flexDirection: 'row',
    gap: 12,
  },
  toggleField: {
    flex: 1,
  },
  dropdownField: {
    flex: 1.2,
  },

  sectionLabel: {
    fontSize: 11,
    color: Editorial.textCaption,
    fontWeight: '600',
    marginBottom: 6,
  },

  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 40,
    paddingHorizontal: 10,
    borderRadius: 8,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  toggleText: {
    fontSize: 12,
    fontWeight: '600',
    color: INK,
  },
  switchContainer: {
    width: 38,
    height: 20,
    borderRadius: 999,
    backgroundColor: ink(0.12),
    paddingHorizontal: 2,
    justifyContent: 'center',
  },
  switchContainerActive: {
    backgroundColor: '#34C759',
  },
  switchCircle: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: '#FFFFFF',
  },
  switchCircleActive: {
    alignSelf: 'flex-end',
  },

  dropdownWrapper: {
    position: 'relative',
    zIndex: 100,
  },
  dropdownHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 40,
    paddingHorizontal: 10,
    borderRadius: 8,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  dropdownSelectedText: {
    fontSize: 12,
    color: Editorial.ink,
    flex: 1,
    marginRight: 4,
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
    zIndex: 101,
    maxHeight: 120,
    overflow: 'scroll',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
  },
  dropdownItem: {
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: Editorial.lineSoft,
  },
  dropdownItemActive: {
    backgroundColor: Editorial.surfaceSoft,
  },
  dropdownItemText: {
    fontSize: 11,
    color: Editorial.textSoft,
  },
  dropdownItemTextActive: {
    fontWeight: '600',
    color: Editorial.ink,
  },

  noRoomText: {
    fontSize: 12,
    color: Editorial.textCaption,
    fontStyle: 'italic',
  },

  albumGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 2,
    marginHorizontal: -20, // 부모 paddingHorizontal(20)을 상쇄하여 좌우 여백을 완전히 없앰
    marginTop: 10,
  },
  albumSlot: {
    flex: 1,
    aspectRatio: 1,
  },
  photoWrapper: {
    position: 'relative',
    width: '100%',
    height: '100%',
  },
  photoThumb: {
    width: '100%',
    height: '100%',
    backgroundColor: Editorial.surface,
  },
  deleteBadge: {
    position: 'absolute',
    top: 4,
    right: 4,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  photoAddBtn: {
    width: '100%',
    height: '100%',
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  photoAddIcon: { fontSize: 22, color: ink(0.4) },
  photoAddText: { fontSize: 11, color: Editorial.textCaption },

  guideText: {
    fontSize: 10,
    color: Editorial.textCaption,
    marginTop: 12,
    lineHeight: 14,
    textAlign: 'center',
  },
  dropdownHeaderDisabled: {
    backgroundColor: '#E5E7EB',
    borderColor: '#D1D5DB',
    opacity: 0.6,
  },
  dropdownTextDisabled: {
    color: ink(0.35),
  },
});
