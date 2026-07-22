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

/* 하단 탭바에는 넣지 않지만 라우트로는 등록해야 하는 화면들.
   TabTrigger 가 트리에 없으면 expo-router 가 라우트를 인식하지 못해 다른 탭이 열린다.
   그래서 모바일 바에서도 숨긴 채로 등록해 둔다. */
const NEW_CHAT_TAB = { name: 'chat-mode', href: '/chat-mode', icon: 'bubble.left', label: '새 채팅' } as const;
const CALENDAR_TAB = { name: 'calendar', href: '/calendar', icon: 'calendar', label: '캘린더' } as const;
/* 사이드바 항목으로는 안 보이지만 (tabs) 안에 있어야 좌측 사이드바가 유지되는 상세·설정 화면들.
   TabTrigger 가 트리에 없으면 expo-router 가 라우트를 인식 못 해 엉뚱한 탭이 열리므로 등록만 해 둔다.
   (탭 그룹 밖 화면은 사이드바 없이 전체폭으로 떠 사이드바가 사라진다. icon 은 hidden 이라 표시 안 됨.) */
const HIDDEN_ROUTES = [
  { name: 'chat-room', href: '/chat-room', icon: 'bubble.left', label: '대화' },
  { name: 'look-detail', href: '/look-detail', icon: 'book', label: '추천 룩' },
  { name: 'fitting', href: '/fitting', icon: 'sparkles', label: '가상 피팅' },
  { name: 'item-detail', href: '/item-detail', icon: 'tshirt', label: '아이템' },
  { name: 'saved-look', href: '/saved-look', icon: 'book', label: '저장 룩' },
  { name: 'budget', href: '/budget', icon: 'person', label: '예산' },
  { name: 'personal-color', href: '/personal-color', icon: 'person', label: '퍼스널컬러' },
  { name: 'style-onboarding', href: '/style-onboarding', icon: 'person', label: '추구미' },
  { name: 'permissions', href: '/permissions', icon: 'person', label: '권한' },
  { name: 'measure-input', href: '/measure-input', icon: 'ruler', label: '체형측정' },
  { name: 'measure-capture', href: '/measure-capture', icon: 'ruler', label: '체형촬영' },
  { name: 'measure-result', href: '/measure-result', icon: 'ruler', label: '체형결과' },
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
  /* 채팅 패널을 띄우지 않는 화면:
     - 채팅 화면 자체(chat-room/chat-mode): 같은 대화가 두 벌로 보이게 된다.
     - 상세 화면(추천룩/가상피팅/아이템상세): 이 화면들은 그 자리를 아이템 2단 배치에 쓴다. */
  const showChatPanel =
    isWide && !['/chat-room', '/chat-mode', '/look-detail', '/fitting', '/item-detail'].includes(pathname);

  return (
    <Tabs style={[styles.root, isDesktop && styles.rootDesktop]}>
      <TabList asChild>
        {isDesktop ? (
          <Sidebar>
            <TabTrigger name={NEW_CHAT_TAB.name} href={NEW_CHAT_TAB.href} asChild>
              <SidebarItem icon={NEW_CHAT_TAB.icon} label={NEW_CHAT_TAB.label} />
            </TabTrigger>
            {TABS.map((t) => (
              <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
                <SidebarItem icon={t.icon} label={t.label} />
              </TabTrigger>
            ))}
            <TabTrigger name={CALENDAR_TAB.name} href={CALENDAR_TAB.href} asChild>
              <SidebarItem icon={CALENDAR_TAB.icon} label={CALENDAR_TAB.label} />
            </TabTrigger>
            {/* 라우트 등록용 — 사이드바 항목으로는 보이지 않는다. */}
            {HIDDEN_ROUTES.map((t) => (
              <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
                <SidebarItem icon={t.icon} label={t.label} hidden />
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
            {/* 라우트 등록용 — 하단 바에는 자리를 차지하지 않게 숨긴다. */}
            {[CALENDAR_TAB, NEW_CHAT_TAB, ...HIDDEN_ROUTES].map((t) => (
              <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
                <TabItem icon={t.icon} label={t.label} hidden />
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

      <View style={styles.sidebarNav}>{children}</View>
    </View>
  );
}

function SidebarItem({
  icon,
  label,
  isFocused,
  hidden,
  ...props
}: TabTriggerSlotProps & { icon: IconName; label: string; hidden?: boolean }) {
  const color = isFocused ? INK : ink(0.5);
  return (
    <Pressable
      {...props}
      style={[styles.sidebarItem, isFocused && styles.sidebarItemOn, hidden && styles.hiddenTrigger]}>
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
  hidden,
  ...props
}: TabTriggerSlotProps & { icon: IconName; label: string; hidden?: boolean }) {
  const color = isFocused ? INK : ink(0.4);
  return (
    <Pressable {...props} style={[styles.item, hidden && styles.hiddenTrigger]}>
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
  hiddenTrigger: { display: 'none' },

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
