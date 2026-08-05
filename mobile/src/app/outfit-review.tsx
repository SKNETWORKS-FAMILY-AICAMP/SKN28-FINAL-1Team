import { Image } from 'expo-image';
import { router, type Href } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Icon } from '@/components/icon';
import { ModalShell } from '@/components/ui';
import { ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { pickOutfitPhoto, takeOutfitPhoto } from '@/lib/pickItemPhoto';
import { useAuth } from '@/state/auth';
import { outfitAnalysisStore, useOutfitAnalysis } from '@/state/outfit-analysis';

const INK = Editorial.ink;
const FOUND_ITEMS = ['오프화이트 니트 상의', '블랙 스트레이트 팬츠', '블랙 로퍼'];

export default function OutfitReviewScreen() {
  const { isLoggedIn } = useAuth();
  const { job } = useOutfitAnalysis();
  const [photo, setPhoto] = useState<string | null>(null);
  const [selected, setSelected] = useState(() => new Set(FOUND_ITEMS));

  const pending = outfitAnalysisStore.isPending(job);
  const result = job?.phase === 'SUCCEEDED' ? job.evaluation : null;
  const shownPhoto = job?.photoUri ?? photo;

  const choosePhoto = async (source: 'album' | 'camera' = 'album') => {
    const uri = source === 'album' ? await pickOutfitPhoto() : await takeOutfitPhoto();
    if (!uri) return;
    if (job && !pending) await outfitAnalysisStore.clear();
    setPhoto(uri);
  };

  const analyze = async () => {
    const targetPhoto = photo ?? job?.photoUri;
    if (!targetPhoto) return;
    try {
      await outfitAnalysisStore.start(targetPhoto);
      router.replace('/(tabs)/home');
    } catch {
      // 실패 메시지는 전역 작업 상태에 저장되어 같은 화면에서 보여준다.
    }
  };

  const startNewAnalysis = async () => {
    await outfitAnalysisStore.clear();
    setPhoto(null);
  };

  const toggleItem = (item: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(item)) next.delete(item);
      else next.add(item);
      return next;
    });
  };

  return (
    <ModalShell maxWidth={ContentMax.narrow}>
      <View style={styles.container}>
        <SafeAreaView edges={['top']}>
          <View style={styles.header}>
            <Text style={styles.headerTitle}>내 착장 분석</Text>
            <Pressable hitSlop={12} onPress={() => router.back()}>
              <Text style={styles.close}>×</Text>
            </Pressable>
          </View>
        </SafeAreaView>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {pending ? (
            <PendingView photo={shownPhoto} phase={job?.phase} />
          ) : result ? (
            <>
              {shownPhoto ? <Image source={{ uri: shownPhoto }} style={styles.resultImage} contentFit="cover" /> : null}
              <Text style={styles.resultEyebrow}>COZY&apos;S REVIEW</Text>
              <Text style={styles.title}>{result.summary}</Text>
              <View style={styles.feedbackCard}>
                <Text style={styles.feedbackTitle}>잘 어울리는 포인트</Text>
                <Text style={styles.feedbackText}>{result.strengths.map((item) => `• ${item}`).join('\n')}</Text>
              </View>
              <View style={styles.tipCard}>
                <Text style={styles.tipTitle}>더 좋아질 수 있는 제안</Text>
                <Text style={styles.tipText}>{result.styling_tips.map((item) => `• ${item}`).join('\n')}</Text>
              </View>

              {isLoggedIn ? (
                <>
                  <Text style={styles.itemsTitle}>내 옷장에 추가할 아이템</Text>
                  {FOUND_ITEMS.map((item) => {
                    const checked = selected.has(item);
                    return (
                      <Pressable key={item} style={styles.itemRow} onPress={() => toggleItem(item)}>
                        <View style={[styles.checkbox, checked && styles.checkboxOn]}>
                          <Text style={styles.check}>{checked ? '✓' : ''}</Text>
                        </View>
                        <Text style={styles.itemText}>{item}</Text>
                      </Pressable>
                    );
                  })}
                  <Pressable style={styles.primary} onPress={() => router.push('/item-add' as Href)}>
                    <Text style={styles.primaryText}>{selected.size}개 아이템 저장하기</Text>
                  </Pressable>
                </>
              ) : null}

              <Pressable style={styles.secondaryButton} onPress={startNewAnalysis}>
                <Text style={styles.secondaryButtonText}>새 사진 분석하기</Text>
              </Pressable>
            </>
          ) : (
            <>
              <Text style={styles.title}>평소에 입는 옷들을 보여주세요</Text>
              <Text style={styles.body}>잘 어울리는 포인트를 짚어드릴게요.{`\n`}분석 중에는 다른 화면을 둘러봐도 괜찮아요.</Text>
              <Pressable style={styles.photoBox} onPress={() => choosePhoto()}>
                {shownPhoto ? (
                  <Image source={{ uri: shownPhoto }} style={StyleSheet.absoluteFill} contentFit="cover" />
                ) : (
                  <View style={styles.photoEmpty}>
                    <Text style={styles.photoIcon}>＋</Text>
                    <Text style={styles.photoLabel}>착장 사진 선택하기</Text>
                    <Text style={styles.photoHint}>전신이 보이는 사진이면 더 좋아요</Text>
                  </View>
                )}
              </Pressable>
              <View style={styles.photoActions}>
                <Pressable style={styles.photoAction} onPress={() => choosePhoto()}>
                  <Icon name="photo.on.rectangle" tintColor={INK} size={22} />
                  <Text style={styles.photoActionText}>{shownPhoto ? '다른 사진 선택' : '앨범에서 선택'}</Text>
                </Pressable>
                <Pressable style={styles.photoAction} onPress={() => choosePhoto('camera')}>
                  <Icon name="camera" tintColor={INK} size={22} />
                  <Text style={styles.photoActionText}>카메라로 촬영</Text>
                </Pressable>
              </View>
              {job?.phase === 'FAILED' && job.detail ? <Text style={styles.errorText}>{job.detail}</Text> : null}
              <Pressable
                style={[styles.primary, !shownPhoto && styles.primaryDisabled]}
                disabled={!shownPhoto}
                onPress={analyze}>
                <Text style={styles.primaryText}>{job?.phase === 'FAILED' ? '다시 분석하기' : '착장 분석하기'}</Text>
              </Pressable>
              <Text style={styles.privacy}>사진은 착장 분석을 위해서만 사용돼요.</Text>
            </>
          )}
        </ScrollView>
      </View>
    </ModalShell>
  );
}

function PendingView({ photo, phase }: { photo: string | null; phase?: string }) {
  return (
    <View>
      {photo ? <Image source={{ uri: photo }} style={styles.resultImage} contentFit="cover" /> : null}
      <View style={styles.pendingCard}>
        <ActivityIndicator color={Editorial.selected} />
        <Text style={styles.pendingTitle}>{phase === 'SUBMITTING' ? '사진을 접수하고 있어요' : '착장을 분석하고 있어요'}</Text>
        <Text style={styles.pendingBody}>완료까지 잠시 걸릴 수 있어요. 홈이나 다른 탭을 둘러봐도 분석은 계속됩니다.</Text>
      </View>
      <Pressable style={styles.primary} onPress={() => router.replace('/(tabs)/home')}>
        <Text style={styles.primaryText}>홈 둘러보기</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  header: { height: 58, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: ink(0.1) },
  headerTitle: { fontSize: 16, fontWeight: '600', color: INK },
  close: { fontSize: 24, color: Editorial.textCaption },
  content: { padding: 24, paddingBottom: 40 },
  title: { marginTop: 10, fontFamily: Fonts.serif, fontSize: 24, lineHeight: 32, color: INK },
  body: { marginTop: 13, fontSize: 14, lineHeight: 21, color: Editorial.textCaption },
  photoBox: { height: 300, marginTop: 28, borderRadius: 20, overflow: 'hidden', backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  photoEmpty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 7 },
  photoIcon: { fontSize: 32, color: Editorial.textCaption },
  photoLabel: { fontSize: 14, fontWeight: '600', color: INK },
  photoHint: { fontSize: 12, color: Editorial.textCaption },
  photoActions: { flexDirection: 'row', gap: 12, marginTop: 14 },
  photoAction: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 52, borderRadius: 14, backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  photoActionText: { fontSize: 14, fontWeight: '600', color: INK },
  primary: { height: 52, marginTop: 26, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: Editorial.cta },
  primaryDisabled: { backgroundColor: ink(0.22) },
  primaryText: { color: '#ffffff', fontSize: 14, fontWeight: '600' },
  secondaryButton: { height: 52, marginTop: 14, borderRadius: 999, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: Editorial.line, backgroundColor: Editorial.surface },
  secondaryButtonText: { color: Editorial.textSoft, fontSize: 14, fontWeight: '600' },
  errorText: { marginTop: 18, textAlign: 'center', fontSize: 13, lineHeight: 20, color: Editorial.danger },
  privacy: { marginTop: 13, textAlign: 'center', fontSize: 11, lineHeight: 16, color: Editorial.textCaption },
  resultImage: { height: 250, borderRadius: 20 },
  resultEyebrow: { marginTop: 22, fontSize: 10, letterSpacing: 1.6, fontWeight: '600', color: Editorial.textCaption },
  feedbackCard: { marginTop: 22, borderRadius: 16, padding: 18, backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  feedbackTitle: { fontSize: 14, fontWeight: '700', color: INK },
  feedbackText: { marginTop: 10, fontSize: 15, lineHeight: 24, color: Editorial.textSoft },
  tipCard: { marginTop: 10, borderRadius: 16, borderWidth: 1, borderColor: ink(0.1), padding: 18 },
  tipTitle: { fontSize: 14, fontWeight: '700', color: INK },
  tipText: { marginTop: 10, fontSize: 15, lineHeight: 24, color: Editorial.textSoft },
  itemsTitle: { marginTop: 27, fontSize: 15, fontWeight: '700', color: INK },
  itemRow: { minHeight: 47, flexDirection: 'row', alignItems: 'center', gap: 11, borderBottomWidth: 1, borderBottomColor: ink(0.08) },
  checkbox: { width: 19, height: 19, borderRadius: 6, borderWidth: 1, borderColor: ink(0.25), alignItems: 'center', justifyContent: 'center' },
  checkboxOn: { borderColor: Editorial.selected, backgroundColor: Editorial.selected },
  check: { fontSize: 12, fontWeight: '700', color: '#ffffff' },
  itemText: { fontSize: 13, color: Editorial.textSoft },
  pendingCard: { marginTop: 24, padding: 24, alignItems: 'center', borderRadius: 18, backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  pendingTitle: { marginTop: 14, fontSize: 17, fontWeight: '700', color: INK },
  pendingBody: { marginTop: 8, textAlign: 'center', fontSize: 13, lineHeight: 20, color: Editorial.textCaption },
});
