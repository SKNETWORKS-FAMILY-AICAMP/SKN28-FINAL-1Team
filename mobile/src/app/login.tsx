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

import { Fonts } from '@/constants/theme';
import { useSocialLogin } from '@/hooks/use-social-login';
import type { SocialLoginResult } from '@/lib/socialLogin';

const INK = '#1c1917';
const KAKAO = '#FEE500';
const NAVER = '#03C75A';
const ink = (a: number) => `rgba(28,25,23,${a})`;

// A3 로그인 — "로그인"/소셜 누르면 앱(홈 탭)으로 진입
export default function Login() {
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [show, setShow] = useState(false);

  const { kakao, naver, google, apple, pending } = useSocialLogin();

  const enter = () => router.replace('/home');

  // 소셜 로그인 성공 시 홈으로. (is_new_user 로 온보딩 분기는 Phase 3에서)
  const onSocial = async (login: () => Promise<SocialLoginResult>) => {
    const result = await login();
    if (result) router.replace('/home');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView
          contentContainerStyle={styles.content}
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
          {/* 애플은 iOS 전용 (App Store 정책상 소셜로그인 제공 시 필수) */}
          {Platform.OS === 'ios' && (
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
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: { paddingHorizontal: 30, paddingTop: 16, paddingBottom: 30 },

  brand: { fontFamily: Fonts.serif, fontSize: 26, color: INK, marginTop: 12 },
  guide: { fontSize: 15, color: ink(0.9), marginTop: 46 },

  field: { marginTop: 28 },
  label: { fontSize: 10, fontWeight: '500', color: ink(0.42), letterSpacing: 0.2 },
  input: { marginTop: 10, fontSize: 14, color: ink(0.9), padding: 0 },
  pwRow: { flexDirection: 'row', alignItems: 'center' },
  pwInput: { flex: 1 },
  showText: { fontSize: 12, color: ink(0.5) },
  underline: { marginTop: 10, height: 1, backgroundColor: ink(0.15) },

  forgot: { alignSelf: 'flex-end', marginTop: 16 },
  forgotText: { fontSize: 12, color: ink(0.5) },

  loginBtn: {
    height: 48,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
  },
  loginText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },

  divider: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 26 },
  line: { flex: 1, height: 1, backgroundColor: ink(0.12) },
  orText: { fontSize: 11, color: ink(0.4) },

  social: {
    height: 46,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  socialOutline: { backgroundColor: '#ffffff', borderWidth: 1, borderColor: ink(0.14) },
  socialText: { fontSize: 14, fontWeight: '500', color: ink(0.9) },
  socialTextLight: { color: '#ffffff' },

  signup: { alignSelf: 'center', marginTop: 26 },
  signupText: { fontSize: 13, color: ink(0.5) },
  signupBold: { color: ink(0.9), fontWeight: '500' },
});
