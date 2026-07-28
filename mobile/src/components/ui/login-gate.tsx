import { router, type Href } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BottomTabInset, ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = Editorial.ink;

/**
 * 비회원이 개인 데이터 화면(옷장·마이)에 들어왔을 때 대신 보여주는 안내.
 *
 * 탭 자체를 막지 않고 화면 안에서 안내한다 — 눌리지 않는 탭은 고장으로 읽히고,
 * 웹에서는 URL 로 바로 들어올 수도 있어 화면 단에서 막는 편이 확실하다.
 */
export function LoginGate({ title, body }: { title: string; body: string }) {
  const { contentStyle } = useBreakpoint();

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={[styles.content, contentStyle(ContentMax.narrow)]}>
          <View style={styles.panel}>
            <Text style={styles.eyebrow}>MEMBERS ONLY</Text>
            <Text style={styles.title}>{title}</Text>
            <Text style={styles.body}>{body}</Text>

            <Pressable style={styles.primary} onPress={() => router.push('/login' as Href)}>
              <Text style={styles.primaryText}>로그인하기</Text>
            </Pressable>
            <Pressable style={styles.secondary} onPress={() => router.replace('/(tabs)/home')}>
              <Text style={styles.secondaryText}>둘러보기 계속하기</Text>
            </Pressable>
          </View>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 24,
    paddingBottom: BottomTabInset,
  },

  panel: {
    borderRadius: 28,
    backgroundColor: Editorial.surface,
    paddingHorizontal: 28,
    paddingVertical: 34,
    alignItems: 'flex-start',
  },
  eyebrow: { fontSize: 10, letterSpacing: 1.7, fontWeight: '600', color: ink(0.45) },
  title: { marginTop: 16, fontFamily: Fonts.serif, fontSize: 26, lineHeight: 34, color: INK },
  body: { marginTop: 12, fontSize: 15, lineHeight: 23, color: ink(0.6) },

  primary: {
    marginTop: 28,
    alignSelf: 'stretch',
    height: 50,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: INK,
  },
  primaryText: { color: '#ffffff', fontSize: 14, fontWeight: '600' },
  secondary: {
    marginTop: 12,
    alignSelf: 'stretch',
    height: 50,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  secondaryText: { fontSize: 14, fontWeight: '600', color: ink(0.7) },
});
