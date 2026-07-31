import { useLocalSearchParams } from 'expo-router';
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

const INK = Editorial.ink;
const PAD = 20;
const CHIP = 76;

/**
 * 착장 기록 작성·수정 — 하루치 기록을 한 화면에서 끝낸다.
 * 사진(갤러리·카메라)과 옷(내 옷장·앱 추천·친구 옷장)은 섹션으로 나란히 두고,
 * 옷 선택만 시트로 뺐다. 둘 다 선택 사항이고, 하나라도 있으면 저장할 수 있다.
 */
export default function CalendarEntryScreen() {
  const params = useLocalSearchParams<{ date?: string }>();
  const date = params.date ?? todayKey();
  const existing = useCalendarEntry(date);

  const { contentStyle } = useBreakpoint();
  const toast = useToast();
  const confirm = useConfirm();

  const [photo, setPhoto] = useState<string | undefined>(existing?.photo);
  const [items, setItems] = useState<EntryItem[]>(existing?.items ?? []);
  const [note, setNote] = useState(existing?.note ?? '');
  const [tags, setTags] = useState<AllowedHashtag[]>(existing?.tags ?? []);
  const [shared, setShared] = useState(existing?.shared ?? false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(false);

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

  /* 일정만 적어 둔 날도 유효한 기록이다 — 사진도 옷도 없이 '친구 결혼식'만 남길 수 있다. */
  const canSave = Boolean(photo) || items.length > 0 || note.trim().length > 0;

  const handleSave = () => {
    if (!canSave) return;
    calendarStore.saveEntry({ date, photo, items, note, tags, shared });
    toast(existing ? '기록을 수정했어요' : '착장을 기록했어요', { variant: 'success' });
    goBack('/(tabs)/calendar');
  };

  const handleDelete = async () => {
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

  return (
    <ModalShell maxWidth={ContentMax.narrow}>
      <View style={styles.container}>
        <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
          <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
            <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/calendar')}>
              <Icon name="chevron.left" tintColor={INK} size={22} />
            </Pressable>
            <Text style={styles.title}>{existing ? '착장 기록 수정' : '착장 기록하기'}</Text>
            {existing ? (
              <Pressable hitSlop={12} onPress={handleDelete}>
                <Icon name="trash" tintColor={ink(0.45)} size={20} />
              </Pressable>
            ) : (
              <View style={styles.headerSpacer} />
            )}
          </View>

          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
            <Text style={styles.dateLabel}>{formatDateLabel(date)}</Text>

            {/* 오늘의 룩 사진 */}
            <Text style={[styles.sectionTitle, styles.sectionLead]}>오늘의 룩 사진</Text>
            {photo ? (
              <View style={styles.photoWrap}>
                <SmartImage uri={photo} width="100%" aspectRatio={4 / 5} radius={16} />
                <Pressable style={styles.photoRemove} onPress={() => setPhoto(undefined)} hitSlop={8}>
                  <Icon name="xmark" tintColor="#fff" size={14} />
                </Pressable>
              </View>
            ) : (
              <View style={styles.photoEmpty}>
                <Icon name="photo" tintColor={ink(0.28)} size={30} />
                <Text style={styles.photoHint}>사진 없이 옷이나 일정만 기록해도 괜찮아요</Text>
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

            {/* 입은 옷 */}
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>입은 옷</Text>
              {items.length > 0 ? <Text style={styles.count}>{items.length}개</Text> : null}
            </View>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chipRow}>
              {items.map((item) => {
                const key = entryItemKey(item);
                return (
                  <View key={key} style={styles.chip}>
                    <SmartImage uri={item.image} width={CHIP} aspectRatio={1} radius={12} />
                    <Pressable
                      style={styles.chipRemove}
                      onPress={() => removeItem(key)}
                      hitSlop={8}>
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
              })}
              <Pressable style={styles.addChip} onPress={() => setPickerOpen(true)}>
                <Icon name="plus" tintColor={ink(0.45)} size={22} />
                <Text style={styles.addChipText}>옷 고르기</Text>
              </Pressable>
            </ScrollView>

            {/* 일정 */}
            <View style={styles.sectionHead}>
              <Text style={styles.sectionTitle}>일정</Text>
              <Text style={styles.count}>선택</Text>
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

            {/* 친구 공개 */}
            <Pressable style={styles.shareRow} onPress={() => setShared((v) => !v)}>
              <View style={styles.shareIcon}>
                <Icon name="person.2" tintColor={INK} size={17} />
              </View>
              <View style={styles.shareBody}>
                <Text style={styles.shareTitle}>함께 쓰는 옷장 친구에게 공개</Text>
                <Text style={styles.shareDesc}>저장 후에도 켜고 끌 수 있어요</Text>
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
              <Text style={styles.saveText}>저장하기</Text>
            </Pressable>
          </View>
        </SafeAreaView>

        <ItemPickerSheet
          visible={pickerOpen}
          selected={items}
          onClose={() => setPickerOpen(false)}
          onConfirm={setItems}
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
  chip: { width: CHIP },
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

  shareRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
    marginTop: 30,
  },
  shareIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shareBody: { flex: 1, gap: 3 },
  shareTitle: { fontSize: Type.footnote, fontWeight: '600', color: INK },
  shareDesc: { fontSize: Type.micro, color: Editorial.textCaption },
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
