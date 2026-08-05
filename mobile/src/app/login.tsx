import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  TextStyle,
  View,
  ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useToast } from '@/components/ui';
import { APPLE_LOGIN_ENABLED } from '@/constants/config';
import { Editorial, ink, Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useSocialLogin } from '@/hooks/use-social-login';
import type { SocialLoginResult } from '@/lib/socialLogin';
import { authStore } from '@/state/auth';

const INK = Editorial.ink;
const KAKAO = Editorial.kakao;
const NAVER = '#03C75A';

// A3 로그인 — "로그인"/소셜 누르면 앱(홈 탭)으로 진입
export default function Login() {
  const { contentStyle } = useBreakpoint();
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [show, setShow] = useState(false);

  const { kakao, naver, google, apple, pending } = useSocialLogin();
  const toast = useToast();

  /* 백엔드에 이메일/비번 로그인 API 가 없어 데모 세션으로 진입한다.
     둘러보기와 달리 '로그인한 사용자'(authed)로 들어가므로 홈·옷장·마이가 모두 열린다. */
  const enter = () => {
    if (!email.trim() || !pw) {
      toast('이메일과 비밀번호를 입력해 주세요');
      return;
    }
    authStore.signInDemo();
    toast('데모 계정으로 로그인했어요');
    router.replace('/home');
  };

  // 소셜 로그인 성공 시 홈으로. (is_new_user 로 온보딩 분기는 Phase 3에서)
  const onSocial = async (login: () => Promise<SocialLoginResult>) => {
    const result = await login();
    if (result) router.replace('/home');
  };

  // 비회원 진입: 로그인하지 않은 상태를 확정하고 홈으로. (직전 데모 세션이 남아있어도 정리)
  const browseAsGuest = () => {
    authStore.continueAsGuest();
    router.replace('/home');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}
          keyboardShouldPersistTaps="handled">
          <Text style={styles.brand}>cozy</Text>
          <Text style={styles.guide}>로그인하고 오늘의 코디를 받아보세요</Text>

          {/* 이메일 */}
          <View style={styles.field}>
            <Text style={styles.label}>이메일</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={ink(0.32)}
              autoCapitalize="none"
              keyboardType="email-address"
            />
            <View style={styles.underline} />
          </View>

          {/* 비밀번호 */}
          <View style={styles.field}>
            <Text style={styles.label}>비밀번호</Text>
            <View style={styles.pwRow}>
              <TextInput
                style={[styles.input, styles.pwInput]}
                value={pw}
                onChangeText={setPw}
                placeholder="••••••••"
                placeholderTextColor={ink(0.32)}
                secureTextEntry={!show}
              />
              <Pressable hitSlop={8} onPress={() => setShow((s) => !s)}>
                <Text style={styles.showText}>{show ? '숨김' : '표시'}</Text>
              </Pressable>
            </View>
            <View style={styles.underline} />
          </View>

          <Pressable style={styles.forgot} onPress={() => router.push('/reset')}>
            <Text style={styles.forgotText}>비밀번호를 잊으셨나요?</Text>
          </Pressable>

          {/* 로그인 */}
          <Pressable style={styles.loginBtn} onPress={enter}>
            <Text style={styles.loginText}>로그인</Text>
          </Pressable>

          {/* 가입 전에 핵심 경험을 먼저 제공한다. 옷장·마이는 로그인 후에 열린다. */}
          <Pressable style={styles.guest} onPress={browseAsGuest}>
            <Text style={styles.guestText}>로그인 없이 둘러보기</Text>
          </Pressable>
          <Text style={styles.guestHint}>홈·룩북·착장 분석을 먼저 볼 수 있어요</Text>

          {/* 또는 */}
          <View style={styles.divider}>
            <View style={styles.line} />
            <Text style={styles.orText}>또는</Text>
            <View style={styles.line} />
          </View>

          {/* 소셜 로그인 */}
          <SocialButton
            label="카카오로 계속하기"
            style={{ backgroundColor: KAKAO }}
            loading={pending === 'kakao'}
            disabled={pending !== null}
            onPress={() => onSocial(kakao)}
          />
          <SocialButton
            label="네이버로 계속하기"
            style={{ backgroundColor: NAVER }}
            textStyle={styles.socialTextLight}
            spinnerColor="#ffffff"
            loading={pending === 'naver'}
            disabled={pending !== null}
            onPress={() => onSocial(naver)}
          />
          <SocialButton
            label="Google로 계속하기"
            style={styles.socialOutline}
            loading={pending === 'google'}
            disabled={pending !== null}
            onPress={() => onSocial(google)}
          />
          {/* 애플은 iOS 전용 (App Store 정책상 소셜로그인 제공 시 필수).
              지금은 백엔드가 네이티브 애플을 못 받아 숨겨 뒀다 — config.ts APPLE_LOGIN_ENABLED */}
          {APPLE_LOGIN_ENABLED && Platform.OS === 'ios' && (
            <SocialButton
              label="Apple로 계속하기"
              style={{ backgroundColor: INK }}
              textStyle={styles.socialTextLight}
              spinnerColor="#ffffff"
              loading={pending === 'apple'}
              disabled={pending !== null}
              onPress={() => onSocial(apple)}
            />
          )}

          {/* 회원가입 */}
          <Pressable style={styles.signup} onPress={() => router.push('/signup')}>
            <Text style={styles.signupText}>
              아직 계정이 없나요? <Text style={styles.signupBold}>회원가입</Text>
            </Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

// 소셜 로그인 버튼 — 로딩 중이면 스피너, 아니면 라벨
function SocialButton({
  label,
  onPress,
  loading,
  disabled,
  style,
  textStyle,
  spinnerColor = INK,
}: {
  label: string;
  onPress: () => void;
  loading: boolean;
  disabled: boolean;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  spinnerColor?: string;
}) {
  return (
    <Pressable style={[styles.social, style]} onPress={onPress} disabled={disabled}>
      {loading ? (
        <ActivityIndicator color={spinnerColor} />
      ) : (
        <Text style={[styles.socialText, textStyle]}>{label}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },
  content: { paddingHorizontal: 30, paddingTop: 16, paddingBottom: 30 },

  brand: { fontFamily: Fonts.serif, fontSize: 26, color: INK, marginTop: 12 },
  guide: { fontSize: 15, color: Editorial.ink, marginTop: 46 },

  field: { marginTop: 28 },
  label: { fontSize: 10, fontWeight: '500', color: Editorial.textCaption, letterSpacing: 0.2 },
  input: { marginTop: 10, fontSize: 14, color: Editorial.ink, padding: 0 },
  pwRow: { flexDirection: 'row', alignItems: 'center' },
  pwInput: { flex: 1 },
  showText: { fontSize: 12, color: Editorial.textCaption },
  underline: { marginTop: 10, height: 1, backgroundColor: ink(0.15) },

  forgot: { alignSelf: 'flex-end', marginTop: 16 },
  forgotText: { fontSize: 12, color: Editorial.textCaption },

  loginBtn: {
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
  },
  loginText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },

  divider: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 26 },
  line: { flex: 1, height: 1, backgroundColor: ink(0.12) },
  orText: { fontSize: 11, color: Editorial.textCaption },

  social: {
    height: 46,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  socialOutline: { backgroundColor: Editorial.surface, borderWidth: 1, borderColor: ink(0.14) },
  socialText: { fontSize: 14, fontWeight: '500', color: Editorial.ink },
  socialTextLight: { color: '#ffffff' },

  guest: {
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  guestText: { fontSize: 15, fontWeight: '500', color: Editorial.textSoft },
  guestHint: { alignSelf: 'center', marginTop: 10, fontSize: 12, color: Editorial.textCaption },
  signup: { alignSelf: 'center', marginTop: 26 },
  signupText: { fontSize: 13, color: Editorial.textCaption },
  signupBold: { color: Editorial.ink, fontWeight: '500' },
});
