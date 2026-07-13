import { router } from 'expo-router';
import { useRef, useState } from 'react';
import {
  Dimensions,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts } from '@/constants/theme';

const INK = '#1c1917';
const BONE = '#ecebe7';
const ink = (a: number) => `rgba(28,25,23,${a})`;

// 웹 데스크톱에선 브라우저 전체 폭이 잡히므로 폰 프레임 폭으로 캡 (global.css와 동일: 440)
const width = Math.min(Dimensions.get('window').width, 440);

const SLIDES = [
  {
    kicker: 'AI STYLIST',
    title: '매일 아침,\n오늘의 룩을 골라드려요',
    body: '날씨와 일정, 당신의 취향을 읽고\nAI 캐릭터가 코디를 제안해요.',
  },
  {
    kicker: 'YOUR CLOSET',
    title: '내 옷장을\n그대로 옮겨보세요',
    body: '사진 한 장이면 AI가 자동으로\n카테고리·색상·소재를 정리해요.',
  },
  {
    kicker: 'FITTING',
    title: '입어보기 전에\n먼저 확인하세요',
    body: '체형 측정으로 사이즈를 매칭하고\n2D 가상 착장으로 미리 봐요.',
  },
];

// A2 온보딩 — 3장 소개 슬라이드
export default function Onboarding() {
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
              <View style={styles.visual}>
                <Text style={styles.visualMark}>A</Text>
              </View>
              <Text style={styles.kicker}>{s.kicker}</Text>
              <Text style={styles.title}>{s.title}</Text>
              <Text style={styles.body}>{s.body}</Text>
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
  visual: {
    alignSelf: 'stretch',
    height: 320,
    borderRadius: 24,
    backgroundColor: BONE,
    alignItems: 'center',
    justifyContent: 'center',
  },
  visualMark: { fontFamily: Fonts.serif, fontSize: 120, color: ink(0.12) },
  kicker: { fontSize: 11, letterSpacing: 2, color: ink(0.4), fontWeight: '600', marginTop: 34 },
  title: { fontFamily: Fonts.serif, fontSize: 28, color: INK, lineHeight: 36, marginTop: 12 },
  body: { fontSize: 14, color: ink(0.5), lineHeight: 22, marginTop: 14 },

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
