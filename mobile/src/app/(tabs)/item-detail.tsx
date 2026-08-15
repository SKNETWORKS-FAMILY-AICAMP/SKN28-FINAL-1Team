import { Icon } from '@/components/icon';
import { ErrorState, LoadingState, SmartImage, useConfirm, useToast } from '@/components/ui';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ItemTagSheet } from '@/components/closet/item-tag-sheet';
import { DetailTwoPane } from '@/components/detail-two-pane';
import { Editorial, ink, Fonts, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { confirmWardrobeItem, useWardrobeItem } from '@/hooks/use-wardrobe';
import { deleteWardrobeItem, itemDisplayName, type WardrobeApiItem, getMySharedRooms, listSharedRoomItems, registerItemToSharedRoom, unregisterItemFromSharedRoom, type SharedRoom } from '@/lib/wardrobeApi';

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
  const { contentStyle, width, isMobile } = useBreakpoint();
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
  const [dropdownOpen, setDropdownOpen] = useState(false);

  /* 공유 상태 동기화.
   *
   * useFocusEffect 인 이유: 이 화면은 탭 스택에 얹혀 한 번 뜨면 언마운트되지 않는다.
   * 마운트 시 1회만 조회하면, 옷장 공유 탭에서 X로 공유를 해제하고 돌아와도
   * 토글이 계속 켜진 채로 남는다(반대 방향은 이 화면이 직접 바꾸니 맞아 보였다).
   * 화면에 들어올 때마다 서버 상태로 다시 맞춘다.
   *
   * 그리고 스캔 전에 반드시 초기화한다 — 예전엔 "찾으면 true" 만 있고
   * "못 찾으면 false" 가 없어서, 한 번 켜진 값이 다음 아이템까지 따라왔다. */
  const syncShareState = useCallback(async () => {
    if (!id || isReadOnly) return;
    try {
      const rooms = (await getMySharedRooms()) || [];
      setSharedRooms(rooms);
      if (rooms.length === 0) {
        setSharedRoomIds([]);
        setShareEnabled(false);
        return;
      }

      // 방별 조회를 모두 기다린 뒤 한 번에 판정한다 — 개별 then 으로 흩어 놓으면
      // 늦게 온 응답이 먼저 온 결과를 덮어써 상태가 요동친다.
      const results = await Promise.all(
        rooms.map(async (room) => ({
          roomId: room.id,
          hasItem: (await listSharedRoomItems(room.id)).some((it) => it.wardrobe_item.id === id),
        })),
      );
      const shared = results.filter((r) => r.hasItem).map((r) => r.roomId);

      setSharedRoomIds(shared);
      setShareEnabled(shared.length > 0);

    } catch {
      /* 공유 상태는 곁가지다 — 못 읽어도 상세 화면 자체는 그대로 보여준다 */
    }
  }, [id, isReadOnly]);

  useFocusEffect(
    useCallback(() => {
      void syncShareState();
    }, [syncShareState]),
  );

  /* 토글은 '공유 여부'가 아니라 **방 목록을 펼칠지**만 정한다.
     켤 때 아무 방에도 넣지 않는 이유: 어느 방에 넣을지는 아래 목록에서 고르는 것이고,
     임의로 첫 방에 밀어 넣으면 사용자가 고르기도 전에 공유가 일어난다.
     끌 때는 지금 들어가 있는 모든 방에서 뺀다 — "공유 안 함"의 뜻이 그것뿐이다. */
  const handleToggleShare = async (nextEnabled: boolean) => {
    if (!item) return;
    if (nextEnabled) {
      setShareEnabled(true);
      setDropdownOpen(true);
      return;
    }
    try {
      for (const rid of sharedRoomIds) {
        await unregisterItemFromSharedRoom(rid, item.id);
      }
      setSharedRoomIds([]);
      setShareEnabled(false);
      setDropdownOpen(false);
      toast('공유를 취소했어요');
    } catch (e) {
      toast(e instanceof Error ? e.message : '공유 처리에 실패했어요', { variant: 'error' });
    }
  };

  /* 목록의 방을 누를 때마다 그 방만 켜고 끈다(한 번 더 누르면 해제).
     한 벌을 여러 방에 걸 수 있어야 하므로 다른 방은 건드리지 않는다 —
     예전엔 방을 고르면 나머지 방에서 빼버려서, 고르는 게 아니라 '이동'이었다.
     고르고 나서도 목록을 닫지 않는다: 두 번째 방을 이어서 고를 수 있어야 한다. */
  const handleToggleRoom = async (roomId: string) => {
    if (!item) return;
    const alreadyShared = sharedRoomIds.includes(roomId);
    try {
      if (alreadyShared) {
        await unregisterItemFromSharedRoom(roomId, item.id);
        setSharedRoomIds((prev) => prev.filter((rid) => rid !== roomId));
      } else {
        await registerItemToSharedRoom(roomId, item.id);
        setSharedRoomIds((prev) => [...prev, roomId]);

      }
    } catch (e) {
      toast(e instanceof Error ? e.message : '공유 처리에 실패했어요', { variant: 'error' });
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

  const shareBox = !isReadOnly && sharedRooms.length > 0 ? (
    <View style={isMobile ? styles.shareAreaMobile : styles.shareAreaDesktop}>
      <View style={styles.shareRow}>
        <View style={styles.shareToggleWrap}>
          <Text style={styles.shareLabel} numberOfLines={1}>공유 옷장</Text>
          <Pressable
            style={[styles.switch, shareEnabled && styles.switchOn]}
            onPress={() => handleToggleShare(!shareEnabled)}>
            <View style={[styles.switchKnob, shareEnabled && styles.switchKnobOn]} />
          </Pressable>
        </View>
        <View style={styles.roomPickerWrap}>
          <Pressable
            style={[styles.roomPicker, !shareEnabled && styles.roomPickerDisabled]}
            onPress={() => setDropdownOpen((open) => !open)}
            disabled={!shareEnabled}>
            <Text style={[styles.roomPickerText, !shareEnabled && styles.roomPickerTextDisabled]} numberOfLines={1}>
              공유할 옷장 선택
            </Text>
            <Icon
              name={dropdownOpen ? 'chevron.up' : 'chevron.down'}
              tintColor={shareEnabled ? Editorial.textCaption : ink(0.25)}
              size={15}
            />
          </Pressable>
          {shareEnabled && dropdownOpen ? (
            <View style={styles.roomMenu}>
              <ScrollView
                nestedScrollEnabled
                showsVerticalScrollIndicator={sharedRooms.length > 4}
                style={{ maxHeight: 160 }}>
                {sharedRooms.map((room) => {
                  const checked = sharedRoomIds.includes(room.id);
                  return (
                    <Pressable
                      key={room.id}
                      style={[styles.roomOption, checked && styles.roomOptionSelected]}
                      onPress={() => handleToggleRoom(room.id)}
                      accessibilityRole="checkbox"
                      accessibilityState={{ checked }}>
                      <Text
                        style={[styles.roomOptionText, checked && styles.roomOptionTextSelected]}
                        numberOfLines={1}>
                        {room.title}
                      </Text>
                      {checked ? (
                        <Icon name="checkmark" tintColor={INK} size={13} />
                      ) : null}
                    </Pressable>
                  );
                })}
              </ScrollView>
            </View>
          ) : null}
        </View>
      </View>
    </View>
  ) : null;

  return (
    <View style={styles.container}>
      {header}

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(maxW)]}>
        {/* 모바일: 1. 공유 옷장 토글 박스 -> 2. 옷 사진 -> 3. 아이템 제목 순서 */}
        {isMobile ? shareBox : null}

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

              {/* PC 웹(데스크톱): 아까와 동일하게 오른쪽 열 내부 배치 */}
              {!isMobile ? shareBox : null}

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
  shareAreaMobile: {
    position: 'relative',
    zIndex: 100,
    elevation: 20,
    overflow: 'visible',
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 14,
    padding: 14,
    marginHorizontal: 20,
    marginTop: 10,
    marginBottom: 16,
    backgroundColor: Editorial.surface,
  },
  shareAreaDesktop: {
    position: 'relative',
    zIndex: 100,
    elevation: 20,
    overflow: 'visible',
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 14,
    padding: 14,
    marginTop: 18,
    marginBottom: 18,
    backgroundColor: Editorial.surface,
  },
  shareRow: {
    position: 'relative',
    zIndex: 100,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  shareToggleWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  shareLabel: {
    fontSize: Type.footnote,
    fontWeight: '600',
    color: INK,
  },
  switch: {
    width: 42,
    height: 24,
    borderRadius: 12,
    backgroundColor: ink(0.16),
    padding: 2,
    justifyContent: 'center',
  },
  switchOn: {
    backgroundColor: '#34C759',
  },
  switchKnob: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#fff',
  },
  switchKnobOn: {
    alignSelf: 'flex-end',
  },
  roomPickerWrap: {
    position: 'relative',
    zIndex: 101,
    flex: 1,
  },
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
  roomPickerDisabled: {
    backgroundColor: ink(0.04),
    opacity: 0.6,
  },
  roomPickerText: {
    flex: 1,
    marginRight: 8,
    fontSize: Type.footnote,
    color: INK,
  },
  roomPickerTextDisabled: {
    color: ink(0.35),
  },
  roomMenu: {
    position: 'absolute',
    zIndex: 102,
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
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
  },
  roomOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 11,
    borderBottomWidth: 1,
    borderBottomColor: Editorial.lineSoft,
    backgroundColor: Editorial.surface,
  },
  roomOptionSelected: {
    backgroundColor: Editorial.surfaceSoft,
  },
  roomOptionText: {
    flex: 1,
    marginRight: 8,
    fontSize: Type.footnote,
    color: Editorial.textSoft,
  },
  roomOptionTextSelected: {
    fontWeight: '700',
    color: INK,
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
