import { router } from 'expo-router';
import { useRef, useState } from 'react';
import {
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { SmartImage } from '@/components/ui';
import { Fonts } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const VISUAL_H = 320;

/** 온보딩 슬라이드 이미지 — 랜딩(/landing)과 같은 3장을 공유한다.
 *  교체하려면 assets/images/mock/ 의 파일을 바꾸면 된다. */
const ONBOARDING_IMAGES = {
  stylist: require('../../assets/images/mock/stylist.jpg'),
  closet: require('../../assets/images/mock/closet.jpg'),
  fitting: require('../../assets/images/mock/fitting.jpg'),
} as const;

const SLIDES = [
  {
    kicker: 'AI STYLIST',
    image: ONBOARDING_IMAGES.stylist,
    title: '매일 아침, 오늘의 룩을 골라드려요',
    body: '날씨·일정·취향을 반영해 AI가 코디를 제안해요.',
  },
  {
    kicker: 'YOUR CLOSET',
    image: ONBOARDING_IMAGES.closet,
    title: '내 옷장을 그대로 옮겨보세요',
    body: '사진 한 장이면 카테고리·색상·소재를 자동으로 정리해요.',
  },
  {
    kicker: 'FITTING',
    image: ONBOARDING_IMAGES.fitting,
    title: '입어보기 전에 먼저 확인하세요',
    body: '체형 측정으로 사이즈를 맞추고 가상 착장으로 미리 볼 수 있어요.',
  },
];

// A2 온보딩 — 3장 소개 슬라이드
export default function Onboarding() {
  // 슬라이드 폭 = 창 폭(폰 프레임 상한 적용). 웹이 SPA 라 브라우저에서 항상 정확히 측정된다.
  const { frameWidth: width } = useBreakpoint();

  const [page, setPage] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const p = Math.round(e.nativeEvent.contentOffset.x / width);
    if (p !== page) setPage(p);
  };

  const isLast = page === SLIDES.length - 1;
  const next = () => {
    if (isLast) router.push('/login');
    else scrollRef.current?.scrollTo({ x: width * (page + 1), animated: true });
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        {/* 상단: 워드마크 + 건너뛰기 */}
        <View style={styles.top}>
          <Text style={styles.brand}>cozy</Text>
          <Pressable hitSlop={10} onPress={() => router.push('/login')}>
            <Text style={styles.skip}>건너뛰기</Text>
          </Pressable>
        </View>

        <ScrollView
          ref={scrollRef}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          onScroll={onScroll}
          scrollEventThrottle={16}>
          {SLIDES.map((s) => (
            <View key={s.kicker} style={[styles.slide, { width }]}>
              <SmartImage asset={s.image} height={VISUAL_H} radius={24} contentFit="cover" />
              <Text style={styles.kicker}>{s.kicker}</Text>
              <Text style={styles.title} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.85}>
                {s.title}
              </Text>
              <Text style={styles.body} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.85}>
                {s.body}
              </Text>
            </View>
          ))}
        </ScrollView>

        {/* 하단: 도트 + CTA */}
        <View style={styles.bottom}>
          <View style={styles.dots}>
            {SLIDES.map((s, i) => (
              <View key={s.kicker} style={[styles.dot, i === page && styles.dotOn]} />
            ))}
          </View>
          <Pressable style={styles.cta} onPress={next}>
            <Text style={styles.ctaText}>{isLast ? '시작하기' : '다음'}</Text>
          </Pressable>
          <Pressable style={styles.secondary} onPress={() => router.push('/login')}>
            <Text style={styles.secondaryText}>이미 계정이 있어요</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },

  top: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 30,
    paddingTop: 8,
  },
  brand: { fontFamily: Fonts.serif, fontSize: 22, color: INK },
  skip: { fontSize: 13, color: ink(0.4) },

  slide: { paddingHorizontal: 40, paddingTop: 24, alignItems: 'flex-start' },
  kicker: { fontSize: 11, letterSpacing: 2, color: ink(0.4), fontWeight: '600', marginTop: 34 },
  title: { fontFamily: Fonts.serif, fontSize: 22, color: INK, lineHeight: 28, marginTop: 12 },
  body: { fontSize: 13, color: ink(0.5), lineHeight: 18, marginTop: 10 },

  bottom: { paddingHorizontal: 30, paddingBottom: 8 },
  dots: { flexDirection: 'row', gap: 6, justifyContent: 'center', marginBottom: 22 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: ink(0.15) },
  dotOn: { width: 20, backgroundColor: INK },
  cta: {
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },
  secondary: { alignSelf: 'center', marginTop: 16, paddingVertical: 4 },
  secondaryText: { fontSize: 13, color: ink(0.45) },
});
