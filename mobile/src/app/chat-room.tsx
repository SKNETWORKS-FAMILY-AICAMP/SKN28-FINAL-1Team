import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatConversation } from '@/components/chat/chat-conversation';
import { Icon } from '@/components/icon';
import { ContentMax, Editorial, ink } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = Editorial.ink;
const WINE = Editorial.wine;

/**
 * C2 채팅 대화 화면.
 * 대화 본문은 ChatConversation 이 담당한다 — 넓은 화면에서 우측 패널로도 같은 컴포넌트를 쓴다.
 */
export default function ChatRoom() {
  const { contentStyle } = useBreakpoint();

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <View style={styles.headerCenter}>
            <Text style={styles.headerTitle}>가을 데일리 미니멀</Text>
            <View style={styles.modeBadge}>
              <View style={styles.modeDot} />
              <Text style={styles.modeText}>추구미 반영</Text>
            </View>
          </View>
          <Pressable hitSlop={12}>
            <Icon name="ellipsis" tintColor={ink(0.5)} size={18} />
          </Pressable>
        </View>
      </SafeAreaView>
      <View style={styles.divider} />

      <ChatConversation variant="screen" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },

  headerSafe: { backgroundColor: '#ffffff' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
  },
  headerCenter: { flex: 1, alignItems: 'center', gap: 3 },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },
  modeBadge: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  modeDot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: WINE },
  modeText: { fontSize: 11, color: ink(0.45) },
  divider: { height: 1, backgroundColor: ink(0.08) },
});
