import { router } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';

/**
 * 개발 전용 단축 버튼.
 * 어느 화면에서든 눌러 스플래시('/')로 돌아가 첫 실행 플로우를 다시 테스트한다.
 * `__DEV__`가 false인 배포 빌드에서는 렌더되지 않는다.
 */
export function DevReset() {
  if (!__DEV__) return null;
  return (
    <Pressable
      style={styles.btn}
      hitSlop={8}
      onPress={() => router.replace('/')}
      accessibilityLabel="개발용: 스플래시로 이동">
      <Text style={styles.icon}>⟲</Text>
      <Text style={styles.label}>처음</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    position: 'absolute',
    right: 8,
    top: '48%',
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: 'rgba(28,25,23,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
  },
  icon: { color: '#fff', fontSize: 17, lineHeight: 19 },
  label: { color: '#fff', fontSize: 8, fontWeight: '700', letterSpacing: 0.3 },
});
