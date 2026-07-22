import { View } from 'react-native';

import { useBreakpoint } from '@/hooks/use-breakpoint';

/**
 * 상세 화면(추천룩·가상피팅·아이템상세) 본문 레이아웃.
 *
 * 데스크톱(사이드바가 뜨는 폭)에선 왼쪽 사진 + 오른쪽 상세·아이템 **2단**으로 배치해
 * 넓은 화면의 가로 공간을 활용한다(이 화면들은 우측 채팅 패널을 끄고 그 자리를 아이템에 쓴다).
 * 태블릿·모바일에선 기존처럼 사진 아래에 상세를 **세로로** 쌓는다.
 */
export function DetailTwoPane({
  image,
  details,
  // 사진은 크게·고정. 오른쪽(상세·아이템)이 남는 폭을 flex 로 채우며 반응형으로 줄어든다.
  imageWidth = 520,
}: {
  image: React.ReactNode;
  details: React.ReactNode;
  imageWidth?: number;
}) {
  const { isDesktop } = useBreakpoint();

  if (!isDesktop) {
    return (
      <>
        {image}
        {details}
      </>
    );
  }

  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 28, paddingHorizontal: 20 }}>
      {/* 사진: 고정 폭으로 크기를 유지(작아지지 않게). */}
      <View style={{ width: imageWidth, flexShrink: 0 }}>{image}</View>
      {/* 상세·아이템: 남는 공간을 채우며 창이 좁아지면 함께 줄어든다. */}
      <View style={{ flex: 1, minWidth: 0 }}>{details}</View>
    </View>
  );
}
