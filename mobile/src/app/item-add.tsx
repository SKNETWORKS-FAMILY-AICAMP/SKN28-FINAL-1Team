import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Icon } from '@/components/icon';
import { ModalShell, SmartImage, useToast } from '@/components/ui';
import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { confirmWardrobeItem, useWardrobeUpload } from '@/hooks/use-wardrobe';
import { deleteWardrobeItem, itemDisplayName, type WardrobeApiItem } from '@/lib/wardrobeApi';
import { draftItem, useDraftPhoto } from '@/state/draft-item';

const INK = Editorial.ink;

/** 태그 몇 개를 한 줄로 — 확인 단계에선 전체가 아니라 알아볼 만큼만 보여준다. */
function tagLine(item: WardrobeApiItem): string {
  return [item.category_small || item.category_large, item.color, item.material, item.fit]
    .filter(Boolean)
    .join(' · ');
}

/**
 * D2 아이템 등록.
 *
 * 등록은 비동기다: 사진을 올리면(202) 이미지 프로세서가 누끼·분류를 하고,
 * 끝나면 job 에 아이템이 채워진다. 사진 1장에서 **여러 벌**이 나올 수 있다.
 * 결과는 confirmed=false(확인 대기) 상태이므로, 사용자가 확인해야 옷장에 정식 편입된다.
 * 태그 하나하나를 고치는 일은 아이템 상세에서 한다 — 여기선 맞는지만 확인한다.
 */
export default function ItemAddScreen() {
  const { contentStyle } = useBreakpoint();
  const photo = useDraftPhoto();
  const toast = useToast();
  const upload = useWardrobeUpload();

  /* 확정·삭제로 처리를 끝낸 아이템은 목록에서 뺀다 (남은 것만 보여주면 할 일이 분명해진다) */
  const [handled, setHandled] = useState<string[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  const remaining = upload.items.filter((i) => !handled.includes(i.id));

  const openSource = () => router.push('/item-add-source');

  const close = () => {
    draftItem.setPhoto(null);
    upload.reset();
    router.replace('/(tabs)/closet');
  };

  const startUpload = () => {
    if (!photo) {
      openSource();
      return;
    }
    upload.start(photo);
  };

  const confirmOne = async (item: WardrobeApiItem) => {
    setBusyId(item.id);
    try {
      await confirmWardrobeItem(item.id);
      setHandled((prev) => [...prev, item.id]);
      toast(`${itemDisplayName(item)}을(를) 옷장에 담았어요`, { variant: 'success' });
    } catch (e) {
      toast(e instanceof Error ? e.message : '저장하지 못했어요', { variant: 'error' });
    } finally {
      setBusyId(null);
    }
  };

  const discardOne = async (item: WardrobeApiItem) => {
    setBusyId(item.id);
    try {
      await deleteWardrobeItem(item.id);
      setHandled((prev) => [...prev, item.id]);
    } catch (e) {
      toast(e instanceof Error ? e.message : '삭제하지 못했어요', { variant: 'error' });
    } finally {
      setBusyId(null);
    }
  };

  const busy = upload.phase === 'uploading' || upload.phase === 'processing';

  return (
    <ModalShell maxWidth={ContentMax.narrow}>
      <View style={styles.container}>
        <SafeAreaView edges={['top']} style={styles.headerSafe}>
          <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
            <View style={styles.headerText}>
              <Text style={styles.title}>아이템 등록</Text>
              <Text style={styles.subtitle}>
                {upload.phase === 'done'
                  ? 'AI가 분류한 결과를 확인해 주세요'
                  : '사진을 올리면 AI가 누끼 처리·분류해요'}
              </Text>
            </View>
            <Pressable hitSlop={12} onPress={close} accessibilityLabel="닫기">
              <Icon name="xmark" tintColor={ink(0.5)} size={18} />
            </Pressable>
          </View>
        </SafeAreaView>
        <View style={styles.divider} />

        <ScrollView contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
          {/* 사진 — 처리 중에는 바꿀 수 없다 */}
          <Pressable style={styles.photo} onPress={busy ? undefined : openSource} disabled={busy}>
            {photo ? (
              <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} contentFit="cover" />
            ) : (
              <View style={styles.photoEmpty}>
                <Text style={styles.photoEmptyIcon}>＋</Text>
                <Text style={styles.photoEmptyText}>사진 추가하기</Text>
              </View>
            )}
          </Pressable>

          {/* 진행 상태 */}
          {upload.phase === 'uploading' ? (
            <View style={styles.statusRow}>
              <ActivityIndicator color={INK} />
              <Text style={styles.statusText}>사진을 올리는 중…</Text>
            </View>
          ) : null}

          {upload.phase === 'processing' ? (
            <View style={styles.statusRow}>
              <ActivityIndicator color={INK} />
              <View style={styles.statusBody}>
                <Text style={styles.statusText}>옷을 분리하고 태그를 붙이는 중…</Text>
                <Text style={styles.statusHint}>
                  잠시 걸릴 수 있어요. 이 화면을 열어 두면 끝나는 대로 보여드려요.
                </Text>
              </View>
            </View>
          ) : null}

          {upload.phase === 'failed' ? (
            <View style={styles.failCard}>
              <Text style={styles.failText}>{upload.error}</Text>
              <Pressable style={styles.retryBtn} onPress={startUpload}>
                <Icon name="arrow.clockwise" tintColor={INK} size={14} />
                <Text style={styles.retryText}>다시 시도</Text>
              </Pressable>
            </View>
          ) : null}

          {/* 결과 — 사진 1장에서 여러 벌이 나올 수 있다 */}
          {upload.phase === 'done' ? (
            remaining.length === 0 ? (
              <View style={styles.doneCard}>
                <Text style={styles.doneText}>
                  {upload.items.length === 0
                    ? '옷을 찾지 못했어요. 옷이 잘 보이는 사진으로 다시 올려보세요.'
                    : '모두 정리했어요.'}
                </Text>
              </View>
            ) : (
              <>
                <Text style={styles.resultCount}>찾은 옷 {remaining.length}개</Text>
                {remaining.map((item) => (
                  <View key={item.id} style={styles.resultCard}>
                    <SmartImage uri={item.image_url} width={64} height={78} radius={12} />
                    <View style={styles.resultBody}>
                      <Text style={styles.resultName} numberOfLines={1}>
                        {itemDisplayName(item)}
                      </Text>
                      <Text style={styles.resultTags} numberOfLines={2}>
                        {tagLine(item)}
                      </Text>
                    </View>
                    <View style={styles.resultActions}>
                      <Pressable
                        style={styles.discardBtn}
                        onPress={() => discardOne(item)}
                        disabled={busyId === item.id}>
                        <Text style={styles.discardText}>제외</Text>
                      </Pressable>
                      <Pressable
                        style={styles.confirmBtn}
                        onPress={() => confirmOne(item)}
                        disabled={busyId === item.id}>
                        <Text style={styles.confirmText}>담기</Text>
                      </Pressable>
                    </View>
                  </View>
                ))}
                <Text style={styles.resultHint}>
                  태그를 자세히 고치려면 담은 뒤 옷장에서 아이템을 열어 주세요.
                </Text>
              </>
            )
          ) : null}
        </ScrollView>

        {/* 하단 바 — 단계에 따라 하는 일이 바뀐다 */}
        <View style={styles.bottomDivider} />
        <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
          {upload.phase === 'done' ? (
            <Pressable style={styles.primaryBtn} onPress={close}>
              <Text style={styles.primaryText}>옷장으로</Text>
            </Pressable>
          ) : (
            <Pressable
              style={[styles.primaryBtn, (!photo || busy) && styles.primaryBtnOff]}
              onPress={startUpload}
              disabled={!photo || busy}>
              <Text style={styles.primaryText}>
                {busy ? '처리 중…' : '분류 시작'}
              </Text>
            </Pressable>
          )}
        </SafeAreaView>
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },

  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 12,
  },
  headerText: { flex: 1, gap: 4 },
  title: { fontSize: Type.lead, fontWeight: '700', color: INK },
  subtitle: { fontSize: Type.caption, color: Editorial.textCaption },
  divider: { height: 1, backgroundColor: ink(0.08) },

  content: { paddingHorizontal: 20, paddingTop: 18, paddingBottom: 24, gap: 16 },

  photo: {
    height: 240,
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  photoEmpty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 6 },
  photoEmptyIcon: { fontSize: 26, color: ink(0.35) },
  photoEmptyText: { fontSize: Type.footnote, color: Editorial.textCaption },

  statusRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  statusBody: { flex: 1, gap: 4 },
  statusText: { fontSize: Type.footnote, color: INK, fontWeight: '500' },
  statusHint: { fontSize: Type.caption, color: Editorial.textCaption, lineHeight: 19 },

  failCard: {
    gap: 12,
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  failText: { fontSize: Type.footnote, color: INK, lineHeight: 21 },
  retryBtn: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    height: 38,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.16),
  },
  retryText: { fontSize: Type.caption, fontWeight: '600', color: INK },

  doneCard: { padding: 16, borderRadius: 14, borderWidth: 1, borderColor: Editorial.line },
  doneText: { fontSize: Type.footnote, color: Editorial.textCaption, lineHeight: 21 },

  resultCount: { fontSize: Type.caption, fontWeight: '600', color: Editorial.textCaption },
  resultCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  resultBody: { flex: 1, gap: 4, minWidth: 0 },
  resultName: { fontSize: Type.footnote, fontWeight: '600', color: INK },
  resultTags: { fontSize: Type.caption, color: Editorial.textCaption, lineHeight: 18 },
  resultActions: { gap: 6, alignItems: 'stretch' },
  discardBtn: {
    paddingHorizontal: 12,
    height: 32,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.16),
    alignItems: 'center',
    justifyContent: 'center',
  },
  discardText: { fontSize: Type.micro, fontWeight: '600', color: Editorial.textCaption },
  confirmBtn: {
    paddingHorizontal: 12,
    height: 32,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  confirmText: { fontSize: Type.micro, fontWeight: '600', color: '#fff' },
  resultHint: { fontSize: Type.micro, color: Editorial.textMuted, lineHeight: 18 },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { paddingHorizontal: 20, paddingTop: 12 },
  primaryBtn: {
    height: 52,
    borderRadius: 14,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnOff: { opacity: 0.35 },
  primaryText: { fontSize: Type.label, fontWeight: '600', color: '#fff' },
});
