import { Image, type ImageContentFit, type ImageSource } from 'expo-image';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View, type DimensionValue, type ViewStyle } from 'react-native';

import { Icon } from '@/components/icon';
import { Editorial, ink } from '@/constants/theme';
import { getImageSource } from '@/lib/resolveImageUri';

/**
 * 이미지 래퍼 — 로딩 중엔 'bone' 배경, 로드 실패(깨짐) 시 사진 아이콘 placeholder.
 * Pinterest 등 hotlink 차단 URL은 getImageSource()가 플랫폼별로 처리한다.
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
  const source = useMemo(() => getImageSource(uri), [uri]);

  useEffect(() => {
    setFailed(false);
  }, [uri]);

  const showPlaceholder = !source || failed;

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
          source={source as ImageSource}
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
