import { Image } from 'expo-image';
import { router, type Href } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Icon } from '@/components/icon';
import { ModalShell } from '@/components/ui';
import { ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { ApiError } from '@/lib/apiClient';
import { analyzeOutfitPhoto, type OutfitEvaluation } from '@/lib/outfitAnalysisApi';
import { pickOutfitPhoto, takeOutfitPhoto } from '@/lib/pickItemPhoto';
import { useAuth } from '@/state/auth';

const INK = Editorial.ink;

const FOUND_ITEMS = ['오프화이트 니트 상의', '블랙 스트레이트 팬츠', '블랙 로퍼'];

/**
 * 첫 착장 분석 경험의 프론트엔드 MVP.
 * 착장 평가는 분석 API 결과를 사용한다. 감지 아이템은 백엔드 응답이 보완될 때까지
 * 프론트 MVP의 고정 데이터를 유지한다.
 */
export default function OutfitReviewScreen() {
  const { isLoggedIn } = useAuth();
  const [photo, setPhoto] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [complete, setComplete] = useState(false);
  const [evaluation, setEvaluation] = useState<OutfitEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState(() => new Set(FOUND_ITEMS));

  const choosePhoto = async (source: 'album' | 'camera' = 'album') => {
    const uri = source === 'album' ? await pickOutfitPhoto() : await takeOutfitPhoto();
    if (!uri) return;
    setPhoto(uri);
    setComplete(false);
    setEvaluation(null);
    setError(null);
  };

  const analyze = async () => {
    if (!photo) return;
    setAnalyzing(true);
    setError(null);
    try {
      const response = await analyzeOutfitPhoto(photo);
      setEvaluation(response.evaluation);
      setComplete(true);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 400) {
        setError('사진 형식이나 용량을 확인하고 다시 선택해 주세요.');
      } else if (caught instanceof ApiError && caught.status === 503) {
        setError('지금은 착장 분석을 완료하지 못했어요. 잠시 후 다시 시도해 주세요.');
      } else if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError(
          caught instanceof Error && caught.message.startsWith('착장 분석 시간이')
            ? caught.message
            : '서버에 연결하지 못했어요. 네트워크를 확인하고 다시 시도해 주세요.',
        );
      }
    } finally {
      setAnalyzing(false);
    }
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
              <Text style={styles.close}>✕</Text>
            </Pressable>
          </View>
        </SafeAreaView>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {!complete ? (
            <>
              <Text style={styles.title}>평소에 입는 옷들을 보여주세요</Text>
              <Text style={styles.body}>잘 어울리는 포인트를 짚어드리고{`\n`}옷장에 담을 아이템까지 찾아드릴게요</Text>
              <Pressable style={styles.photoBox} onPress={() => choosePhoto()}>
                {photo ? (
                  <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} contentFit="cover" />
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
                  <Text style={styles.photoActionText}>{photo ? '다른 사진 선택' : '앨범에서 선택'}</Text>
                </Pressable>
                <Pressable style={styles.photoAction} onPress={() => choosePhoto('camera')}>
                  <Icon name="camera" tintColor={INK} size={22} />
                  <Text style={styles.photoActionText}>카메라로 촬영</Text>
                </Pressable>
              </View>
              {error ? <Text style={styles.errorText}>{error}</Text> : null}
              <Pressable style={[styles.primary, !photo && styles.primaryDisabled]} disabled={!photo || analyzing} onPress={analyze}>
                {analyzing ? <ActivityIndicator color="#ffffff" /> : <Text style={styles.primaryText}>{error ? '다시 분석하기' : '착장 분석하기'}</Text>}
              </Pressable>
              <Text style={styles.privacy}>사진은 분석을 위해서만 사용돼요.</Text>
            </>
          ) : (
            <>
              <Image source={{ uri: photo! }} style={styles.resultImage} contentFit="cover" />
              <Text style={styles.resultEyebrow}>COZY&apos;S REVIEW</Text>
              <Text style={styles.title}>{evaluation?.summary}</Text>
              <View style={styles.feedbackCard}>
                <Text style={styles.feedbackTitle}>잘 어울리는 포인트</Text>
                <Text style={styles.feedbackText}>{evaluation?.strengths.map((strength) => `• ${strength}`).join('\n')}</Text>
              </View>
              <View style={styles.tipCard}>
                <Text style={styles.tipTitle}>더 좋아질 수 있는 제안</Text>
                <Text style={styles.tipText}>{evaluation?.styling_tips.map((tip) => `• ${tip}`).join('\n')}</Text>
              </View>
              <Text style={styles.itemsTitle}>내 옷장에 추가할 아이템</Text>
              {FOUND_ITEMS.map((item) => {
                const checked = selected.has(item);
                return (
                  <Pressable key={item} style={styles.itemRow} onPress={() => toggleItem(item)}>
                    <View style={[styles.checkbox, checked && styles.checkboxOn]}><Text style={styles.check}>{checked ? '✓' : ''}</Text></View>
                    <Text style={styles.itemText}>{item}</Text>
                  </Pressable>
                );
              })}
              <Pressable style={styles.primary} onPress={() => router.push((isLoggedIn ? '/item-add' : '/login') as Href)}>
                <Text style={styles.primaryText}>{isLoggedIn ? `${selected.size}개 아이템 저장하기` : '로그인하고 옷장에 저장하기'}</Text>
              </Pressable>
              {!isLoggedIn ? <Text style={styles.privacy}>분석 결과는 확인했어요. 저장하면 다음 추천에도 반영돼요.</Text> : null}
            </>
          )}
        </ScrollView>
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  header: { height: 58, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderBottomColor: ink(0.1) },
  headerTitle: { fontSize: 16, fontWeight: '600', color: INK },
  close: { fontSize: 18, color: Editorial.textCaption },
  content: { padding: 24, paddingBottom: 40 },
  /* 한 줄에 담기는 크기 — 줄바꿈은 강제하지 않고 좁은 화면에서만 흐르게 둔다 */
  title: { marginTop: 10, fontFamily: Fonts.serif, fontSize: 24, lineHeight: 32, color: INK },
  body: { marginTop: 13, fontSize: 14, lineHeight: 21, color: Editorial.textCaption },
  photoBox: { height: 300, marginTop: 28, borderRadius: 20, overflow: 'hidden', backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  photoEmpty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 7 },
  photoIcon: { fontSize: 32, color: Editorial.textCaption },
  photoLabel: { fontSize: 14, fontWeight: '600', color: INK },
  photoHint: { fontSize: 12, color: Editorial.textCaption },
  photoActions: { flexDirection: 'row', gap: 12, marginTop: 14 },
  photoAction: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 52,
    borderRadius: 14,
    backgroundColor: Editorial.surface,
    borderWidth: 1, borderColor: Editorial.line,
  },
  photoActionText: { fontSize: 14, fontWeight: '600', color: INK },
  primary: { height: 52, marginTop: 26, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: Editorial.cta },
  primaryDisabled: { backgroundColor: ink(0.22) },
  primaryText: { color: '#ffffff', fontSize: 14, fontWeight: '600' },
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
});
