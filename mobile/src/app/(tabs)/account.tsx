import { Icon } from '@/components/icon';
import { useConfirm, useToast } from '@/components/ui';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { SUPPORT_EMAIL } from '@/constants/support';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { goBack } from '@/lib/goBack';
import { useAuth } from '@/state/auth';

const INK = Editorial.ink;

const PROVIDER_LABEL: Record<string, string> = {
  naver: '네이버',
  kakao: '카카오',
  google: '구글',
  apple: '애플',
};

/** 탈퇴하면 사라지는 것 — 무엇이 없어지는지 알고 누르게 한다. */
const DELETED_ON_WITHDRAW = [
  '옷장에 등록한 옷과 사진',
  '체형 치수와 촬영 사진',
  '추구미·퍼스널컬러·예산 설정',
  '저장한 룩과 착장 기록',
];

/**
 * 계정 관리 — 연결된 소셜 계정 확인 · 회원 탈퇴.
 *
 * ⚠️ 계정 삭제 API 가 아직 없다(백엔드 `MeView` 는 GET/PATCH 만, DELETE 미구현).
 *    그래서 **탈퇴가 된 척하지 않는다.** 가짜로 완료를 알리면 사용자는 지워진 줄 알고
 *    떠나지만 데이터는 그대로 남는다 — 그건 죽은 버튼보다 나쁘다.
 *
 * ⚠️ 비밀번호 변경이 여기 없는 이유: 이 서비스는 소셜 로그인 전용이라 **계정에 비밀번호가 없다.**
 *    이메일·비밀번호 로그인이 생기면 그때 같이 만든다.
 */
export default function AccountScreen() {
  const { contentStyle } = useBreakpoint();
  const tabInset = useBottomTabInset();
  const { user } = useAuth();
  const confirm = useConfirm();
  const toast = useToast();

  const accounts = user?.social_accounts ?? [];

  const withdraw = async () => {
    const ok = await confirm({
      title: '정말 탈퇴할까요?',
      message: '옷장·체형·설정이 모두 지워지고 되돌릴 수 없어요.',
      confirmLabel: '탈퇴',
      destructive: true,
    });
    if (!ok) return;
    /* 여기가 DELETE /api/v1/users/me/ 를 부를 자리다. 서버가 생기면 이 줄만 바꾼다. */
    toast('계정 삭제는 아직 서버에 연결되지 않았어요', { variant: 'error' });
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>계정 관리</Text>
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.content,
          { paddingBottom: tabInset + 24 },
          contentStyle(ContentMax.narrow),
        ]}>
        <Text style={styles.sectionTitle}>로그인 방법</Text>
        <View style={styles.card}>
          {accounts.length > 0 ? (
            accounts.map((a, i) => (
              <View key={a.provider}>
                <View style={styles.row}>
                  <Text style={styles.rowLabel}>
                    {PROVIDER_LABEL[a.provider] ?? a.provider}로 로그인
                  </Text>
                  <Text style={styles.rowHint} numberOfLines={1}>
                    {a.email ?? '이메일 미제공'}
                  </Text>
                </View>
                {i < accounts.length - 1 ? <View style={styles.line} /> : null}
              </View>
            ))
          ) : (
            <View style={styles.row}>
              <Text style={styles.rowLabel}>연결된 소셜 계정이 없어요</Text>
            </View>
          )}
        </View>
        <Text style={styles.note}>
          이 서비스는 소셜 로그인으로만 들어와요. 계정에 따로 비밀번호가 없어서 비밀번호 변경도
          없어요.
        </Text>

        <Text style={styles.sectionTitle}>회원 탈퇴</Text>
        <View style={styles.card}>
          <Text style={styles.deleteLead}>탈퇴하면 이런 것들이 사라져요</Text>
          {DELETED_ON_WITHDRAW.map((d) => (
            <View key={d} style={styles.bulletRow}>
              <View style={styles.bullet} />
              <Text style={styles.bulletText}>{d}</Text>
            </View>
          ))}
          <Text style={styles.deleteTail}>
            잠깐 쉬고 싶은 거라면 로그아웃만 해도 돼요. 계정은 그대로 남아요.
          </Text>
        </View>

        <Pressable style={styles.withdrawBtn} onPress={withdraw}>
          <Text style={styles.withdrawText}>회원 탈퇴</Text>
        </Pressable>

        <Text style={styles.note}>
          지금은 탈퇴 요청이 서버에 전달되지 않아요. 계정을 바로 지워야 한다면 {SUPPORT_EMAIL} 로
          알려주세요.
        </Text>

        <Pressable style={styles.logoutLink} onPress={() => router.replace('/(tabs)/my')}>
          <Text style={styles.logoutLinkText}>마이로 돌아가기</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
  },
  headerTitle: { fontSize: Type.label, fontWeight: '600', color: INK },

  content: { paddingHorizontal: 20, paddingTop: 8 },
  sectionTitle: {
    fontSize: Type.caption,
    fontWeight: '600',
    color: Editorial.textCaption,
    marginTop: 26,
    marginBottom: 10,
  },
  card: {
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 16,
    paddingVertical: 4,
  },
  line: { height: 1, backgroundColor: ink(0.07), marginHorizontal: 14 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  rowLabel: { flex: 1, fontSize: Type.footnote, color: INK },
  rowHint: { fontSize: Type.micro, color: Editorial.textCaption, maxWidth: '45%' },

  note: {
    fontSize: Type.micro,
    color: Editorial.textMuted,
    lineHeight: 18,
    marginTop: 10,
    paddingHorizontal: 2,
  },

  deleteLead: {
    fontSize: Type.caption,
    fontWeight: '600',
    color: INK,
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: 8,
  },
  bulletRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 4 },
  bullet: { width: 3, height: 3, borderRadius: 2, backgroundColor: ink(0.35) },
  bulletText: { fontSize: Type.caption, color: Editorial.textSoft },
  deleteTail: {
    fontSize: Type.micro,
    color: Editorial.textCaption,
    lineHeight: 18,
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: 10,
  },

  withdrawBtn: {
    marginTop: 14,
    height: 48,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: Editorial.wine,
    alignItems: 'center',
    justifyContent: 'center',
  },
  withdrawText: { fontSize: Type.footnote, fontWeight: '600', color: Editorial.wine },

  logoutLink: { marginTop: 26, alignItems: 'center', paddingVertical: 10 },
  logoutLinkText: { fontSize: Type.caption, color: Editorial.textCaption },
});
