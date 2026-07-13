import { useEffect, useRef } from 'react';
import {
  ActivityIndicator,
  Animated,
  Pressable,
  StyleSheet,
  Text,
  View,
  type DimensionValue,
  type ViewStyle,
} from 'react-native';

import { Icon, type IconName } from '@/components/icon';
import { Editorial, ink, Type } from '@/constants/theme';

/**
 * 로딩 상태 — AI 추천 생성 중(최대 5초), 옷장 태깅 중, 가상피팅 생성 중 등.
 * message로 무엇을 기다리는지 알려준다. (스피너 + 안내문)
 */
export function LoadingState({
  message = '불러오는 중…',
  style,
}: {
  message?: string;
  style?: ViewStyle;
}) {
  return (
    <View style={[styles.center, style]}>
      <ActivityIndicator color={Editorial.ink} />
      <Text style={styles.loadingText}>{message}</Text>
    </View>
  );
}

/**
 * 에러 상태 — 네트워크/서버 오류. onRetry가 있으면 '다시 시도' 버튼을 보여준다.
 */
export function ErrorState({
  title = '문제가 생겼어요',
  description = '네트워크 상태를 확인하고 다시 시도해 주세요.',
  onRetry,
  style,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  style?: ViewStyle;
}) {
  return (
    <View style={[styles.center, style]}>
      <View style={styles.errIcon}>
        <Icon name="exclamationmark.triangle" tintColor={Editorial.wine} size={24} />
      </View>
      <Text style={styles.errTitle}>{title}</Text>
      <Text style={styles.errDesc}>{description}</Text>
      {onRetry ? (
        <Pressable style={styles.retry} onPress={onRetry} hitSlop={8}>
          <Icon name="arrow.clockwise" tintColor={Editorial.ink} size={15} />
          <Text style={styles.retryText}>다시 시도</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

/**
 * 스켈레톤 — 콘텐츠가 로드되는 동안 자리를 잡아주는 잔잔한 펄스 블록.
 * 예) 추천 카드/옷장 그리드 로딩 시 실제 카드 크기로 깔아두기.
 */
export function Skeleton({
  width = '100%',
  height = 16,
  radius = 8,
  style,
}: {
  width?: DimensionValue;
  height?: number;
  radius?: number;
  style?: ViewStyle;
}) {
  const pulse = useRef(new Animated.Value(0.5)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 650, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.5, duration: 650, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  return (
    <Animated.View
      style={[
        { width, height, borderRadius: radius, backgroundColor: Editorial.bone, opacity: pulse },
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, paddingVertical: 48 },
  loadingText: { marginTop: 14, fontSize: Type.footnote, color: ink(0.5) },

  errIcon: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Editorial.accent,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  errTitle: { fontSize: Type.label, fontWeight: '600', color: ink(0.85) },
  errDesc: {
    fontSize: Type.footnote,
    color: ink(0.45),
    textAlign: 'center',
    marginTop: 7,
    lineHeight: 20,
  },
  retry: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginTop: 20,
    height: 44,
    paddingHorizontal: 20,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.15),
  },
  retryText: { fontSize: Type.footnote, fontWeight: '600', color: Editorial.ink },
});
