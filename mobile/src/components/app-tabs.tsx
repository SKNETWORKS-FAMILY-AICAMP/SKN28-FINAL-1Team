import { Tabs, TabList, TabSlot, TabTrigger, TabTriggerSlotProps } from 'expo-router/ui';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
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
      <TabSlot style={styles.slot} />
      <TabList asChild>
        <BottomBar>
          {TABS.slice(0, 2).map((tab) => (
            <TabTrigger key={tab.name} name={tab.name} href={tab.href} asChild>
              <TabItem icon={tab.icon} label={tab.label} />
            </TabTrigger>
          ))}
          <AskButton />
          {TABS.slice(2).map((tab) => (
            <TabTrigger key={tab.name} name={tab.name} href={tab.href} asChild>
              <TabItem icon={tab.icon} label={tab.label} />
            </TabTrigger>
          ))}
        </BottomBar>
      </TabList>
    </Tabs>
  );
}

function BottomBar({ children, ...props }: React.ComponentProps<typeof View>) {
  const insets = useSafeAreaInsets();
  return <View {...props} style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 8) }]}>{children}</View>;
}

function TabItem({ icon, label, isFocused, ...props }: TabTriggerSlotProps & { icon: IconName; label: string }) {
  const color = isFocused ? INK : ink(0.4);
  return (
    <Pressable {...props} style={styles.item}>
      <Icon name={icon} tintColor={color} size={22} />
      <Text style={[styles.label, { color, fontWeight: isFocused ? '600' : '500' }]}>{label}</Text>
    </Pressable>
  );
}

function AskButton() {
  return (
    <View style={styles.askSlot}>
      <Pressable style={styles.askButton} onPress={() => router.push('/chat-mode')} accessibilityLabel="질문하기">
        <Icon name="plus" tintColor={INK} size={23} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#ffffff' },
  slot: { flex: 1 },
  bar: {
    position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.96)', borderTopWidth: 1, borderTopColor: ink(0.06), paddingTop: 8,
  },
  item: { flex: 1, alignItems: 'center', gap: 3, paddingVertical: 2 },
  label: { fontSize: 10.5, letterSpacing: 0.2 },
  askSlot: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  askButton: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: '#f3f2ef', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: ink(0.08),
  },
});
