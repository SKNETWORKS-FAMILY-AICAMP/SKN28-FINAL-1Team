import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LoginGate } from '@/components/ui';
import { ink, ContentMax, Editorial } from '@/constants/theme';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useAuth } from '@/state/auth';
import { formatBudget, usePrefs } from '@/state/prefs';

const INK = Editorial.ink;

type Row = {
  icon: IconName;
  label: string;
  hint?: string;
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
  const tabInset = useBottomTabInset();
  const prefs = usePrefs();
  const { user, isLoggedIn, signOut } = useAuth();
  const name = prefs.nickname || displayName(user?.nickname, user?.email) || '코지';
  const email = user?.email ?? 'cozy@example.com';

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
        { icon: 'bell', label: '알림 설정', onPress: () => router.push('/notifications') },
        { icon: 'lock', label: '데이터·권한 관리', onPress: () => router.push('/permissions') },
        { icon: 'questionmark.circle', label: '도움말·문의', onPress: () => {} },
      ],
    },
  ];

  // 마이는 계정 화면이라 비회원에게 보여줄 것이 없다. (훅 순서 유지를 위해 전부 호출한 뒤 분기)
  if (!isLoggedIn) {
    return (
      <LoginGate
        title="내 정보는 로그인하고 볼 수 있어요"
        body="체형·추구미 같은 설정은 계정에 저장돼요."
      />
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.content, { paddingBottom: tabInset + 24 }, contentStyle(ContentMax.wide)]}>
          {/* 프로필 — 테두리로 감싸지 않는다. 화면에 하나뿐인 머리라 굳이 구분할 상대가 없다. */}
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

          {/* 이동만 하면 세션이 남는다 — 토큰·데모 표식을 먼저 폐기하고 로그인으로 보낸다. */}
          <Pressable
            style={styles.logout}
            onPress={async () => {
              await signOut();
              router.replace('/login');
            }}>
            <Text style={styles.logoutText}>로그아웃</Text>
          </Pressable>
          <Text style={styles.version}>cozy · v0.1.0</Text>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 16 },

  /* 감싸는 카드가 없으니 좌우 여백은 content 가 이미 준다 — 위아래만 띄운다. */
  profile: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Editorial.accent,
  },
  profileText: { flex: 1, minWidth: 0 },
  name: { fontSize: 18, fontWeight: '700', color: INK, letterSpacing: -0.3 },
  email: { fontSize: 12, color: Editorial.textCaption, marginTop: 2 },
  editBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1, borderColor: Editorial.line,
  },
  editText: { fontSize: 12, color: Editorial.textCaption, fontWeight: '600' },

  group: { marginTop: 28 },
  groupTitle: { fontSize: 12, fontWeight: '600', color: Editorial.textCaption, marginBottom: 10, marginLeft: 4 },
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
    backgroundColor: Editorial.control,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowLabel: { flex: 1, fontSize: 14.5, color: Editorial.ink, fontWeight: '500' },
  rowHint: { fontSize: 12.5, color: Editorial.textCaption },
  rowLine: { height: 1, backgroundColor: ink(0.07), marginLeft: 60 },

  logout: { alignSelf: 'center', marginTop: 30, paddingVertical: 8 },
  logoutText: { fontSize: 13.5, color: Editorial.textCaption },
  version: { alignSelf: 'center', fontSize: 11, color: Editorial.textMuted, marginTop: 8 },
});
