import { Icon } from '@/components/icon';
import { ErrorState, LoadingState, SmartImage, useConfirm, useToast } from '@/components/ui';
import { router, useLocalSearchParams } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ItemTagSheet } from '@/components/closet/item-tag-sheet';
import { DetailTwoPane } from '@/components/detail-two-pane';
import { Editorial, ink, Fonts } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { confirmWardrobeItem, useWardrobeItem } from '@/hooks/use-wardrobe';
import { deleteWardrobeItem, itemDisplayName, type WardrobeApiItem, getMySharedRooms, listSharedRoomItems, registerItemToSharedRoom, unregisterItemFromSharedRoom, type SharedRoom } from '@/lib/wardrobeApi';
import { useEffect } from 'react';

const INK = Editorial.ink;
const BONE = Editorial.bone;

/** 스펙 표에 올릴 것 — 값이 빈 항목은 서버가 못 채운 것이라 아예 빼고 보여준다. */
function specsOf(item: WardrobeApiItem): { label: string; value: string }[] {
  return [
    { label: '색', value: item.color },
    { label: '소재', value: item.material },
    { label: '핏', value: item.fit },
    { label: '패턴', value: item.pattern },
    { label: '소매', value: item.sleeve },
    { label: '기장', value: item.length },
    { label: '계절', value: item.season.join('·') },
  ].filter((s) => s.value);
}

// D3 아이템 상세 — 태그 확인·수정·삭제
export default function ItemDetail() {
  const { contentStyle, width } = useBreakpoint();
  const maxW = width >= 1280 ? 960 : 720;
  const { id, readonly } = useLocalSearchParams<{ id?: string; readonly?: string }>();
  const isReadOnly = readonly === '1';

  const { item, loading, error, reload, setItem } = useWardrobeItem(id);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const toast = useToast();
  const confirm = useConfirm();

  const [sharedRooms, setSharedRooms] = useState<SharedRoom[]>([]);
  const [sharedRoomIds, setSharedRoomIds] = useState<string[]>([]);
  const [shareEnabled, setShareEnabled] = useState(false);
  const [selectedRoomId, setSelectedRoomId] = useState<string>('');
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // 공유 상태 동기화 및 방 목록 조회
  useEffect(() => {
    if (id && !isReadOnly) {
      getMySharedRooms().then((rooms) => {
        setSharedRooms(rooms || []);
        if (rooms && rooms.length > 0) {
          setSelectedRoomId(rooms[0].id);
          // 이 아이템이 어느 방에 공유되어 있는지 확인
          rooms.forEach((room) => {
            listSharedRoomItems(room.id).then((items) => {
              const hasItem = items.some((it) => it.wardrobe_item.id === id);
              if (hasItem) {
                setSharedRoomIds([room.id]);
                setShareEnabled(true);
                setSelectedRoomId(room.id);
              }
            });
          });
        }
      });
    }
  }, [id, isReadOnly]);

  const handleToggleShare = async (nextEnabled: boolean) => {
    if (!item) return;
    try {
      if (nextEnabled) {
        if (!selectedRoomId) return;
        await registerItemToSharedRoom(selectedRoomId, item.id);
        setSharedRoomIds([selectedRoomId]);
        setShareEnabled(true);
        toast('공유 옷장에 공유했어요');
      } else {
        // 기존 공유된 모든 방에서 해제
        for (const rid of sharedRoomIds) {
          await unregisterItemFromSharedRoom(rid, item.id);
        }
        setSharedRoomIds([]);
        setShareEnabled(false);
        toast('공유를 취소했어요');
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : '공유 처리에 실패했어요', { variant: 'error' });
    }
  };

  const handleSelectRoom = async (roomId: string) => {
    if (!item) return;
    try {
      for (const rid of sharedRoomIds) {
        await unregisterItemFromSharedRoom(rid, item.id);
      }
      await registerItemToSharedRoom(roomId, item.id);
      setSharedRoomIds([roomId]);
      setSelectedRoomId(roomId);
      toast('공유 옷장을 변경했어요');
    } catch (e) {
      toast(e instanceof Error ? e.message : '공유 옷장 변경에 실패했어요', { variant: 'error' });
    }
  };

  /* 태그를 고치지 않고 "맞다"고만 확인하는 경로. 고칠 게 있으면 수정 시트에서 저장하면 된다. */
  const onConfirm = async () => {
    if (!item) return;
    setConfirming(true);
    try {
      const { item: confirmed, sharedRoomId } = await confirmWardrobeItem(item.id);
      setItem(confirmed);
      /* 등록할 때 공유를 켜 뒀다면 확정과 동시에 공유까지 끝난다 —
         두 번 알리지 않고 한 줄로 합쳐 말한다. */
      toast(sharedRoomId ? '옷장에 확정하고 공유했어요' : '옷장에 확정했어요', {
        variant: 'success',
      });
    } catch (e) {
      toast(e instanceof Error ? e.message : '확인하지 못했어요', { variant: 'error' });
    } finally {
      setConfirming(false);
    }
  };

  const onDelete = async () => {
    if (!item) return;
    const ok = await confirm({
      title: '이 아이템을 삭제할까요?',
      message: '삭제하면 되돌릴 수 없어요.',
      confirmLabel: '삭제',
      destructive: true,
    });
    if (!ok) return;
    try {
      await deleteWardrobeItem(item.id);
      toast('삭제했어요', { variant: 'success' });
      goBack('/(tabs)/closet');
    } catch (e) {
      toast(e instanceof Error ? e.message : '삭제하지 못했어요', { variant: 'error' });
    }
  };

  const header = (
    <SafeAreaView edges={['top']} style={styles.headerSafe}>
      <View style={[styles.header, contentStyle(maxW)]}>
        <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/closet')}>
          <Icon name="chevron.left" tintColor={INK} size={20} />
        </Pressable>
        {item && !isReadOnly ? (
          <View style={styles.headerActions}>
            <Pressable hitSlop={10} onPress={() => setEditing(true)} accessibilityLabel="태그 수정">
              <Icon name="square.and.pencil" tintColor={ink(0.6)} size={19} />
            </Pressable>
            <Pressable hitSlop={10} onPress={onDelete} accessibilityLabel="삭제">
              <Icon name="trash" tintColor={ink(0.6)} size={18} />
            </Pressable>
          </View>
        ) : null}
      </View>
    </SafeAreaView>
  );

  if (loading) {
    return (
      <View style={styles.container}>
        {header}
        <LoadingState message="아이템을 불러오는 중…" style={styles.state} />
      </View>
    );
  }

  if (error || !item) {
    return (
      <View style={styles.container}>
        {header}
        <ErrorState
          title="아이템을 불러오지 못했어요"
          description={error ?? '옷장에서 다시 열어 주세요.'}
          onRetry={reload}
          style={styles.state}
        />
      </View>
    );
  }

  const specs = specsOf(item);
  const category = [item.category_large, item.category_small].filter(Boolean).join(' · ');

  return (
    <View style={styles.container}>
      {header}

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(maxW)]}>
        {/* 데스크톱: [사진 | 상세] 2단 / 태블릿·모바일: 세로 */}
        <DetailTwoPane
          image={
            <View style={styles.image}>
              {/* 바깥 View 가 비율로 크기를 잡으므로 사진은 그 안을 절대좌표로 채운다 */}
              <SmartImage
                uri={item.image_url}
                width="100%"
                radius={20}
                contentFit="cover"
                style={styles.imageFill}
              />
              <View style={styles.catBadge}>
                <Text style={styles.catBadgeText}>{category}</Text>
              </View>
            </View>
          }
          details={
            <View style={styles.body}>
              <Text style={styles.name}>{itemDisplayName(item)}</Text>
              {item.style.length > 0 ? (
                <Text style={styles.styleLine}>{item.style.join(' · ')}</Text>
              ) : null}

              {/* 확인 대기 — 확정 전에는 추천에 쓰이지 않는다는 걸 알려준다 */}
              {!isReadOnly && !item.confirmed ? (
                <View style={styles.pending}>
                  <View style={styles.pendingHead}>
                    <Icon name="exclamationmark.triangle" tintColor={Editorial.wine} size={15} />
                    <Text style={styles.pendingText}>
                      AI가 붙인 태그를 아직 확인하지 않았어요. 확인해야 추천에 함께 쓰여요.
                    </Text>
                  </View>
                  <Pressable
                    style={[styles.confirmBtn, confirming && styles.confirmBtnOff]}
                    onPress={onConfirm}
                    disabled={confirming}>
                    <Icon name="checkmark" tintColor="#fff" size={14} />
                    <Text style={styles.confirmText}>
                      {confirming ? '확인 중…' : '태그가 맞아요'}
                    </Text>
                  </Pressable>
                </View>
              ) : null}

              {/* 공유 옷장 설정 영역 (색 정보 상단에 상주) */}
              {!isReadOnly && sharedRooms.length > 0 ? (
                <View style={styles.shareArea}>
                  <View style={styles.shareHeader}>
                    <Text style={styles.shareLabel}>공유 옷장에 공유</Text>
                    <Pressable
                      style={[styles.switchContainer, shareEnabled && styles.switchContainerActive]}
                      onPress={() => handleToggleShare(!shareEnabled)}
                    >
                      <View style={[styles.switchCircle, shareEnabled && styles.switchCircleActive]} />
                    </Pressable>
                  </View>
                  {shareEnabled && (
                    <View style={styles.dropdownWrapper}>
                      <Pressable
                        style={styles.dropdownHeader}
                        onPress={() => setDropdownOpen(!dropdownOpen)}
                      >
                        <Text style={styles.dropdownSelectedText} numberOfLines={1}>
                          {selectedRoomId
                            ? sharedRooms.find((r) => r.id === selectedRoomId)?.title
                            : '선택'}
                        </Text>
                        <Icon
                          name={dropdownOpen ? 'chevron.up' : 'chevron.down'}
                          tintColor={Editorial.textCaption}
                          size={14}
                        />
                      </Pressable>
                      {dropdownOpen && (
                        <View style={styles.dropdownList}>
                          {sharedRooms.map((room) => (
                            <Pressable
                              key={room.id}
                              style={[
                                styles.dropdownItem,
                                selectedRoomId === room.id && styles.dropdownItemActive,
                              ]}
                              onPress={() => {
                                handleSelectRoom(room.id);
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
                  )}
                </View>
              ) : null}

              {specs.length > 0 ? (
                <View style={styles.specGrid}>
                  {specs.map((s) => (
                    <View key={s.label} style={styles.specTile}>
                      <Text style={styles.specLabel}>{s.label}</Text>
                      <Text style={styles.specValue}>{s.value}</Text>
                    </View>
                  ))}
                </View>
              ) : !isReadOnly ? (
                <Pressable style={styles.noSpec} onPress={() => setEditing(true)}>
                  <Text style={styles.noSpecText}>
                    태그가 아직 비어 있어요. 눌러서 채워 주세요.
                  </Text>
                </Pressable>
              ) : null}

              {!isReadOnly ? (
                <Pressable style={styles.editRow} onPress={() => setEditing(true)}>
                  <Icon name="square.and.pencil" tintColor={ink(0.55)} size={15} />
                  <Text style={styles.editText}>태그 수정</Text>
                </Pressable>
              ) : null}
            </View>
          }
        />
      </ScrollView>

      <View style={styles.bottomDivider} />
      <View style={[styles.bottomBar, { paddingBottom: 12 }, contentStyle(maxW)]}>
        <Pressable style={styles.cta} onPress={() => router.push('/chat-mode')}>
          <Icon name="sparkles" tintColor="#fff" size={15} />
          <Text style={styles.ctaText}>이 옷으로 코디 추천받기</Text>
        </Pressable>
      </View>

      {!isReadOnly ? (
        <ItemTagSheet
          visible={editing}
          item={item}
          onClose={() => setEditing(false)}
          onSaved={setItem}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  shareArea: {
    backgroundColor: Editorial.surfaceSoft,
    borderRadius: 16,
    padding: 14,
    marginTop: 22,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  shareHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  shareLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: INK,
  },
  switchContainer: {
    width: 44,
    height: 24,
    borderRadius: 999,
    backgroundColor: ink(0.12),
    paddingHorizontal: 2,
    justifyContent: 'center',
  },
  switchContainerActive: {
    backgroundColor: '#34C759',
  },
  switchCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
  },
  switchCircleActive: {
    alignSelf: 'flex-end',
  },
  dropdownWrapper: {
    position: 'relative',
    zIndex: 100,
    marginTop: 10,
  },
  dropdownHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 40,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: Editorial.surface,
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
    paddingHorizontal: 12,
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
  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 8,
  },
  headerActions: { flexDirection: 'row', gap: 18 },
  state: { paddingTop: 80 },

  content: { paddingBottom: 24 },
  image: {
    /* 고정 높이로 두면 폭이 넓어지는 데스크톱에서 가로로 납작해져 세로 사진이 잘린다.
       폰 폭(400) 기준 비율을 유지한다. */
    aspectRatio: 1.053,
    backgroundColor: BONE,
    marginHorizontal: 20,
    borderRadius: 20,
    overflow: 'hidden',
  },
  imageFill: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  catBadge: {
    position: 'absolute',
    top: 14,
    left: 14,
    backgroundColor: 'rgba(255,255,255,0.9)',
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: 999,
  },
  catBadgeText: { fontSize: 11, fontWeight: '600', color: Editorial.textSoft },

  body: { paddingHorizontal: 20, paddingTop: 22 },
  name: { fontFamily: Fonts.serif, fontSize: 26, color: INK },
  styleLine: { fontSize: 14, color: Editorial.textCaption, marginTop: 5 },

  pending: {
    gap: 12,
    marginTop: 18,
    backgroundColor: Editorial.accent,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  pendingHead: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  pendingText: { flex: 1, fontSize: 12.5, color: Editorial.wine, lineHeight: 18 },
  confirmBtn: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    height: 36,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
  },
  confirmBtnOff: { opacity: 0.5 },
  confirmText: { fontSize: 13, fontWeight: '600', color: '#fff' },

  specGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 22,
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 16,
    overflow: 'hidden',
  },
  specTile: { width: '50%', paddingHorizontal: 16, paddingVertical: 15, gap: 5 },
  specLabel: { fontSize: 11, color: Editorial.textCaption },
  specValue: { fontSize: 14.5, fontWeight: '500', color: Editorial.ink },

  noSpec: {
    marginTop: 22,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: Editorial.line,
    borderRadius: 16,
    paddingVertical: 22,
    alignItems: 'center',
  },
  noSpecText: { fontSize: 13, color: Editorial.textCaption },

  editRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    alignSelf: 'flex-start',
    marginTop: 18,
    paddingHorizontal: 14,
    height: 40,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  editText: { fontSize: 13, fontWeight: '600', color: INK },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { backgroundColor: Editorial.page, paddingHorizontal: 20, paddingTop: 12 },
  cta: {
    flexDirection: 'row',
    gap: 8,
    height: 52,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { fontSize: 14.5, color: '#fff', fontWeight: '500' },
});
