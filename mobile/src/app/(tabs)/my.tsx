import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ink, BottomTabInset, ContentMax, Editorial } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useAuth } from '@/state/auth';
import { formatBudget, usePrefs } from '@/state/prefs';

const INK = Editorial.ink;
const CHIP = Editorial.surface;

type Row = {
  icon: IconName;
  label: string;
  hint?: string;
  onPress: () => void;
};

type Stat = {
  num: string;
  label: string;
  onPress: () => void;
};

const AUTO_USERNAME = /^(naver|kakao|google)_/;

function displayName(
  nickname: string | null | undefined,
  email: string | null | undefined,
): string {
  if (nickname && !AUTO_USERNAME.test(nickname)) return nickname;
  if (email) return email.split('@')[0];
  return '회원';
}

// H1 마이 탭 — 프로필 요약 + 설정 메뉴
export default function MyScreen() {
  const { contentStyle } = useBreakpoint();
  const prefs = usePrefs();
  const { user } = useAuth();
  const name = prefs.nickname || displayName(user?.nickname, user?.email) || '코지';
  const email = user?.email ?? 'cozy@example.com';

  const stats: Stat[] = [
    { num: '42', label: '옷장', onPress: () => router.push('/closet') },
    { num: '8', label: '저장 룩', onPress: () => router.push('/lookbook') },
    { num: '156', label: '착용', onPress: () => router.push('/calendar') },
  ];

  const groups: { title: string; rows: Row[] }[] = [
    {
      title: '내 정보',
      rows: [
        {
          icon: 'figure.stand',
          label: '체형 정보',
          hint: '측정하기',
          onPress: () => router.push({ pathname: '/measure-input', params: { returnTo: 'my' } }),
        },
        {
          icon: 'sparkles',
          label: '추구미·선호도',
          hint: '미니멀 외 2',
          onPress: () => router.push({ pathname: '/style-onboarding', params: { returnTo: 'my' } }),
        },
        {
          icon: 'paintpalette',
          label: '퍼스널컬러',
          hint: prefs.personalColor ?? '설정하기',
          onPress: () => router.push('/personal-color'),
        },
        {
          icon: 'wallet',
          label: '예산',
          hint: formatBudget(prefs.budget) ?? '설정하기',
          onPress: () => router.push('/budget'),
        },
      ],
    },
    {
      title: '설정',
      rows: [
        { icon: 'bell', label: '알림 설정', onPress: () => {} },
        { icon: 'lock', label: '데이터·권한 관리', onPress: () => router.push('/permissions') },
        { icon: 'questionmark.circle', label: '도움말·문의', onPress: () => {} },
      ],
    },
  ];

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
          {/* 프로필 + 활동 요약 */}
          <View style={styles.heroCard}>
            <View style={styles.profile}>
              <View style={styles.avatar} />
              <View style={styles.profileText}>
                <Text style={styles.name}>{name}</Text>
                <Text style={styles.email} numberOfLines={1}>{email}</Text>
              </View>
              <Pressable
                style={styles.editBtn}
                hitSlop={8}
                onPress={() => router.push('/edit-profile')}>
                <Icon name="pencil" tintColor={ink(0.55)} size={14} />
                <Text style={styles.editText}>편집</Text>
              </Pressable>
            </View>

            <View style={styles.statsRow}>
              {stats.map((s, i) => (
                <Pressable key={s.label} style={styles.statTile} onPress={s.onPress}>
                  {i > 0 ? <View style={styles.statDivider} /> : null}
                  <Text style={styles.statNum}>{s.num}</Text>
                  <Text style={styles.statLabel}>{s.label}</Text>
                </Pressable>
              ))}
            </View>
          </View>

          {/* 메뉴 그룹 */}
          {groups.map((g) => (
            <View key={g.title} style={styles.group}>
              <Text style={styles.groupTitle}>{g.title}</Text>
              <View style={styles.card}>
                {g.rows.map((r, i) => (
                  <Pressable key={r.label} onPress={r.onPress}>
                    <View style={styles.row}>
                      <View style={styles.rowIcon}>
                        <Icon name={r.icon} tintColor={INK} size={18} />
                      </View>
                      <Text style={styles.rowLabel}>{r.label}</Text>
                      {r.hint ? <Text style={styles.rowHint}>{r.hint}</Text> : null}
                      <Icon name="chevron.right" tintColor={ink(0.25)} size={14} />
                    </View>
                    {i < g.rows.length - 1 ? <View style={styles.rowLine} /> : null}
                  </Pressable>
                ))}
              </View>
            </View>
          ))}

          <Pressable style={styles.logout} onPress={() => router.replace('/login')}>
            <Text style={styles.logoutText}>로그아웃</Text>
          </Pressable>
          <Text style={styles.version}>cozy · v0.1.0</Text>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: BottomTabInset + 24 },

  heroCard: {
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: Editorial.white,
  },
  profile: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 18,
    paddingTop: 18,
    paddingBottom: 18,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Editorial.accent,
  },
  profileText: { flex: 1, minWidth: 0 },
  name: { fontSize: 18, fontWeight: '700', color: INK, letterSpacing: -0.3 },
  email: { fontSize: 12, color: ink(0.45), marginTop: 2 },
  editBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: Editorial.surfaceSoft,
  },
  editText: { fontSize: 12, color: ink(0.55), fontWeight: '600' },

  statsRow: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: ink(0.07),
    paddingVertical: 15,
    paddingHorizontal: 12,
  },
  statTile: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    paddingVertical: 4,
    position: 'relative',
  },
  statDivider: {
    position: 'absolute',
    left: 0,
    top: 6,
    bottom: 6,
    width: 1,
    backgroundColor: ink(0.08),
  },
  statNum: { fontSize: 18, fontWeight: '600', color: INK, letterSpacing: -0.2 },
  statLabel: { fontSize: 12, color: ink(0.45), fontWeight: '500' },

  group: { marginTop: 28 },
  groupTitle: { fontSize: 12, fontWeight: '600', color: ink(0.4), marginBottom: 10, marginLeft: 4 },
  card: {
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 16,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 15,
  },
  rowIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    backgroundColor: CHIP,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowLabel: { flex: 1, fontSize: 14.5, color: ink(0.9), fontWeight: '500' },
  rowHint: { fontSize: 12.5, color: ink(0.4) },
  rowLine: { height: 1, backgroundColor: ink(0.07), marginLeft: 60 },

  logout: { alignSelf: 'center', marginTop: 30, paddingVertical: 8 },
  logoutText: { fontSize: 13.5, color: ink(0.45) },
  version: { alignSelf: 'center', fontSize: 11, color: ink(0.3), marginTop: 8 },
});
