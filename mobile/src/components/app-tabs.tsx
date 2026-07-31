import { Editorial, ink } from '@/constants/theme';
import { Tabs, TabList, TabSlot, TabTrigger, TabTriggerSlotProps } from 'expo-router/ui';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Icon, type IconName } from './icon';

const INK = Editorial.ink;

// 채팅은 탭이 아니라 가운데 + 버튼에서 시작한다.
const TABS = [
  { name: 'home', href: '/home', icon: 'house', label: '홈' },
  { name: 'closet', href: '/closet', icon: 'tshirt', label: '옷장' },
  { name: 'lookbook', href: '/lookbook', icon: 'book', label: '룩북' },
  { name: 'my', href: '/my', icon: 'person', label: '마이' },
] as const satisfies readonly { name: string; href: string; icon: IconName; label: string }[];

/* 바에는 안 보이지만 (tabs) 안에 있어 **라우트로는 등록해야 하는** 화면들.
   TabTrigger 가 트리에 없으면 expo-router 가 그 라우트를 인식하지 못해
   router.push 가 조용히 무시된다 — 마이의 '체형 정보'·'추구미'가 눌러도 반응이 없던 이유.
   웹(app-tabs.web.tsx)에는 진작 있었는데 네이티브에만 빠져 있었다. */
const HIDDEN_ROUTES = [
  { name: 'chat', href: '/chat' },
  { name: 'chat-room', href: '/chat-room' },
  { name: 'chat-mode', href: '/chat-mode' },
  { name: 'calendar', href: '/calendar' },
  { name: 'item-detail', href: '/item-detail' },
  { name: 'look-detail', href: '/look-detail' },
  { name: 'fitting', href: '/fitting' },
  { name: 'saved-look', href: '/saved-look' },
  { name: 'budget', href: '/budget' },
  { name: 'personal-color', href: '/personal-color' },
  { name: 'style-onboarding', href: '/style-onboarding' },
  { name: 'notifications', href: '/notifications' },
  { name: 'permissions', href: '/permissions' },
  { name: 'measure-input', href: '/measure-input' },
  { name: 'measure-capture', href: '/measure-capture' },
  { name: 'measure-result', href: '/measure-result' },
] as const satisfies readonly { name: string; href: string }[];

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
          {/* 라우트 등록용 — 바에는 자리를 차지하지 않게 숨긴다. */}
          {HIDDEN_ROUTES.map((r) => (
            <TabTrigger key={r.name} name={r.name} href={r.href} asChild>
              <HiddenTrigger />
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

/** 라우트만 등록하고 화면에는 아무것도 그리지 않는 트리거 */
function HiddenTrigger(props: TabTriggerSlotProps) {
  return <Pressable {...props} style={styles.hidden} />;
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
  root: { flex: 1, backgroundColor: Editorial.page },
  slot: { flex: 1 },
  bar: {
    position: 'absolute', left: 0, right: 0, bottom: 0, flexDirection: 'row', alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.96)', borderTopWidth: 1, borderTopColor: ink(0.06), paddingTop: 8,
  },
  item: { flex: 1, alignItems: 'center', gap: 3, paddingVertical: 2 },
  // 라우트 등록만 하고 자리는 차지하지 않는다
  hidden: { width: 0, height: 0, opacity: 0 },
  label: { fontSize: 10.5, letterSpacing: 0.2 },
  askSlot: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  askButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: ink(0.08),
  },
});
