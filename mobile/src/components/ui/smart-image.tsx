import { Image, type ImageContentFit, type ImageSource } from 'expo-image';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View, type DimensionValue, type ViewStyle } from 'react-native';

import { Icon } from '@/components/icon';
import { Editorial, ink } from '@/constants/theme';
import { getImageSource } from '@/lib/resolveImageUri';

/**
 * 이미지 래퍼 — 로딩 중엔 'bone' 배경, 로드 실패(깨짐) 시 사진 아이콘 placeholder.
 * Pinterest 등 hotlink 차단 URL은 getImageSource()가 플랫폼별로 처리한다.
 * 번들에 포함된 로컬 에셋은 asset={require(...)}로 넘긴다 (외부 프록시를 타지 않음).
 *
 * 크기는 height(고정 높이) 또는 aspectRatio(폭에 비례한 높이) 중 하나로 준다.
 * 폭이 화면에 따라 달라지는 자리(그리드 카드 등)에선 aspectRatio 를 써야 비율이 유지된다.
 */
export function SmartImage({
  uri,
  asset,
  width = '100%',
  height,
  aspectRatio,
  radius = 16,
  contentFit = 'cover',
  style,
}: {
  uri?: string | null;
  asset?: number;
  width?: DimensionValue;
  height?: number;
  /** 1 = 정사각형. height 대신 사용하며, 지정 시 height 는 무시된다. */
  aspectRatio?: number;
  radius?: number;
  contentFit?: ImageContentFit;
  style?: ViewStyle;
}) {
  const [failed, setFailed] = useState(false);
  const source = useMemo(() => asset ?? getImageSource(uri), [asset, uri]);

  useEffect(() => {
    setFailed(false);
  }, [asset, uri]);

  const showPlaceholder = !source || failed;

  return (
    <View
      style={[
        {
          width,
          // aspectRatio 를 주면 높이는 폭에서 파생된다 → height 는 넘기지 않는다.
          ...(aspectRatio ? { aspectRatio } : { height }),
          borderRadius: radius,
          backgroundColor: Editorial.bone,
          overflow: 'hidden',
        },
        styles.center,
        style,
      ]}>
      {showPlaceholder ? (
        <Icon name="photo" tintColor={ink(0.28)} size={Math.min((height ?? 140) * 0.28, 40)} />
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
