import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { DatePickerSheet } from '@/components/calendar/date-picker-sheet';
import { ItemPickerSheet } from '@/components/calendar/item-picker-sheet';
import { Icon } from '@/components/icon';
import { ModalShell, SmartImage, useConfirm, useToast } from '@/components/ui';
import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { goBack } from '@/lib/goBack';
import { pickFromAlbum, pickFromCamera } from '@/lib/pickItemPhoto';
import {
  calendarStore,
  entryItemKey,
  formatDateLabel,
  todayKey,
  useCalendarEntry,
  type EntryItem,
} from '@/state/calendar';
import { ALLOWED_HASHTAGS, type AllowedHashtag } from '@/state/lookbook';
import { savedLookStore } from '@/state/saved';

const INK = Editorial.ink;
const PAD = 20;
const CHIP = 76;
const DESKTOP_CHIP = 68;

/**
 * 룩 하나를 짓는 폼 — 룩북과 캘린더가 같은 화면을 쓴다.
 *
 * 두 화면을 하나로 합친 이유: 담기는 내용(사진·입은 옷·일정·해시태그·공개 여부)이 똑같고,
 * 다른 것은 **날짜가 이미 정해졌는지**뿐이다. 폼을 둘로 두면 한쪽에만 필드가 붙어
 * 같은 일을 하는 화면이 서로 다르게 자란다.
 *
 * - date 가 있으면 캘린더 기록 모드: 그 날짜에 저장하고, '룩북에도 올리기'를 고를 수 있다.
 * - date 가 없으면 룩북 모드: 내 룩북에 올리고, '캘린더에도 기록하기'를 켜면 날짜를 고른다.
 */
export function LookComposer({ date }: { date?: string }) {
  const mode = date ? 'calendar' : 'lookbook';
  const existing = useCalendarEntry(date ?? '');

  const { contentStyle } = useBreakpoint();
  const toast = useToast();
  const confirm = useConfirm();

  /* 사진·입은 옷을 2열로 둘지는 창 폭(isDesktop)이 아니라 이 폼이 실제로 받은 폭으로 정한다.
     이 화면은 모달이라 창이 넓어도 콘텐츠 폭은 ContentMax.narrow 로 제한되는데,
     창 폭 기준으로 2열을 켜면 좁은 모달에 두 열이 욱여넣어져 깨진다. */
  const [primaryWidth, setPrimaryWidth] = useState(0);
  const twoCol = primaryWidth >= 560;

  const [photo, setPhoto] = useState<string | undefined>(existing?.photo);
  const [items, setItems] = useState<EntryItem[]>(existing?.items ?? []);
  const [note, setNote] = useState(existing?.note ?? '');
  const [tags, setTags] = useState<AllowedHashtag[]>(existing?.tags ?? []);
  const [shared, setShared] = useState(existing?.shared ?? false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  /* 반대편에도 남길지 — 캘린더 모드면 '룩북에도', 룩북 모드면 '캘린더에도'.
     이미 이어져 있는 기록(existing.lookId)은 토글이 아니라 사실 표시로 그린다. */
  const alreadyLinked = Boolean(existing?.lookId && savedLookStore.getLook(existing.lookId));
  const [linkOn, setLinkOn] = useState(false);
  const [linkDate, setLinkDate] = useState(todayKey());
  const [dateOpen, setDateOpen] = useState(false);

  const toggleCalendarLink = () => {
    if (linkOn) {
      setLinkOn(false);
      return;
    }
    /* 룩북에서 캘린더를 함께 기록하려면 날짜가 필수다. 토글 직후 바로 고르게 해
       기본 날짜를 모르고 저장하는 흐름과, 아래에 날짜 행을 하나 더 두는 낭비를 없앤다. */
    setLinkOn(true);
    setDateOpen(true);
  };

  const renderItemChip = (item: EntryItem, compact = false) => {
    const key = entryItemKey(item);
    const size = compact ? DESKTOP_CHIP : CHIP;
    return (
      <View key={key} style={[styles.chip, compact && styles.chipDesktop]}>
        <SmartImage uri={item.image} width={size} aspectRatio={1} radius={12} />
        <Pressable
          style={styles.chipRemove}
          onPress={() => removeItem(key)}
          hitSlop={8}
          accessibilityLabel={`${item.name} 빼기`}>
          <Icon name="xmark" tintColor="#fff" size={11} />
        </Pressable>
        <Text style={styles.chipName} numberOfLines={1}>
          {item.name}
        </Text>
        {item.owner ? (
          <Text style={styles.chipOwner} numberOfLines={1}>
            {item.owner}님 옷
          </Text>
        ) : null}
      </View>
    );
  };

  const pick = async (kind: 'album' | 'camera') => {
    setLoading(true);
    try {
      const uri = kind === 'album' ? await pickFromAlbum() : await pickFromCamera();
      if (uri) setPhoto(uri);
    } finally {
      setLoading(false);
    }
  };

  const toggleTag = (tag: AllowedHashtag) => {
    setTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
  };

  const removeItem = (key: string) => {
    setItems((prev) => prev.filter((i) => entryItemKey(i) !== key));
  };

  /**
   * 저장할 수 있는 조건이 두 모드에서 다르다.
   * - 캘린더: 일정만 적어 둔 날도 유효한 기록이다 — 사진도 옷도 없이 '친구 결혼식'만 남길 수 있다.
   * - 룩북: 그리드에 보여 줄 그림이 있어야 룩이 성립한다. 사진이거나, 고른 옷의 첫 장이거나.
   *   일정만 적힌 룩은 카드가 빈칸으로 남아 목록에서 아무것도 가리키지 못한다.
   */
  const canSave =
    mode === 'lookbook'
      ? Boolean(photo) || items.length > 0
      : Boolean(photo) || items.length > 0 || note.trim().length > 0;

  /** 룩북 카드에 쓸 대표 사진 — 룩 사진이 없으면 담은 옷의 첫 장으로 대신한다. */
  const coverImage = photo ?? items.find((i) => i.image)?.image;

  const makeLook = (entryDate?: string) =>
    savedLookStore.addLook({
      image: coverImage,
      comment: note.trim() || undefined,
      origin: 'closet',
      items,
      note,
      entryDate,
      tags,
    });

  const handleSave = async () => {
    if (!canSave) return;

    if (mode === 'calendar' && date) {
      const lookId = linkOn && !alreadyLinked ? makeLook(date).id : undefined;
      calendarStore.saveEntry({ date, photo, items, note, tags, shared, lookId });
      toast(
        lookId
          ? '착장을 기록하고 룩북에도 올렸어요'
          : existing
            ? '기록을 수정했어요'
            : '착장을 기록했어요',
        { variant: 'success' },
      );
      goBack('/(tabs)/calendar');
      return;
    }

    /* 룩북 모드 — 고른 날에 이미 기록이 있으면 조용히 덮지 않고 먼저 묻는다. */
    if (linkOn && calendarStore.getEntry(linkDate)) {
      const ok = await confirm({
        title: `${formatDateLabel(linkDate)}에 이미 기록이 있어요`,
        message: '이 룩으로 그날 기록을 바꿀까요?',
        confirmLabel: '바꾸기',
      });
      if (!ok) return;
    }

    const look = makeLook(linkOn ? linkDate : undefined);
    if (linkOn) {
      calendarStore.saveEntry({
        date: linkDate,
        photo,
        items,
        note,
        tags,
        shared,
        lookId: look.id,
      });
    }
    toast(linkOn ? '룩북에 올리고 캘린더에도 기록했어요' : '룩북에 올렸어요', {
      variant: 'success',
    });
    router.navigate('/(tabs)/lookbook?tab=saved');
  };

  const handleDelete = async () => {
    if (!date) return;
    const ok = await confirm({
      title: '이 기록을 지울까요?',
      message: '사진과 담은 옷이 함께 지워져요.',
      confirmLabel: '삭제',
      destructive: true,
    });
    if (!ok) return;
    calendarStore.removeEntry(date);
    toast('기록을 지웠어요');
    goBack('/(tabs)/calendar');
  };

  const backTo = mode === 'calendar' ? '/(tabs)/calendar' : '/(tabs)/lookbook';
  const title =
    mode === 'lookbook' ? '룩 올리기' : existing ? '착장 기록 수정' : '착장 기록하기';

  return (
    <ModalShell maxWidth={ContentMax.narrow}>
      <View style={styles.container}>
        <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
          <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
            <Pressable hitSlop={12} onPress={() => goBack(backTo)}>
              <Icon name="chevron.left" tintColor={INK} size={22} />
            </Pressable>
            <Text style={styles.title}>{title}</Text>
            {mode === 'calendar' && existing ? (
              <Pressable hitSlop={12} onPress={handleDelete} accessibilityLabel="기록 삭제">
                <Icon name="trash" tintColor={ink(0.45)} size={20} />
              </Pressable>
            ) : (
              <View style={styles.headerSpacer} />
            )}
          </View>

          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
            {date ? <Text style={styles.dateLabel}>{formatDateLabel(date)}</Text> : null}

            {/* 넓은 화면에서는 사진과 입은 옷을 나란히 둔다. 모바일은 한 열이라 손가락으로
                사진·옷을 고르는 순서가 그대로 유지된다. */}
            <View
              style={[styles.primaryFields, twoCol && styles.primaryFieldsDesktop]}
              onLayout={(e) => setPrimaryWidth(e.nativeEvent.layout.width)}>
              <View style={[styles.primaryField, twoCol && styles.primaryFieldFlex]}>
                <Text style={[styles.sectionTitle, styles.sectionLead]}>
                  {mode === 'calendar' ? '오늘의 룩 사진' : '룩 사진'}
                </Text>
                {photo ? (
                  <View style={styles.photoWrap}>
                    <SmartImage
                      uri={photo}
                      width="100%"
                      aspectRatio={twoCol ? 4 / 3 : 4 / 5}
                      radius={16}
                    />
                    <Pressable
                      style={styles.photoRemove}
                      onPress={() => setPhoto(undefined)}
                      hitSlop={8}
                      accessibilityLabel="사진 지우기">
                      <Icon name="xmark" tintColor="#fff" size={14} />
                    </Pressable>
                  </View>
                ) : (
                  <View style={styles.photoEmpty}>
                    <Icon name="photo" tintColor={ink(0.28)} size={30} />
                    <Text style={styles.photoHint}>
                      {mode === 'calendar'
                        ? '사진 없이 옷이나 일정만 기록해도 괜찮아요'
                        : '사진이 없으면 고른 옷의 첫 장이 표지가 돼요'}
                    </Text>
                  </View>
                )}
                <View style={styles.pickRow}>
                  <Pressable style={styles.pickBtn} onPress={() => pick('album')} disabled={loading}>
                    <Icon name="photo.on.rectangle" tintColor={INK} size={18} />
                    <Text style={styles.pickLabel}>갤러리</Text>
                  </Pressable>
                  <Pressable style={styles.pickBtn} onPress={() => pick('camera')} disabled={loading}>
                    <Icon name="camera" tintColor={INK} size={18} />
                    <Text style={styles.pickLabel}>카메라</Text>
                  </Pressable>
                </View>
                {loading ? (
                  <View style={styles.loadingRow}>
                    <ActivityIndicator color={INK} />
                  </View>
                ) : null}
              </View>

              {twoCol ? <View style={styles.primaryDivider} /> : null}

              <View style={[styles.primaryField, twoCol && styles.primaryFieldFlex]}>
                <View style={[styles.sectionHead, styles.itemSectionHead, twoCol && styles.itemSectionHeadDesktop]}>
                  <Text style={styles.sectionTitle}>입은 옷</Text>
                  {items.length > 0 ? <Text style={styles.count}>{items.length}개</Text> : null}
                </View>
                {twoCol && items.length === 0 ? (
                  <Pressable
                    style={[styles.addChip, styles.addChipDesktopEmpty]}
                    onPress={() => setPickerOpen(true)}>
                    <Icon name="plus" tintColor={ink(0.45)} size={22} />
                    <Text style={styles.addChipText}>옷 고르기</Text>
                  </Pressable>
                ) : twoCol ? (
                  <View style={styles.chipGrid}>
                    {items.map((item) => renderItemChip(item, true))}
                    <Pressable style={[styles.addChip, styles.addChipDesktop]} onPress={() => setPickerOpen(true)}>
                      <Icon name="plus" tintColor={ink(0.45)} size={20} />
                      <Text style={styles.addChipText}>옷 고르기</Text>
                    </Pressable>
                  </View>
                ) : (
                  <ScrollView
                    horizontal
                    showsHorizontalScrollIndicator={false}
                    contentContainerStyle={styles.chipRow}>
                    {items.map((item) => renderItemChip(item))}
                    <Pressable style={styles.addChip} onPress={() => setPickerOpen(true)}>
                      <Icon name="plus" tintColor={ink(0.45)} size={22} />
                      <Text style={styles.addChipText}>옷 고르기</Text>
                    </Pressable>
                  </ScrollView>
                )}
              </View>
            </View>

            {/* 일정 — '선택' 꼬리표를 달지 않는다. 여기만 선택이라고 적으면 나머지가 필수로 읽히는데
                실제로는 사진·옷·일정 모두 골라 채우는 칸이고, 무엇이 있어야 저장되는지는
                사진 자리의 안내와 저장 버튼이 이미 말해 준다. */}
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>일정</Text>
            </View>
            <TextInput
              style={styles.noteInput}
              value={note}
              onChangeText={setNote}
              placeholder="예) 팀 회의, 친구 결혼식, 제주 여행"
              placeholderTextColor={Editorial.textMuted}
              maxLength={60}
              returnKeyType="done"
            />

            {/* 해시태그 */}
            <Text style={[styles.sectionTitle, styles.tagSection]}>해시태그</Text>
            <View style={styles.tagRow}>
              {ALLOWED_HASHTAGS.map((tag) => {
                const on = tags.includes(tag);
                return (
                  <Pressable
                    key={tag}
                    onPress={() => toggleTag(tag)}
                    style={[styles.tag, on && styles.tagOn]}>
                    <Text style={[styles.tagText, on && styles.tagTextOn]}>#{tag}</Text>
                  </Pressable>
                );
              })}
            </View>

            {/* 반대편에도 남기기 */}
            {alreadyLinked ? (
              <View style={[styles.optionRow, styles.firstOption, styles.linkedRow]}>
                <View style={styles.optionIcon}>
                  <Icon name="book" tintColor={INK} size={17} />
                </View>
                <View style={styles.optionBody}>
                  <Text style={styles.optionTitle}>룩북에 올려 둔 기록이에요</Text>
                  <Text style={styles.optionDesc}>내 룩북 · 저장됨에서 볼 수 있어요</Text>
                </View>
                <Icon name="checkmark" tintColor={ink(0.45)} size={16} />
              </View>
            ) : (
              <>
                <Pressable
                  style={[styles.optionRow, styles.firstOption]}
                  onPress={mode === 'lookbook' ? toggleCalendarLink : () => setLinkOn((v) => !v)}>
                  <View style={styles.optionIcon}>
                    <Icon name={mode === 'calendar' ? 'book' : 'calendar'} tintColor={INK} size={17} />
                  </View>
                  <View style={styles.optionBody}>
                    <Text style={styles.optionTitle}>
                      {mode === 'calendar' ? '룩북에도 올리기' : '캘린더에도 기록하기'}
                    </Text>
                    <Text style={styles.optionDesc}>
                      {mode === 'calendar'
                        ? '내 룩북에 같은 룩으로 남겨요'
                        : '어느 날 입은 착장인지 남겨요'}
                    </Text>
                  </View>
                  <View style={[styles.switch, linkOn && styles.switchOn]}>
                    <View style={[styles.knob, linkOn && styles.knobOn]} />
                  </View>
                </Pressable>

                {/* 고른 날짜는 폼에 남겨 둔다 — 토글을 켤 때 시트가 바로 뜨지만, 거기서 그냥 닫으면
                    기본값(오늘)이 조용히 저장된다. 어느 날에 저장되는지는 늘 보여야 하고,
                    다시 고를 길도 여기여야 한다. */}
                {mode === 'lookbook' && linkOn ? (
                  <Pressable style={styles.dateRow} onPress={() => setDateOpen(true)}>
                    <Text style={styles.dateRowLabel}>날짜</Text>
                    <Text style={styles.dateRowValue}>{formatDateLabel(linkDate)}</Text>
                    <Icon name="chevron.right" tintColor={ink(0.3)} size={15} />
                  </Pressable>
                ) : null}
              </>
            )}

            {/* 공개 범위는 기록 위치를 정한 뒤 고른다. 룩북·캘린더 공용 폼이라 두 진입점에서
                같은 순서로 보인다. */}
            <Pressable style={styles.optionRow} onPress={() => setShared((v) => !v)}>
              <View style={styles.optionIcon}>
                <Icon name="person.2" tintColor={INK} size={17} />
              </View>
              <View style={styles.optionBody}>
                <Text style={styles.optionTitle}>함께 쓰는 옷장 친구에게 공개</Text>
                <Text style={styles.optionDesc}>저장 후에도 켜고 끌 수 있어요</Text>
              </View>
              <View style={[styles.switch, shared && styles.switchOn]}>
                <View style={[styles.knob, shared && styles.knobOn]} />
              </View>
            </Pressable>
          </ScrollView>

          <View style={styles.footer}>
            <Pressable
              style={[styles.saveBtn, !canSave && styles.saveBtnDisabled]}
              onPress={handleSave}
              disabled={!canSave}>
              <Text style={styles.saveText}>
                {mode === 'calendar' ? '저장하기' : '룩북에 올리기'}
              </Text>
            </Pressable>
          </View>
        </SafeAreaView>

        <ItemPickerSheet
          visible={pickerOpen}
          selected={items}
          onClose={() => setPickerOpen(false)}
          onConfirm={setItems}
        />

        <DatePickerSheet
          visible={dateOpen}
          value={linkDate}
          onClose={() => setDateOpen(false)}
          onSelect={setLinkDate}
        />
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: PAD,
    paddingVertical: 12,
  },
  title: { flex: 1, textAlign: 'center', fontSize: Type.label, fontWeight: '700', color: INK },
  headerSpacer: { width: 22 },

  content: { paddingHorizontal: PAD, paddingBottom: 24 },
  dateLabel: { fontSize: Type.lead, fontWeight: '700', color: INK, marginBottom: 22 },

  sectionHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 28,
    marginBottom: 12,
  },
  sectionTitle: { fontSize: Type.body, fontWeight: '700', color: INK },
  /* 섹션 머리와 내용 사이 간격 — sectionHead 를 쓰지 않는 단독 제목용 */
  sectionLead: { marginBottom: 12 },
  count: { fontSize: Type.caption, color: Editorial.textCaption },

  primaryFields: { gap: 28 },
  /* 넓은 웹 모달에서는 두 입력을 한 줄에 둬, 빈 사진 영역이 아래 콘텐츠를 밀어내지 않는다. */
  primaryFieldsDesktop: { flexDirection: 'row', alignItems: 'flex-start', gap: 24 },
  /* 세로(1열) 모드에서는 내용 높이만큼만 차지해야 한다. flex:1 을 주면 부모 높이가
     스크롤뷰라 정해지지 않아 두 칸이 높이 0으로 붕괴하며 서로 겹친다.
     좌우로 폭을 나눠야 하는 2열(가로) 모드에서만 flex:1 을 켠다. */
  primaryField: { minWidth: 0 },
  primaryFieldFlex: { flex: 1 },
  /* 사진과 옷은 한 기록의 두 재료지만, 서로 다른 선택 흐름이라 가는 점선으로 경계를 준다. */
  primaryDivider: {
    alignSelf: 'stretch',
    borderLeftWidth: 1,
    borderStyle: 'dashed',
    borderColor: Editorial.line,
  },
  itemSectionHead: { marginTop: 0, marginBottom: 12 },
  /* 모바일에서 사진 다음에 오는 기존 간격은 그대로 둔다. */
  itemSectionHeadDesktop: { marginTop: 0 },

  photoWrap: { position: 'relative' },
  photoRemove: {
    position: 'absolute',
    top: 10,
    right: 10,
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: ink(0.55),
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoEmpty: {
    height: 150,
    borderRadius: 16,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  photoHint: { fontSize: Type.caption, color: Editorial.textCaption },

  noteInput: {
    height: 48,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Editorial.line,
    paddingHorizontal: 14,
    fontSize: Type.footnote,
    color: INK,
  },
  pickRow: { flexDirection: 'row', gap: 10, marginTop: 12 },
  pickBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 44,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  pickLabel: { fontSize: Type.footnote, fontWeight: '600', color: INK },
  loadingRow: { alignItems: 'center', marginTop: 12 },

  chipRow: { gap: 10, paddingRight: PAD, paddingBottom: 4 },
  /* 데스크톱 오른쪽 칸은 스크롤 대신 격자로 쌓는다. 추가 타일까지 항상 화면에 남는다. */
  chipGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingBottom: 4 },
  chip: { width: CHIP },
  chipDesktop: { width: DESKTOP_CHIP },
  chipRemove: {
    position: 'absolute',
    top: 5,
    right: 5,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: ink(0.55),
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipName: { fontSize: Type.micro, color: INK, marginTop: 6 },
  chipOwner: { fontSize: Type.micro, color: Editorial.textMuted, marginTop: 1 },
  addChip: {
    width: CHIP,
    height: CHIP,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  /* 아직 옷을 하나도 고르지 않았을 때는 오른쪽의 빈 면적 전체가 선택 버튼이 된다. */
  addChipDesktopEmpty: { width: '100%', height: 150 },
  addChipDesktop: { width: DESKTOP_CHIP, height: DESKTOP_CHIP },
  addChipText: { fontSize: Type.micro, color: Editorial.textCaption },

  tagSection: { marginTop: 30, marginBottom: 12 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tag: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  tagOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  tagText: { fontSize: Type.caption, fontWeight: '500', color: Editorial.textCaption },
  tagTextOn: { color: '#fff' },

  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
    /* 옵션 줄끼리는 한 묶음이라 바짝 붙인다 */
    marginTop: 8,
  },
  /* 묶음의 첫 줄만 해시태그와 사이를 벌린다 — 고르는 것과 정하는 것의 경계 */
  firstOption: { marginTop: 34 },
  /* 이미 이어져 있어 누를 것이 없는 줄 — 면을 깔아 토글 줄과 구분한다 */
  linkedRow: { backgroundColor: Editorial.surfaceSoft },
  optionIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionBody: { flex: 1, gap: 3 },
  optionTitle: { fontSize: Type.footnote, fontWeight: '600', color: INK },
  optionDesc: { fontSize: Type.micro, color: Editorial.textCaption },
  switch: {
    width: 44,
    height: 26,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: Editorial.line,
    padding: 2,
    justifyContent: 'center',
  },
  switchOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  knob: { width: 20, height: 20, borderRadius: 10, backgroundColor: ink(0.2) },
  knobOn: { backgroundColor: '#fff', alignSelf: 'flex-end' },

  /* 토글 바로 아래 붙는 날짜 줄 — 토글의 딸린 항목이라 간격을 좁게 둔다 */
  dateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 14,
    height: 48,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
    marginTop: 8,
  },
  dateRowLabel: { fontSize: Type.footnote, color: Editorial.textCaption },
  dateRowValue: { flex: 1, textAlign: 'right', fontSize: Type.footnote, fontWeight: '600', color: INK },

  footer: { paddingHorizontal: PAD, paddingTop: 12, paddingBottom: 8 },
  saveBtn: {
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnDisabled: { opacity: 0.35 },
  saveText: { fontSize: Type.body, fontWeight: '600', color: '#fff' },
});
