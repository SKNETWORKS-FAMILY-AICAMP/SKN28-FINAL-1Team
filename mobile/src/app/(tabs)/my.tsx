import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BottomTabInset, Fonts } from '@/constants/theme';
import { formatBudget, usePrefs } from '@/state/prefs';

const INK = '#1c1917';
const CHIP = '#f3f2ef';
const ink = (a: number) => `rgba(28,25,23,${a})`;

type Row = {
  icon: IconName;
  label: string;
  hint?: string;
  onPress: () => void;
};

const STATS = [
  { num: '42', label: '옷장' },
  { num: '8', label: '저장한 룩' },
  { num: '156', label: '착용 기록' },
];

// H1 마이 탭 — 프로필 요약 + 설정 메뉴
export default function MyScreen() {
  const prefs = usePrefs();
  const groups: { title: string; rows: Row[] }[] = [
    {
      title: '내 정보',
      rows: [
        {
          icon: 'figure.stand',
          label: '체형 정보',
          hint: '측정하기',
          onPress: () => router.push('/measure-input'),
        },
        {
          icon: 'sparkles',
          label: '추구미·선호도',
          hint: '미니멀 외 2',
          onPress: () => router.push('/style-onboarding'),
        },
      ],
    },
    {
      title: '개인화',
      rows: [
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
          contentContainerStyle={styles.content}>
          {/* 프로필 */}
          <View style={styles.profile}>
            <View style={styles.avatar}>
              <Text style={styles.avatarMark}>C</Text>
            </View>
            <View style={styles.profileText}>
              <Text style={styles.name}>코지</Text>
              <Text style={styles.email}>cozy@example.com</Text>
            </View>
            <Pressable style={styles.editBtn}>
              <Text style={styles.editText}>편집</Text>
            </Pressable>
          </View>

          {/* 스탯 */}
          <View style={styles.statsRow}>
            {STATS.map((s, i) => (
              <View key={s.label} style={styles.statTile}>
                {i > 0 ? <View style={styles.statDivider} /> : null}
                <Text style={styles.statNum}>{s.num}</Text>
                <Text style={styles.statLabel}>{s.label}</Text>
              </View>
            ))}
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

  profile: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  avatar: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarMark: { fontFamily: Fonts.serif, fontSize: 26, color: '#fff' },
  profileText: { flex: 1 },
  name: { fontFamily: Fonts.serif, fontSize: 22, fontWeight: '500', color: INK },
  email: { fontSize: 12.5, color: ink(0.45), marginTop: 3 },
  editBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  editText: { fontSize: 12.5, color: ink(0.6), fontWeight: '500' },

  statsRow: {
    flexDirection: 'row',
    marginTop: 24,
    backgroundColor: '#f7f6f3',
    borderRadius: 16,
    paddingVertical: 18,
  },
  statTile: { flex: 1, alignItems: 'center', gap: 4 },
  statDivider: {
    position: 'absolute',
    left: 0,
    top: 4,
    bottom: 4,
    width: 1,
    backgroundColor: ink(0.08),
  },
  statNum: { fontFamily: Fonts.serif, fontSize: 22, fontWeight: '600', color: INK },
  statLabel: { fontSize: 11, color: ink(0.45) },

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
