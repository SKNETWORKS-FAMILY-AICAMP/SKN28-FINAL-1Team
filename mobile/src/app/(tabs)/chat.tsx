import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BottomTabInset, Fonts } from '@/constants/theme';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

type Session = { id: string; title: string; last: string; time: string };
const GROUPS: { mode: string; tint: string; sessions: Session[] }[] = [
  {
    mode: '추구미 반영',
    tint: '#5E2B2F',
    sessions: [
      { id: '1', title: '가을 데일리 미니멀', last: '이 니트에 슬랙스 매치 어때요?', time: '방금' },
      { id: '2', title: '면접룩 추천', last: '차분한 네이비 코디로 정리했어요', time: '어제' },
    ],
  },
  {
    mode: '옷장 기반',
    tint: '#1c1917',
    sessions: [
      { id: '3', title: '내 트렌치로 코디', last: '보유하신 트렌치 3가지로 제안해요', time: '2일 전' },
      { id: '4', title: '주말 브런치룩', last: '데님에 로퍼로 캐주얼하게', time: '3일 전' },
    ],
  },
];

// C1 채팅 탭 — 모드별 세션 목록 (그룹 접기 지원)
export default function ChatScreen() {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const toggle = (mode: string) => setCollapsed((c) => ({ ...c, [mode]: !c[mode] }));

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        {/* 헤더 */}
        <View style={styles.header}>
          <Text style={styles.title}>채팅</Text>
          <Pressable
            style={styles.newBtn}
            onPress={() => router.push('/chat-mode')}>
            <Icon name="plus" tintColor="#fff" size={15} />
            <Text style={styles.newText}>새 채팅</Text>
          </Pressable>
        </View>

        {/* 검색 */}
        <View style={styles.searchBar}>
          <Icon name="magnifyingglass" tintColor={ink(0.35)} size={16} />
          <Text style={styles.searchPlaceholder}>대화 검색</Text>
        </View>

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}>
          {GROUPS.map((g) => {
            const isCollapsed = collapsed[g.mode];
            return (
            <View key={g.mode} style={styles.group}>
              <Pressable style={styles.groupHead} onPress={() => toggle(g.mode)} hitSlop={8}>
                <View style={[styles.modeDot, { backgroundColor: g.tint }]} />
                <Text style={styles.groupTitle}>{g.mode}</Text>
                <Text style={styles.groupCount}>{g.sessions.length}</Text>
                <View style={styles.groupSpacer} />
                <Icon
                  name={isCollapsed ? 'chevron.right' : 'chevron.down'}
                  tintColor={ink(0.35)}
                  size={14}
                />
              </Pressable>
              {!isCollapsed &&
                g.sessions.map((s) => (
                <Pressable
                  key={s.id}
                  style={styles.session}
                  onPress={() => router.push('/chat-room')}>
                  <View style={[styles.thumb, { backgroundColor: `${g.tint}14` }]}>
                    <Icon name="bubble.left.and.bubble.right" tintColor={g.tint} size={18} />
                  </View>
                  <View style={styles.sessionBody}>
                    <View style={styles.sessionTop}>
                      <Text style={styles.sessionTitle} numberOfLines={1}>{s.title}</Text>
                      <Text style={styles.sessionTime}>{s.time}</Text>
                    </View>
                    <Text style={styles.sessionLast} numberOfLines={1}>{s.last}</Text>
                  </View>
                </Pressable>
              ))}
            </View>
            );
          })}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },

  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 12,
  },
  title: { fontFamily: Fonts.serif, fontSize: 26, fontWeight: '500', color: INK },
  newBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: INK,
    paddingLeft: 12,
    paddingRight: 16,
    height: 38,
    borderRadius: 999,
  },
  newText: { color: '#fff', fontSize: 13, fontWeight: '500' },

  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 20,
    height: 42,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#f3f2ef',
  },
  searchPlaceholder: { fontSize: 13.5, color: ink(0.35) },

  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: BottomTabInset + 24 },
  group: { marginTop: 20 },
  groupHead: { flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 8, paddingVertical: 4 },
  modeDot: { width: 7, height: 7, borderRadius: 3.5 },
  groupTitle: { fontSize: 13, fontWeight: '600', color: ink(0.5) },
  groupCount: {
    fontSize: 11,
    fontWeight: '600',
    color: ink(0.4),
    minWidth: 18,
    height: 18,
    lineHeight: 18,
    textAlign: 'center',
    backgroundColor: '#f0efe9',
    borderRadius: 9,
    overflow: 'hidden',
  },
  groupSpacer: { flex: 1 },

  session: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  thumb: {
    width: 46,
    height: 46,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sessionBody: { flex: 1, gap: 3 },
  sessionTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  sessionTitle: { flex: 1, fontSize: 14.5, fontWeight: '500', color: ink(0.9) },
  sessionTime: { fontSize: 11, color: ink(0.35), marginLeft: 8 },
  sessionLast: { fontSize: 12.5, color: ink(0.45) },
});
