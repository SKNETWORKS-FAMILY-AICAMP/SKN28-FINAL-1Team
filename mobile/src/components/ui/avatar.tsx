import { StyleSheet, Text, View, type ViewStyle } from 'react-native';

import { SmartImage } from '@/components/ui/smart-image';
import { Editorial, Fonts } from '@/constants/theme';

/**
 * 프로필 아바타 — 사진이 있으면 사진, 없으면 이름 첫 글자를 새긴 모노그램.
 *
 * 사진 업로드가 아직 없어 자리를 비워 두면 흰 원만 남아 '깨진 이미지'처럼 보인다.
 * 지금은 화면들이 목업 사진(PROFILE_IMAGE)을 넘겨 쓰고, 업로드가 붙으면 uri 만 바꿔 끼우면 된다.
 * 사진이 없는 계정은 모노그램으로 떨어진다 — 면은 순백이라 원은 테두리로만 그린다.
 */
export function Avatar({
  name,
  uri,
  asset,
  size = 52,
  style,
}: {
  name?: string | null;
  uri?: string | null;
  /** 번들에 포함된 이미지 — require(...) 결과 */
  asset?: number;
  size?: number;
  style?: ViewStyle;
}) {
  const circle: ViewStyle = { width: size, height: size, borderRadius: size / 2 };

  if (asset || uri) {
    return (
      <SmartImage
        asset={asset}
        uri={uri}
        width={size}
        height={size}
        radius={size / 2}
        style={{ ...styles.photo, ...style }}
      />
    );
  }

  const initial = (name?.trim() || '코').slice(0, 1).toUpperCase();
  return (
    <View style={[styles.circle, circle, style]}>
      <Text style={[styles.initial, { fontSize: size * 0.42 }]}>{initial}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  circle: {
    borderWidth: 1,
    borderColor: Editorial.lineStrong,
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  /* 사진 가장자리가 흰 배경에 묻히지 않게 얇은 테두리를 두른다 */
  photo: { borderWidth: 1, borderColor: Editorial.line },
  initial: { fontFamily: Fonts.serif, color: Editorial.ink, includeFontPadding: false },
});
