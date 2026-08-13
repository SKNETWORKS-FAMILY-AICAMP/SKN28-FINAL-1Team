import { Icon } from '@/components/icon';
import { DetailTwoPane } from '@/components/detail-two-pane';
import { LoadingState, SmartImage, useToast } from '@/components/ui';
import { Editorial, ink, Fonts } from '@/constants/theme';
import { dailyLookToVariant, TODAY_LOOK } from '@/constants/today-look';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useDailyLook } from '@/hooks/use-daily-look';
import { goBack } from '@/lib/goBack';
import { pickBodyPhoto } from '@/lib/pickItemPhoto';
import { fitDailyLookToMannequin } from '@/lib/virtualTryOnApi';
import { useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = Editorial.ink;
const CANVAS = '#f5f1ea';

export default function Fitting() {
  const { lookId } = useLocalSearchParams<{ lookId?: string }>();
  const { contentStyle, width } = useBreakpoint();
  const { look: dailyLook } = useDailyLook(Boolean(lookId));
  const look = useMemo(() => dailyLookToVariant(dailyLook) ?? TODAY_LOOK, [dailyLook]);
  const [phase, setPhase] = useState<'idle' | 'loading' | 'done'>('idle');
  const [resultUri, setResultUri] = useState<string | null>(null);
  const toast = useToast();
  const maxW = width >= 1280 ? 960 : 720;

  const generate = async () => {
    if (!lookId) {
      toast('추천 룩 정보를 찾을 수 없어요.', { variant: 'error' });
      return;
    }
    const personUri = await pickBodyPhoto();
    if (!personUri) return;

    setPhase('loading');
    try {
      const result = await fitDailyLookToMannequin(lookId, personUri);
      setResultUri(result.image_url);
      setPhase('done');
      toast('이 추천 룩을 내 체형 마네킹에 입혔어요.', { variant: 'success' });
    } catch (error) {
      setPhase(resultUri ? 'done' : 'idle');
      toast(error instanceof Error ? error.message : '가상 착장을 만들지 못했어요.', {
        variant: 'error',
      });
    }
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(maxW)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/look-detail')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>가상 피팅</Text>
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(maxW)]}>
        <DetailTwoPane
          image={
            <View style={styles.canvas}>
              {phase === 'loading' ? (
                <LoadingState message={'선택한 추천 룩을\n내 체형 마네킹에 입히고 있어요'} />
              ) : resultUri ? (
                <>
                  {/* width 는 'auto' 로 둔다. '100%' 로 두면 캔버스에 좌우 패딩이 생겼을 때
                      폭이 그만큼 줄어드는데 left:0 에 붙어 버려서 오른쪽에 빈 띠가 남는다.
                      contentFit 은 contain — 생성 결과는 비율이 제각각이라 cover 로 채우면
                      전신에서 얼굴 위·발 아래가 잘린다(착장을 확인하려는 화면이라 치명적). */}
                  <SmartImage
                    uri={resultUri}
                    width="auto"
                    radius={0}
                    contentFit="contain"
                    /* contain 이라 이미지가 캔버스를 다 못 채운다. SmartImage 기본 배경(bone=흰색)을
                       그대로 두면 남는 자리가 캔버스 크림색과 어긋나 액자가 두 색으로 보인다. */
                    style={styles.canvasImage}
                  />
                  <View style={styles.canvasBadge}>
                    <Icon name="figure.stand" tintColor="#fff" size={12} />
                    <Text style={styles.canvasBadgeText}>내 체형 반영</Text>
                  </View>
                </>
              ) : (
                /* 안내 문구에만 좌우 여백이 필요하다. 캔버스 자체에 패딩을 주면
                   결과 이미지가 그 폭만큼 좁아진다. */
                <View style={styles.canvasEmpty}>
                  <Icon name="figure.stand" tintColor={ink(0.45)} size={42} />
                  <Text style={styles.canvasTitle}>전신 사진을 선택해 주세요</Text>
                  <Text style={styles.canvasGuide}>사진은 저장하지 않고 가상 착장에만 사용해요.</Text>
                  <Pressable style={styles.photoBtn} onPress={generate}>
                    <Text style={styles.photoBtnText}>사진 선택하고 입어보기</Text>
                  </Pressable>
                </View>
              )}
            </View>
          }
          details={
            <View style={styles.body}>
              <Text style={styles.title}>{look.title}</Text>
              <Text style={styles.subtitle}>{look.subtitle}</Text>
              <Text style={styles.sectionTitle}>적용되는 추천 룩</Text>
              <View style={styles.thumbRow}>
                {look.pieces.map((piece) => (
                  <View key={piece.slot} style={styles.thumbCol}>
                    <SmartImage
                      uri={piece.image}
                      width="100%"
                      aspectRatio={1}
                      radius={12}
                      contentFit="cover"
                    />
                    <Text style={styles.thumbLabel}>{piece.slot}</Text>
                  </View>
                ))}
              </View>
            </View>
          }
        />
      </ScrollView>

      <View style={styles.bottomDivider} />
      <View style={[styles.bottomBar, { paddingBottom: 12 }, contentStyle(maxW)]}>
        <Pressable
          style={[styles.altBtn, phase === 'loading' && styles.btnDisabled]}
          disabled={phase === 'loading'}
          onPress={generate}>
          <Icon name="arrow.clockwise" tintColor={ink(0.6)} size={15} />
          <Text style={styles.altText}>{resultUri ? '다른 사진으로 생성' : '사진 선택'}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 16, paddingTop: 8, paddingBottom: 10,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },
  content: { paddingBottom: 24 },
  canvas: {
    aspectRatio: 0.8,
    marginHorizontal: 20,
    borderRadius: 20,
    backgroundColor: CANVAS,
    borderWidth: 1,
    borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  canvasImage: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'transparent',
  },
  canvasEmpty: { alignItems: 'center', gap: 10, paddingHorizontal: 24 },
  canvasTitle: { fontSize: 16, fontWeight: '600', color: INK, marginTop: 4 },
  canvasGuide: { fontSize: 12, color: Editorial.textCaption, textAlign: 'center' },
  photoBtn: {
    marginTop: 8, backgroundColor: Editorial.cta, borderRadius: 999,
    paddingHorizontal: 18, paddingVertical: 11,
  },
  photoBtnText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  canvasBadge: {
    position: 'absolute', bottom: 16, right: 16, flexDirection: 'row',
    alignItems: 'center', gap: 5, backgroundColor: INK,
    paddingHorizontal: 11, paddingVertical: 6, borderRadius: 999,
  },
  canvasBadgeText: { fontSize: 11, color: '#fff', fontWeight: '500' },
  body: { paddingHorizontal: 20, paddingTop: 22 },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK },
  subtitle: { fontSize: 13, color: Editorial.textCaption, marginTop: 6 },
  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 26, marginBottom: 12 },
  thumbRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  thumbCol: { width: 72, alignItems: 'center', gap: 6 },
  thumbLabel: { fontSize: 12, color: Editorial.textCaption },
  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: {
    flexDirection: 'row', justifyContent: 'flex-end', backgroundColor: Editorial.page,
    paddingHorizontal: 20, paddingTop: 12,
  },
  btnDisabled: { opacity: 0.4 },
  altBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 7, height: 50,
    paddingHorizontal: 20, borderRadius: 999, borderWidth: 1,
    borderColor: ink(0.14), justifyContent: 'center',
  },
  altText: { fontSize: 14, color: Editorial.textCaption, fontWeight: '500' },
});
