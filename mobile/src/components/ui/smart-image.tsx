import { Image, type ImageContentFit } from 'expo-image';
import { useState } from 'react';
import { StyleSheet, View, type DimensionValue, type ViewStyle } from 'react-native';

import { Icon } from '@/components/icon';
import { Editorial, ink } from '@/constants/theme';

/**
 * 이미지 래퍼 — 로딩 중엔 'bone' 배경, 로드 실패(깨짐) 시 사진 아이콘 placeholder.
 * 옷장/룩북/룩상세 등 원격 이미지가 들어올 자리에 사용. uri가 없어도 placeholder로 안전하게 뜬다.
 */
export function SmartImage({
  uri,
  width = '100%',
  height,
  radius = 16,
  contentFit = 'cover',
  style,
}: {
  uri?: string | null;
  width?: DimensionValue;
  height: number;
  radius?: number;
  contentFit?: ImageContentFit;
  style?: ViewStyle;
}) {
  const [failed, setFailed] = useState(false);
  const showPlaceholder = !uri || failed;

  return (
    <View
      style={[
        { width, height, borderRadius: radius, backgroundColor: Editorial.bone, overflow: 'hidden' },
        styles.center,
        style,
      ]}>
      {showPlaceholder ? (
        <Icon name="photo" tintColor={ink(0.28)} size={Math.min(height * 0.28, 40)} />
      ) : (
        <Image
          source={{ uri }}
          style={StyleSheet.absoluteFill}
          contentFit={contentFit}
          transition={220}
          onError={() => setFailed(true)}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center' },
});
