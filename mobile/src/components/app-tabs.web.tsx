import { router, usePathname } from 'expo-router';
import { Tabs, TabList, TabTrigger, TabSlot, TabTriggerSlotProps } from 'expo-router/ui';
import { Pressable, View, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Editorial, Fonts, ink } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

import { ChatConversation } from './chat/chat-conversation';
import { Icon, type IconName } from './icon';

const INK = Editorial.ink;

/** 데스크톱 사이드바 폭 */
const SIDEBAR_W = 232;

/** 우측 채팅 패널 폭 — 대화는 폭이 넓을수록 읽기 어려워 고정한다. */
const CHAT_PANEL_W = 400;

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
  const { isDesktop, isWide } = useBreakpoint();
  const pathname = usePathname();
  /* 채팅 화면 자체를 보고 있을 땐 패널을 띄우지 않는다 — 같은 대화가 두 벌로 보이게 된다. */
  const showChatPanel = isWide && pathname !== '/chat-room' && pathname !== '/chat-mode';

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
      {showChatPanel ? <ChatPanel /> : null}
    </Tabs>
  );
}

/**
 * 넓은 화면(≥1280)에서 본문 오른쪽에 상주하는 채팅 패널.
 * 옷장·룩북을 보면서 바로 물어볼 수 있게 한다. 폭은 고정 — 대화는 한 줄이 길면 읽기 어렵다.
 */
function ChatPanel() {
  return (
    <View style={styles.chatPanel}>
      <View style={styles.chatPanelHeader}>
        <Text style={styles.chatPanelTitle}>코지에게 물어보기</Text>
        <Pressable
          hitSlop={8}
          onPress={() => router.push('/chat-room')}
          accessibilityLabel="대화 전체 보기">
          <Icon name="arrow.right" tintColor={ink(0.45)} size={16} />
        </Pressable>
      </View>
      <View style={styles.chatPanelDivider} />
      <ChatConversation variant="panel" />
    </View>
  );
}

/* ── 데스크톱: 좌측 사이드바 ─────────────────────────────── */

function Sidebar({ children, ...props }: React.ComponentProps<typeof View>) {
  const pathname = usePathname();

  return (
    <View {...props} style={styles.sidebar}>
      <Text style={styles.sidebarBrand}>cozy</Text>

      <View style={styles.sidebarNav}>
        {/* 탭이 아닌 스택 화면이라 TabTrigger 가 아니라 직접 이동시킨다. */}
        <SidebarLink
          icon="plus"
          label="새 채팅"
          onPress={() => router.push('/chat-mode')}
          active={pathname === '/chat-mode' || pathname === '/chat-room'}
        />
        {children}
        <SidebarLink
          icon="calendar"
          label="캘린더"
          onPress={() => router.push('/calendar')}
          active={pathname === '/calendar'}
        />
      </View>
    </View>
  );
}

/** 탭이 아닌 화면으로 가는 사이드바 항목. 생김새는 SidebarItem 과 동일하게 맞춘다. */
function SidebarLink({
  icon,
  label,
  onPress,
  active,
}: {
  icon: IconName;
  label: string;
  onPress: () => void;
  active: boolean;
}) {
  const color = active ? INK : ink(0.5);
  return (
    <Pressable style={[styles.sidebarItem, active && styles.sidebarItemOn]} onPress={onPress}>
      <Icon name={icon} tintColor={color} size={20} />
      <Text style={[styles.sidebarLabel, { color, fontWeight: active ? '600' : '500' }]}>
        {label}
      </Text>
    </Pressable>
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

  // 우측 채팅 패널 (≥1280)
  chatPanel: {
    width: CHAT_PANEL_W,
    borderLeftWidth: 1,
    borderLeftColor: ink(0.08),
    backgroundColor: Editorial.white,
  },
  chatPanelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 52,
    paddingHorizontal: 16,
  },
  chatPanelTitle: { fontSize: 14, fontWeight: '600', color: INK },
  chatPanelDivider: { height: 1, backgroundColor: ink(0.08) },

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
    /* TabList 가 TabSlot 보다 먼저 오므로(데스크톱에서 왼쪽 열이 되기 위해) 그냥 두면
       뒤에 오는 콘텐츠가 위에 덮여 탭바가 보이지 않는다. */
    zIndex: 10,
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
