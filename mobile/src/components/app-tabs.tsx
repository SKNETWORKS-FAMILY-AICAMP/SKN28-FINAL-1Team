import { NativeTabs } from 'expo-router/unstable-native-tabs';
import { useColorScheme } from 'react-native';

import { Colors } from '@/constants/theme';

// 하단 5탭: 홈 · 채팅 · 옷장 · 룩북 · 마이
// name="..." 은 (tabs)/ 폴더의 파일명과 일치해야 함 (index = 홈)
export default function AppTabs() {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];

  return (
    <NativeTabs
      backgroundColor={colors.background}
      indicatorColor={colors.backgroundElement}
      labelStyle={{ selected: { color: colors.text } }}>
      <NativeTabs.Trigger name="home">
        <NativeTabs.Trigger.Label>홈</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="house" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="chat">
        <NativeTabs.Trigger.Label>채팅</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="bubble.left" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="closet">
        <NativeTabs.Trigger.Label>옷장</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="tshirt" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="lookbook">
        <NativeTabs.Trigger.Label>룩북</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="book" />
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="my">
        <NativeTabs.Trigger.Label>마이</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="person" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
