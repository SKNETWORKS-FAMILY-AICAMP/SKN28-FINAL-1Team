import { Tabs, TabList, TabTrigger, TabSlot, TabTriggerSlotProps } from 'expo-router/ui';
import { router } from 'expo-router';
import { Pressable, View, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon, type IconName } from './icon';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

// 채팅은 탭이 아니라 가운데 + 버튼에서 시작한다.
const TABS = [
  { name: 'home', href: '/home', icon: 'house', label: '홈' },
  { name: 'closet', href: '/closet', icon: 'tshirt', label: '옷장' },
  { name: 'lookbook', href: '/lookbook', icon: 'book', label: '룩북' },
  { name: 'my', href: '/my', icon: 'person', label: '마이' },
] as const satisfies readonly { name: string; href: string; icon: IconName; label: string }[];

export default function AppTabs() {
  return (
    <Tabs style={styles.root}>
      {/* 화면 콘텐츠 (남은 공간 전부) */}
      <TabSlot style={styles.slot} />
      {/* 하단 탭바 */}
      <TabList asChild>
        <BottomBar>
          {TABS.slice(0, 2).map((t) => (
            <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
              <TabItem icon={t.icon} label={t.label} />
            </TabTrigger>
          ))}
          <AskButton />
          {TABS.slice(2).map((t) => (
            <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
              <TabItem icon={t.icon} label={t.label} />
            </TabTrigger>
          ))}
        </BottomBar>
      </TabList>
    </Tabs>
  );
}

function BottomBar({ children, ...props }: React.ComponentProps<typeof View>) {
  const insets = useSafeAreaInsets();
  return (
    <View
      {...props}
      nativeID="cozy-tabbar"
      style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 8) }]}>
      {children}
    </View>
  );
}

function TabItem({
  icon,
  label,
  isFocused,
  ...props
}: TabTriggerSlotProps & { icon: IconName; label: string }) {
  const color = isFocused ? INK : ink(0.4);
  return (
    <Pressable {...props} style={styles.item}>
      <Icon name={icon} tintColor={color} size={22} />
      <Text style={[styles.label, { color, fontWeight: isFocused ? '600' : '500' }]}>
        {label}
      </Text>
    </Pressable>
  );
}

function AskButton() {
  return (
    <View style={styles.askSlot}>
      <Pressable style={styles.askButton} onPress={() => router.push('/chat-mode')} accessibilityLabel="질문하기">
        <Icon name="plus" tintColor={INK} size={20} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#ffffff' },
  slot: { flex: 1 },
  bar: {
    // 콘텐츠 위에 떠 있는 글래스 탭바 (backdrop-filter는 global.css의 #cozy-tabbar에서)
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.6)',
    borderTopWidth: 1,
    borderTopColor: ink(0.06),
    paddingTop: 8,
  },
  item: { flex: 1, alignItems: 'center', gap: 3, paddingVertical: 2 },
  label: { fontSize: 10.5, letterSpacing: 0.2 },
  askSlot: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  askButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#f3f2ef',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: ink(0.08),
  },
});
