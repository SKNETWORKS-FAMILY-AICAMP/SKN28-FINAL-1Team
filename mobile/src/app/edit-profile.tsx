import { Icon } from '@/components/icon';
import { ModalShell, useToast } from '@/components/ui';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useAuth } from '@/state/auth';
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
  const initial = (name.trim() || '코')[0];

  const save = () => {
    prefsStore.setNickname(name);
    toast('프로필을 저장했어요');
    goBack('/(tabs)/my');
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
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{initial}</Text>
            </View>

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
            <Pressable
              style={[styles.saveBtn, !name.trim() && styles.saveBtnDisabled]}
              onPress={save}
              disabled={!name.trim()}>
              <Text style={styles.saveText}>저장</Text>
            </Pressable>
          </SafeAreaView>
        </SafeAreaView>
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.white },
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
  avatar: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: Editorial.bone,
    alignSelf: 'center',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 28,
  },
  avatarText: { fontSize: 32, fontWeight: '700', color: INK },

  label: { fontSize: Type.caption, fontWeight: '600', color: ink(0.5), marginBottom: 8 },
  labelSpaced: { marginTop: 22 },
  input: {
    fontSize: Type.body,
    color: INK,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: ink(0.15),
  },
  readonly: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: ink(0.08) },
  readonlyText: { fontSize: Type.body, color: ink(0.4) },
  hint: { fontSize: Type.micro, color: ink(0.35), marginTop: 8 },

  bottomBar: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8 },
  saveBtn: {
    height: 52,
    borderRadius: 14,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnDisabled: { opacity: 0.4 },
  saveText: { fontSize: Type.label, fontWeight: '600', color: '#fff' },
});
