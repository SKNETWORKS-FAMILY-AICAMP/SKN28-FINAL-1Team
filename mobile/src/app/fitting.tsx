import { Icon } from '@/components/icon';
import { LoadingState, SmartImage, useToast } from '@/components/ui';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const BONE = '#eae0d3';
const ink = (a: number) => `rgba(28,25,23,${a})`;

/** 가상 착장 결과 사진 — 외부 프록시를 타지 않도록 번들 에셋으로 넣는다. */
const RESULT_IMAGE = require('../../assets/images/mock/fitting-result.jpg');

const PIECES = [
  { slot: '상의', image: require('../../assets/images/mock/piece-knit.jpg') },
  { slot: '하의', image: require('../../assets/images/mock/piece-slacks.jpg') },
  { slot: '아우터', image: require('../../assets/images/mock/piece-trench.jpg') },
  { slot: '신발', image: require('../../assets/images/mock/piece-loafer.jpg') },
];

// C5 가상 피팅 — 내 체형에 룩을 입혀 생성 (프로토타입: 타이머로 생성 과정 시뮬레이션)
export default function Fitting() {
  const { contentStyle } = useBreakpoint();
  const [phase, setPhase] = useState<'loading' | 'done'>('loading');
  const toast = useToast();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const generate = () => {
    setPhase('loading');
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setPhase('done');
      toast('가상 피팅이 완성됐어요', { variant: 'success' });
    }, 2600);
  };

  useEffect(() => {
    generate();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.card)]}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>가상 피팅</Text>
          <View style={{ width: 20 }} />
        </View>
      </SafeAreaView>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[styles.content, contentStyle(ContentMax.card)]}>
        {/* 생성 캔버스 */}
        <View style={styles.canvas}>
          {phase === 'loading' ? (
            <LoadingState message={'내 체형에 맞춰\n가상 피팅을 만들고 있어요…'} />
          ) : (
            <>
              {/* 캔버스가 이미 비율·모서리·overflow 를 잡고 있으므로 사진은 그 안을 채우기만 한다. */}
              <SmartImage
                asset={RESULT_IMAGE}
                width="100%"
                aspectRatio={0.952}
                radius={0}
                contentFit="cover"
                style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
              />
              <View style={styles.canvasBadge}>
                <Icon name="figure.stand" tintColor="#fff" size={12} />
                <Text style={styles.canvasBadgeText}>내 체형 반영</Text>
              </View>
            </>
          )}
        </View>

        <View style={styles.body}>
          <Text style={styles.title}>포근한 니트 오피스룩</Text>
          <Text style={styles.subtitle}>서울 8° · 미니멀 · 출근</Text>

          {/* 추천 사이즈 */}
          <View style={styles.sizeCard}>
            <Icon name="ruler" tintColor={INK} size={17} />
            <Text style={styles.sizeText}>
              내 체형 기준 추천 사이즈는 <Text style={styles.sizeStrong}>M</Text> 이에요.
            </Text>
          </View>

          {/* 구성 아이템 썸네일 */}
          <Text style={styles.sectionTitle}>이 룩의 구성</Text>
          <View style={styles.thumbRow}>
            {PIECES.map((p) => (
              <View key={p.slot} style={styles.thumbCol}>
                <SmartImage asset={p.image} width="100%" aspectRatio={1} radius={12} contentFit="cover" />
                <Text style={styles.thumbLabel}>{p.slot}</Text>
              </View>
            ))}
          </View>
        </View>
      </ScrollView>

      {/* 하단 바 */}
      <View style={styles.bottomDivider} />
      <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.card)]}>
        <Pressable
          style={[styles.altBtn, phase === 'loading' && styles.btnDisabled]}
          disabled={phase === 'loading'}
          onPress={generate}>
          <Icon name="arrow.clockwise" tintColor={ink(0.6)} size={15} />
          <Text style={styles.altText}>다시 생성</Text>
        </Pressable>
        <Pressable
          style={[styles.saveBtn, phase === 'loading' && styles.btnDisabled]}
          disabled={phase === 'loading'}
          onPress={() => {
            toast('룩북에 저장했어요', { variant: 'success' });
            router.back();
          }}>
          <Icon name="bookmark.fill" tintColor="#fff" size={15} />
          <Text style={styles.saveText}>룩북에 저장</Text>
        </Pressable>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  headerSafe: { backgroundColor: '#ffffff' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },

  content: { paddingBottom: 24 },
  canvas: {
    /* 고정 높이로 두면 폭이 넓어지는 데스크톱에서 가로로 납작해져 세로 사진이 잘린다.
       폰 폭(400) 기준 비율을 유지한다. */
    aspectRatio: 0.952,
    marginHorizontal: 20,
    borderRadius: 20,
    backgroundColor: BONE,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    overflow: 'hidden',
  },
  canvasLabel: { fontSize: 13, color: ink(0.4), letterSpacing: 0.5, marginTop: 4 },
  canvasBadge: {
    position: 'absolute',
    bottom: 16,
    right: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: INK,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderRadius: 999,
  },
  canvasBadgeText: { fontSize: 11, color: '#fff', fontWeight: '500' },

  body: { paddingHorizontal: 20, paddingTop: 22 },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK },
  subtitle: { fontSize: 13, color: ink(0.45), marginTop: 6 },

  sizeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 18,
    backgroundColor: '#fcffff',
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  sizeText: { flex: 1, fontSize: 14, color: ink(0.7), lineHeight: 20 },
  sizeStrong: { fontWeight: '700', color: INK },

  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 26, marginBottom: 12 },
  thumbRow: { flexDirection: 'row', gap: 10 },
  thumbCol: { flex: 1, alignItems: 'center', gap: 6 },
  thumb: { width: '100%', height: 72, borderRadius: 12, backgroundColor: BONE },
  thumbLabel: { fontSize: 12, color: ink(0.5) },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: '#fff',
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  btnDisabled: { opacity: 0.4 },
  altBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    height: 50,
    paddingHorizontal: 20,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    justifyContent: 'center',
  },
  altText: { fontSize: 14, color: ink(0.6), fontWeight: '500' },
  saveBtn: {
    flex: 1,
    flexDirection: 'row',
    gap: 8,
    height: 50,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveText: { fontSize: 14, color: '#fff', fontWeight: '500' },
});
