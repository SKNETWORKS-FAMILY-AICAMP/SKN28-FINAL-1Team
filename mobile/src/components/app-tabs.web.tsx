import { router } from 'expo-router';
import { Tabs, TabList, TabTrigger, TabSlot, TabTriggerSlotProps } from 'expo-router/ui';
import { Pressable, View, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Editorial, Fonts, ink } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

import { Icon, type IconName } from './icon';

const INK = Editorial.ink;

/** 데스크톱 사이드바 폭 */
const SIDEBAR_W = 232;

// 채팅은 탭이 아니라 + 버튼에서 시작한다.
const TABS = [
  { name: 'home', href: '/home', icon: 'house', label: '홈' },
  { name: 'closet', href: '/closet', icon: 'tshirt', label: '옷장' },
  { name: 'lookbook', href: '/lookbook', icon: 'book', label: '룩북' },
  { name: 'my', href: '/my', icon: 'person', label: '마이' },
] as const satisfies readonly { name: string; href: string; icon: IconName; label: string }[];

/**
 * 탭 내비게이션 (웹).
 * 창 폭에 따라 하단 탭바(모바일) ↔ 좌측 사이드바(데스크톱)로 바뀐다.
 * 기기 종류가 아니라 폭으로 판단하므로 데스크톱에서 창을 좁혀도 하단 탭바로 되돌아간다.
 *
 * TabList 를 먼저 두는 이유: 데스크톱에선 루트가 가로 배치라 그대로 왼쪽 열이 되고,
 * 모바일에선 하단 바가 position:absolute 라 순서와 무관하게 아래에 뜬다.
 */
export default function AppTabs() {
  const { isDesktop } = useBreakpoint();

  return (
    <Tabs style={[styles.root, isDesktop && styles.rootDesktop]}>
      <TabList asChild>
        {isDesktop ? (
          <Sidebar>
            {TABS.map((t) => (
              <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
                <SidebarItem icon={t.icon} label={t.label} />
              </TabTrigger>
            ))}
          </Sidebar>
        ) : (
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
        )}
      </TabList>
      <TabSlot style={styles.slot} />
    </Tabs>
  );
}

/* ── 데스크톱: 좌측 사이드바 ─────────────────────────────── */

function Sidebar({ children, ...props }: React.ComponentProps<typeof View>) {
  return (
    <View {...props} style={styles.sidebar}>
      <Text style={styles.sidebarBrand}>cozy</Text>

      <Pressable
        style={styles.askWide}
        onPress={() => router.push('/chat-mode')}
        accessibilityLabel="질문하기">
        <Icon name="plus" tintColor={Editorial.white} size={16} />
        <Text style={styles.askWideText}>새 질문</Text>
      </Pressable>

      <View style={styles.sidebarNav}>{children}</View>
    </View>
  );
}

function SidebarItem({
  icon,
  label,
  isFocused,
  ...props
}: TabTriggerSlotProps & { icon: IconName; label: string }) {
  const color = isFocused ? INK : ink(0.5);
  return (
    <Pressable {...props} style={[styles.sidebarItem, isFocused && styles.sidebarItemOn]}>
      <Icon name={icon} tintColor={color} size={20} />
      <Text style={[styles.sidebarLabel, { color, fontWeight: isFocused ? '600' : '500' }]}>
        {label}
      </Text>
    </Pressable>
  );
}

/* ── 모바일: 하단 탭바 ──────────────────────────────────── */

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
      <Text style={[styles.label, { color, fontWeight: isFocused ? '600' : '500' }]}>{label}</Text>
    </Pressable>
  );
}

function AskButton() {
  return (
    <View style={styles.askSlot}>
      <Pressable
        style={styles.askButton}
        onPress={() => router.push('/chat-mode')}
        accessibilityLabel="질문하기">
        <Icon name="plus" tintColor={INK} size={20} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Editorial.white },
  rootDesktop: { flexDirection: 'row' },
  slot: { flex: 1, minWidth: 0 },

  // 데스크톱 사이드바
  sidebar: {
    width: SIDEBAR_W,
    borderRightWidth: 1,
    borderRightColor: ink(0.08),
    backgroundColor: Editorial.white,
    paddingHorizontal: 16,
    paddingTop: 28,
    gap: 8,
  },
  sidebarBrand: {
    fontFamily: Fonts.serif,
    fontSize: 24,
    color: INK,
    paddingHorizontal: 10,
    marginBottom: 20,
  },
  askWide: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 42,
    borderRadius: 10,
    backgroundColor: INK,
    marginBottom: 12,
  },
  askWideText: { color: Editorial.white, fontSize: 14, fontWeight: '600' },
  sidebarNav: { gap: 2 },
  sidebarItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    height: 42,
    paddingHorizontal: 10,
    borderRadius: 10,
  },
  sidebarItemOn: { backgroundColor: Editorial.surfaceSoft },
  sidebarLabel: { fontSize: 14, letterSpacing: -0.1 },

  // 모바일 하단 탭바 — 콘텐츠 위에 떠 있는 글래스 바 (backdrop-filter 는 global.css #cozy-tabbar)
  bar: {
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
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: ink(0.08),
  },
});
