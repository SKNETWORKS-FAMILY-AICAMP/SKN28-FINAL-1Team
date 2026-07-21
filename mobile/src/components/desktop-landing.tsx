import { useEffect } from 'react';
import { Platform, ScrollView, StyleSheet, Text, View } from 'react-native';

import { SmartImage } from '@/components/ui';
import { Editorial, Fonts, ink } from '@/constants/theme';

const CONTENT_MAX = 1120;

const HERO_IMAGE =
  'https://i.pinimg.com/1200x/0b/b1/dc/0bb1dc83e68db247e44f0487f88034bb.jpg';

/** 온보딩과 동일한 3가지 가치 제안 — 카피/이미지 재사용으로 톤 일관성 유지. */
const FEATURES = [
  {
    kicker: 'AI STYLIST',
    image: 'https://i.pinimg.com/736x/af/85/0d/af850da2d1737ba3b6f7475775a2fd54.jpg',
    title: '매일 아침, 오늘의 룩',
    body: '날씨·일정·취향을 반영한 오늘의 코디.',
  },
  {
    kicker: 'YOUR CLOSET',
    image: 'https://i.pinimg.com/1200x/0b/b1/dc/0bb1dc83e68db247e44f0487f88034bb.jpg',
    title: '내 옷장을 그대로',
    body: '사진 한 장으로 끝내는 옷장 정리.',
  },
  {
    kicker: 'FITTING',
    image: 'https://i.pinimg.com/1200x/45/5a/66/455a663d331be1b5d9624939a69fc485.jpg',
    title: '입기 전에 먼저 확인',
    body: '체형 측정과 가상 착장으로 미리 맞추는 핏.',
  },
] as const;

/**
 * 데스크톱('진짜 웹') 랜딩 페이지. useIsDesktop() 이 true 일 때만 렌더된다.
 * 마운트 동안 body 에 풀와이드 클래스를 붙여 폰 프레임(global.css 440 캡)을 해제한다.
 */
export function DesktopLanding() {
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    document.body.classList.add('cozy-landing-fullwidth');
    return () => document.body.classList.remove('cozy-landing-fullwidth');
  }, []);

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.pageContent}>
      {/* 상단 바 */}
      <View style={styles.nav}>
        <View style={styles.navInner}>
          <Text style={styles.brand}>cozy</Text>
        </View>
      </View>

      {/* 히어로 */}
      <View style={styles.section}>
        <View style={[styles.inner, styles.hero]}>
          <View style={styles.heroText}>
            <Text style={styles.heroKicker}>AI 패션 클로젯</Text>
            <Text style={styles.heroTitle}>
              내 옷장에서 시작하는{'\n'}오늘의 스타일
            </Text>
            <Text style={styles.heroBody}>
              새 옷 대신, 이미 가진 옷으로.{'\n'}날씨와 취향을 읽어 완성하는 오늘의 코디.
            </Text>
            <View style={styles.heroActions}>
              <Text style={styles.heroHint}></Text>
            </View>
          </View>
          <View style={styles.heroVisual}>
            <SmartImage uri={HERO_IMAGE} height={440} radius={28} contentFit="cover" />
          </View>
        </View>
      </View>

      {/* 기능 3종 */}
      <View style={[styles.section, styles.featuresSection]}>
        <View style={styles.inner}>
          <Text style={styles.sectionKicker}>WHAT COZY DOES</Text>
          <Text style={styles.sectionTitle}></Text>
          <View style={styles.featureGrid}>
            {FEATURES.map((f) => (
              <View key={f.kicker} style={styles.featureCard}>
                <SmartImage uri={f.image} height={220} radius={20} contentFit="cover" />
                <Text style={styles.featureKicker}>{f.kicker}</Text>
                <Text style={styles.featureTitle}>{f.title}</Text>
                <Text style={styles.featureBody}>{f.body}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      {/* CTA 배너 */}
      <View style={styles.section}>
        <View style={[styles.inner, styles.ctaBand]}>
          <Text style={styles.ctaTitle}>지금, cozy 를 둘러보기</Text>
          <Text style={styles.ctaBody}>cozy 가 그리는 하루를 앱 화면으로.</Text>
        </View>
      </View>

      {/* 푸터 */}
      <View style={styles.footer}>
        <View style={[styles.inner, styles.footerInner]}>
          <Text style={styles.footerBrand}>cozy</Text>
          <Text style={styles.footerText}>SKN28-FINAL-1Team · AI 개인화 패션 추천 서비스</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: Editorial.white },
  pageContent: { paddingBottom: 0 },
  inner: { width: '100%', maxWidth: CONTENT_MAX, marginHorizontal: 'auto' },

  nav: { borderBottomWidth: 1, borderBottomColor: ink(0.06), backgroundColor: Editorial.white },
  navInner: {
    width: '100%',
    maxWidth: CONTENT_MAX,
    marginHorizontal: 'auto',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 40,
    paddingVertical: 20,
  },
  brand: { fontFamily: Fonts.serif, fontSize: 26, color: Editorial.ink },
  navCta: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.18),
  },
  navCtaText: { fontSize: 14, color: Editorial.ink, fontWeight: '500' },

  section: { paddingHorizontal: 40 },

  hero: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 56,
    paddingVertical: 88,
  },
  heroText: { flex: 1, gap: 22 },
  heroKicker: { fontSize: 13, letterSpacing: 3, color: ink(0.45), fontWeight: '600' },
  heroTitle: { fontFamily: Fonts.serif, fontSize: 52, lineHeight: 60, color: Editorial.ink },
  heroBody: { fontSize: 17, lineHeight: 27, color: ink(0.6), maxWidth: 460 },
  heroActions: { gap: 12, marginTop: 8 },
  primaryCta: {
    alignSelf: 'flex-start',
    height: 54,
    paddingHorizontal: 34,
    borderRadius: 999,
    backgroundColor: Editorial.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryCtaText: { color: Editorial.white, fontSize: 16, fontWeight: '600' },
  heroHint: { fontSize: 13, color: ink(0.4) },
  heroVisual: { flex: 1, maxWidth: 520 },

  featuresSection: { backgroundColor: Editorial.surfaceSoft, paddingVertical: 88 },
  sectionKicker: {
    fontSize: 12,
    letterSpacing: 2.5,
    color: ink(0.4),
    fontWeight: '600',
    textAlign: 'center',
  },
  sectionTitle: {
    fontFamily: Fonts.serif,
    fontSize: 34,
    color: Editorial.ink,
    textAlign: 'center',
    marginTop: 12,
  },
  featureGrid: { flexDirection: 'row', gap: 28, marginTop: 48 },
  featureCard: { flex: 1, gap: 10 },
  featureKicker: { fontSize: 11, letterSpacing: 2, color: ink(0.4), fontWeight: '600', marginTop: 16 },
  featureTitle: { fontFamily: Fonts.serif, fontSize: 22, color: Editorial.ink, marginTop: 2 },
  featureBody: { fontSize: 15, lineHeight: 23, color: ink(0.55) },

  ctaBand: {
    alignItems: 'center',
    gap: 14,
    paddingVertical: 96,
  },
  ctaTitle: { fontFamily: Fonts.serif, fontSize: 36, color: Editorial.ink, textAlign: 'center' },
  ctaBody: { fontSize: 16, color: ink(0.55), textAlign: 'center' },
  ctaBandButton: {
    marginTop: 12,
    height: 54,
    paddingHorizontal: 40,
    borderRadius: 999,
    backgroundColor: Editorial.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaBandButtonText: { color: Editorial.white, fontSize: 16, fontWeight: '600' },

  footer: { borderTopWidth: 1, borderTopColor: ink(0.06), backgroundColor: Editorial.white },
  footerInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 40,
    paddingVertical: 36,
  },
  footerBrand: { fontFamily: Fonts.serif, fontSize: 20, color: Editorial.ink },
  footerText: { fontSize: 13, color: ink(0.45) },
});
