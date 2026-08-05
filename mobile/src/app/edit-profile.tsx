import { Icon } from '@/components/icon';
import { Avatar, ModalShell, useToast } from '@/components/ui';
import { PROFILE_IMAGE } from '@/constants/look-images';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { authStore, useAuth } from '@/state/auth';
import { prefsStore, usePrefs } from '@/state/prefs';

const INK = Editorial.ink;
const AUTO_USERNAME = /^(naver|kakao|google)_/;

/** 계정 별명(자동 생성 제외) → 이메일 앞부분 순으로 기본 표시 이름 후보 */
function accountName(nickname: string | null | undefined, email: string | null | undefined): string {
  if (nickname && !AUTO_USERNAME.test(nickname)) return nickname;
  if (email) return email.split('@')[0];
  return '';
}

// 프로필 편집 (마이 › 편집) — 표시 이름을 바꾼다. 모바일은 전체화면, 데스크톱은 가운데 다이얼로그.
export default function EditProfileScreen() {
  const { contentStyle } = useBreakpoint();
  const prefs = usePrefs();
  const { user } = useAuth();
  const toast = useToast();

  const current = prefs.nickname ?? accountName(user?.nickname, user?.email);
  const [name, setName] = useState(current);
  const email = user?.email ?? 'cozy@example.com';

  const [saving, setSaving] = useState(false);

  /**
   * 이름 저장 — 로컬에 먼저 반영하고 서버에도 남긴다.
   * 로컬을 먼저 하는 이유: 서버가 막혀도 화면에는 방금 바꾼 이름이 보여야 한다.
   * 서버 저장이 실패하면 숨기지 않고 "이 기기에만 저장됐다"고 알린다 —
   * 저장된 줄 알고 다른 기기에서 찾으면 없는 일이 생긴다.
   */
  const save = async () => {
    const trimmed = name.trim();
    prefsStore.setNickname(trimmed);
    if (!trimmed) {
      goBack('/(tabs)/my');
      return;
    }
    setSaving(true);
    try {
      await authStore.updateNickname(trimmed);
      toast('프로필을 저장했어요');
    } catch {
      toast('이 기기에만 저장했어요. 서버에는 반영되지 않았어요', { variant: 'error' });
    } finally {
      setSaving(false);
      goBack('/(tabs)/my');
    }
  };

  return (
    <ModalShell maxWidth={ContentMax.card}>
      <View style={styles.container}>
        <SafeAreaView edges={['top']} style={styles.safe}>
          <View style={[styles.header, contentStyle(ContentMax.card)]}>
            <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
              <Icon name="chevron.left" tintColor={INK} size={22} />
            </Pressable>
            <Text style={styles.headerTitle}>프로필 편집</Text>
            <View style={styles.headerSpacer} />
          </View>

          <View style={[styles.body, contentStyle(ContentMax.card)]}>
            <Avatar name={name} asset={PROFILE_IMAGE} size={84} style={styles.avatar} />

            <Text style={styles.label}>이름</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="표시할 이름"
              placeholderTextColor={ink(0.35)}
              style={styles.input}
              maxLength={20}
              returnKeyType="done"
              onSubmitEditing={save}
            />

            <Text style={[styles.label, styles.labelSpaced]}>이메일</Text>
            <View style={styles.readonly}>
              <Text style={styles.readonlyText} numberOfLines={1}>
                {email}
              </Text>
            </View>
            <Text style={styles.hint}>이메일은 로그인 계정과 연결돼 바꿀 수 없어요.</Text>
          </View>

          <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.card)]}>
            {/* 서버 왕복이 생겼으니 진행 중임을 알리고 두 번 눌리지 않게 막는다. */}
            <Pressable
              style={[styles.saveBtn, (!name.trim() || saving) && styles.saveBtnDisabled]}
              onPress={save}
              disabled={!name.trim() || saving}>
              <Text style={styles.saveText}>{saving ? '저장 중…' : '저장'}</Text>
            </Pressable>
          </SafeAreaView>
        </SafeAreaView>
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.surface },
  safe: { flex: 1 },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 12,
  },
  headerTitle: { fontSize: Type.label, fontWeight: '700', color: INK },
  headerSpacer: { width: 22 },

  body: { flex: 1, paddingHorizontal: 20, paddingTop: 16 },
  avatar: { alignSelf: 'center', marginBottom: 28 },

  label: { fontSize: Type.caption, fontWeight: '600', color: Editorial.textCaption, marginBottom: 8 },
  labelSpaced: { marginTop: 22 },
  input: {
    fontSize: Type.body,
    color: INK,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: ink(0.15),
  },
  readonly: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: ink(0.08) },
  readonlyText: { fontSize: Type.body, color: Editorial.textCaption },
  hint: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 8 },

  bottomBar: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8 },
  saveBtn: {
    height: 52,
    borderRadius: 14,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnDisabled: { opacity: 0.4 },
  saveText: { fontSize: Type.label, fontWeight: '600', color: '#fff' },
});
