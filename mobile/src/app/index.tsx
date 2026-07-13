import { router } from 'expo-router';
import { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Fonts } from '@/constants/theme';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

// A1 스플래시 — 앱 첫 화면("/"). 1.6초 뒤 온보딩으로 (탭하면 바로 넘어감)
export default function Splash() {
  useEffect(() => {
    const t = setTimeout(() => router.replace('/onboarding'), 1600);
    return () => clearTimeout(t);
  }, []);

  return (
    <Pressable style={styles.container} onPress={() => router.replace('/onboarding')}>
      <Text style={styles.brand}>cozy</Text>
      <View style={styles.rule} />
      <Text style={styles.tag}>AI 패션 클로젯</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 14,
  },
  brand: { fontFamily: Fonts.serif, fontSize: 54, color: INK },
  rule: { width: 26, height: 1, backgroundColor: ink(0.5) },
  tag: { fontSize: 13, color: ink(0.5), letterSpacing: 1 },
});
