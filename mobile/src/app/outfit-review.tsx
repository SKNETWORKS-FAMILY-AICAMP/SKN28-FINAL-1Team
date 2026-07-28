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

const INK = Editorial.ink;

const FOUND_ITEMS = ['오프화이트 니트 상의', '블랙 스트레이트 팬츠', '블랙 로퍼'];

/**
 * 첫 착장 분석 경험의 프론트엔드 MVP.
 * 분석 API가 준비되기 전에는 결과 문구와 감지 아이템을 고정 데이터로 보여주며,
 * 업로드·결과·로그인 전환이라는 UX 흐름을 먼저 검증한다.
 */
export default function OutfitReviewScreen() {
  const { isLoggedIn } = useAuth();
  const [photo, setPhoto] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [complete, setComplete] = useState(false);
  const [selected, setSelected] = useState(() => new Set(FOUND_ITEMS));

  const choosePhoto = async (source: 'album' | 'camera' = 'album') => {
    const uri = source === 'album' ? await pickOutfitPhoto() : await takeOutfitPhoto();
    if (!uri) return;
    setPhoto(uri);
    setComplete(false);
  };

  const analyze = () => {
    if (!photo) return;
    setAnalyzing(true);
    // 실제 분석 API 연결 전, 결과 화면의 유용성을 검증하기 위한 짧은 목업 지연.
    setTimeout(() => {
      setAnalyzing(false);
      setComplete(true);
    }, 700);
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
              <Pressable style={[styles.primary, !photo && styles.primaryDisabled]} disabled={!photo || analyzing} onPress={analyze}>
                {analyzing ? <ActivityIndicator color="#ffffff" /> : <Text style={styles.primaryText}>착장 분석하기</Text>}
              </Pressable>
              <Text style={styles.privacy}>사진은 분석을 위해서만 사용돼요.</Text>
            </>
          ) : (
            <>
              <Image source={{ uri: photo! }} style={styles.resultImage} contentFit="cover" />
              <Text style={styles.resultEyebrow}>COZY&apos;S REVIEW</Text>
              <Text style={styles.title}>균형감 있는{`\n`}모노톤 룩이에요.</Text>
              <View style={styles.feedbackCard}>
                <Text style={styles.feedbackTitle}>잘 어울리는 포인트</Text>
                <Text style={styles.feedbackText}>• 상·하의 명도 대비가 깔끔해 비율이 좋아 보여요.{`\n`}• 절제된 색 조합이 차분한 인상을 만들어줘요.</Text>
              </View>
              <View style={styles.tipCard}>
                <Text style={styles.tipTitle}>더 좋아질 수 있는 제안</Text>
                <Text style={styles.tipText}>밝은 톤의 가방이나 액세서리를 더하면 룩에 포인트가 생겨요.</Text>
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
  title: { marginTop: 10, fontFamily: Fonts.serif, fontSize: 28, lineHeight: 36, color: INK },
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
  privacy: { marginTop: 13, textAlign: 'center', fontSize: 11, lineHeight: 16, color: Editorial.textCaption },
  resultImage: { height: 250, borderRadius: 20 },
  resultEyebrow: { marginTop: 22, fontSize: 10, letterSpacing: 1.6, fontWeight: '600', color: Editorial.textCaption },
  feedbackCard: { marginTop: 22, borderRadius: 16, padding: 18, backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  feedbackTitle: { fontSize: 13, fontWeight: '700', color: INK },
  feedbackText: { marginTop: 9, fontSize: 13, lineHeight: 21, color: Editorial.textSoft },
  tipCard: { marginTop: 10, borderRadius: 16, borderWidth: 1, borderColor: ink(0.1), padding: 18 },
  tipTitle: { fontSize: 13, fontWeight: '700', color: INK },
  tipText: { marginTop: 9, fontSize: 13, lineHeight: 20, color: Editorial.textSoft },
  itemsTitle: { marginTop: 27, fontSize: 15, fontWeight: '700', color: INK },
  itemRow: { minHeight: 47, flexDirection: 'row', alignItems: 'center', gap: 11, borderBottomWidth: 1, borderBottomColor: ink(0.08) },
  checkbox: { width: 19, height: 19, borderRadius: 6, borderWidth: 1, borderColor: ink(0.25), alignItems: 'center', justifyContent: 'center' },
  checkboxOn: { borderColor: Editorial.selected, backgroundColor: Editorial.selected },
  check: { fontSize: 12, fontWeight: '700', color: '#ffffff' },
  itemText: { fontSize: 13, color: Editorial.textSoft },
});
