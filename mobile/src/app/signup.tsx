import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useToast } from '@/components/ui';
import { APPLE_LOGIN_ENABLED } from '@/constants/config';
import { Editorial, ink, Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { emailAuthErrorMessage, signupWithEmail } from '@/lib/emailAuth';

const INK = Editorial.ink;
const KAKAO = Editorial.kakao;

type TermKey = 'age' | 'service' | 'privacy' | 'marketing';
const TERMS: { key: TermKey; label: string; required: boolean }[] = [
  { key: 'age', label: '만 14세 이상입니다', required: true },
  { key: 'service', label: '서비스 이용약관 동의', required: true },
  { key: 'privacy', label: '개인정보 수집·이용 동의', required: true },
  { key: 'marketing', label: '마케팅 정보 수신 동의', required: false },
];

/** 최소 검증용 — 서버가 붙으면 진짜 판정은 서버가 한다. 여기선 명백한 오타만 걸러낸다. */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PW = 8;

// A4 회원가입 — 이메일/비밀번호 + 약관 동의 → 권한 동의(A6)로 진입
export default function Signup() {
  const { contentStyle } = useBreakpoint();
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);
  const [agreed, setAgreed] = useState<Set<TermKey>>(new Set());
  const toast = useToast();

  const allChecked = agreed.size === TERMS.length;
  const requiredDone = TERMS.filter((t) => t.required).every((t) => agreed.has(t.key));

  const toggle = (key: TermKey) =>
    setAgreed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const toggleAll = () =>
    setAgreed(allChecked ? new Set() : new Set(TERMS.map((t) => t.key)));

  /* 빈칸·형식 오류를 처음부터 빨갛게 칠하면 아직 아무것도 안 쓴 사람을 나무라는 꼴이 된다.
     한 번 눌러본 뒤부터 보여준다(비밀번호 확인만은 입력 중에도 바로 알린다 — 오타를 늦게 알수록 손해다). */
  const [submitted, setSubmitted] = useState(false);

  const emailError = !email.trim()
    ? '이메일을 입력해 주세요'
    : !EMAIL_RE.test(email.trim())
      ? '이메일 형식이 올바르지 않아요'
      : null;
  const pwError = !pw
    ? '비밀번호를 입력해 주세요'
    : pw.length < MIN_PW
      ? `비밀번호는 ${MIN_PW}자 이상이어야 해요`
      : null;
  const pw2Error = pw2 !== pw ? '비밀번호가 일치하지 않아요' : null;

  const create = async () => {
    setSubmitted(true);
    if (emailError || pwError || pw2Error) return;
    setSaving(true);
    try {
      await signupWithEmail(email, pw);
      router.replace('/permissions');
    } catch (error) {
      toast(emailAuthErrorMessage(error), { variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  /* 소셜 가입은 이메일·비밀번호를 받지 않으므로 폼 검증을 태우지 않는다. */
  const createWithSocial = () => router.replace('/permissions');

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          <Text style={styles.brand}>cozy</Text>
          <Text style={styles.guide} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.85}>
            계정을 만들고 오늘의 코디를 시작하세요
          </Text>

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
            <View style={[styles.underline, submitted && emailError && styles.underlineError]} />
            {submitted && emailError ? <Text style={styles.errText}>{emailError}</Text> : null}
          </View>

          {/* 비밀번호 */}
          <View style={styles.field}>
            <Text style={styles.label}>비밀번호</Text>
            <View style={styles.pwRow}>
              <TextInput
                style={[styles.input, styles.pwInput]}
                value={pw}
                onChangeText={setPw}
                placeholder="8자 이상"
                placeholderTextColor={ink(0.32)}
                secureTextEntry={!show}
              />
              <Pressable hitSlop={8} onPress={() => setShow((s) => !s)}>
                <Text style={styles.showText}>{show ? '숨김' : '표시'}</Text>
              </Pressable>
            </View>
            <View style={[styles.underline, submitted && pwError && styles.underlineError]} />
            {submitted && pwError ? <Text style={styles.errText}>{pwError}</Text> : null}
          </View>

          {/* 비밀번호 확인 */}
          <View style={styles.field}>
            <Text style={styles.label}>비밀번호 확인</Text>
            <TextInput
              style={styles.input}
              value={pw2}
              onChangeText={setPw2}
              placeholder="비밀번호를 다시 입력하세요"
              placeholderTextColor={ink(0.32)}
              secureTextEntry={!show}
            />
            <View
              style={[
                styles.underline,
                pw2.length > 0 && pw2 !== pw && styles.underlineError,
              ]}
            />
            {(pw2.length > 0 || submitted) && pw2Error ? (
              <Text style={styles.errText}>{pw2Error}</Text>
            ) : null}
          </View>

          {/* 약관 동의 */}
          <View style={styles.terms}>
            <Pressable style={styles.termAll} onPress={toggleAll}>
              <View style={[styles.check, allChecked && styles.checkOn]}>
                {allChecked ? <Text style={styles.checkMark}>✓</Text> : null}
              </View>
              <Text style={styles.termAllText}>전체 동의</Text>
            </Pressable>
            <View style={styles.termLine} />
            {TERMS.map((t) => {
              const on = agreed.has(t.key);
              return (
                <Pressable key={t.key} style={styles.termRow} onPress={() => toggle(t.key)}>
                  <View style={[styles.checkSm, on && styles.checkOn]}>
                    {on ? <Text style={styles.checkMarkSm}>✓</Text> : null}
                  </View>
                  <Text style={styles.termText}>
                    <Text style={t.required ? styles.termReq : styles.termOpt}>
                      {t.required ? '[필수] ' : '[선택] '}
                    </Text>
                    {t.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {/* 회원가입 */}
          <Pressable
            style={[styles.cta, (!requiredDone || saving) && styles.ctaDisabled]}
            disabled={!requiredDone || saving}
            onPress={create}>
            {saving ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <Text style={styles.ctaText}>회원가입</Text>
            )}
          </Pressable>

          {/* 또는 */}
          <View style={styles.divider}>
            <View style={styles.line} />
            <Text style={styles.orText}>또는</Text>
            <View style={styles.line} />
          </View>

          <Pressable style={[styles.social, { backgroundColor: KAKAO }]} onPress={createWithSocial}>
            <Text style={styles.socialText}>카카오로 시작하기</Text>
          </Pressable>
          {/* 백엔드가 네이티브 애플을 못 받아 숨겨 뒀다 — config.ts APPLE_LOGIN_ENABLED */}
          {APPLE_LOGIN_ENABLED ? (
            <Pressable style={[styles.social, { backgroundColor: INK }]} onPress={createWithSocial}>
              <Text style={[styles.socialText, styles.socialTextLight]}>Apple로 시작하기</Text>
            </Pressable>
          ) : null}

          {/* 로그인 이동 */}
          <Pressable style={styles.login} onPress={() => goBack('/login')}>
            <Text style={styles.loginText}>
              이미 계정이 있나요? <Text style={styles.loginBold}>로그인</Text>
            </Text>
          </Pressable>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },
  content: { paddingHorizontal: 30, paddingTop: 12, paddingBottom: 30 },

  brand: { fontFamily: Fonts.serif, fontSize: 26, color: INK, marginTop: 12 },
  guide: { fontSize: 18, fontFamily: Fonts.serif, color: Editorial.ink, marginTop: 30, lineHeight: 24 },

  field: { marginTop: 24 },
  label: { fontSize: 10, fontWeight: '500', color: Editorial.textCaption, letterSpacing: 0.2 },
  input: { marginTop: 10, fontSize: 14, color: Editorial.ink, padding: 0 },
  pwRow: { flexDirection: 'row', alignItems: 'center' },
  pwInput: { flex: 1 },
  showText: { fontSize: 12, color: Editorial.textCaption },
  underline: { marginTop: 10, height: 1, backgroundColor: ink(0.15) },
  underlineError: { backgroundColor: Editorial.danger },
  errText: { marginTop: 6, fontSize: 11, color: Editorial.danger },

  // 약관
  terms: { marginTop: 30, gap: 12 },
  termAll: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  termAllText: { fontSize: 14, fontWeight: '600', color: INK },
  termLine: { height: 1, backgroundColor: ink(0.1) },
  termRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  termText: { fontSize: 13, color: Editorial.textCaption },
  termReq: { color: Editorial.ink, fontWeight: '500' },
  termOpt: { color: Editorial.textCaption },
  check: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: ink(0.2),
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkSm: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: ink(0.2),
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  checkMark: { color: '#fff', fontSize: 13, fontWeight: '700' },
  checkMarkSm: { color: '#fff', fontSize: 11, fontWeight: '700' },

  cta: {
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 28,
  },
  ctaDisabled: { backgroundColor: ink(0.22) },
  ctaText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },

  divider: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 24 },
  line: { flex: 1, height: 1, backgroundColor: ink(0.12) },
  orText: { fontSize: 11, color: Editorial.textCaption },

  social: {
    height: 46,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  socialText: { fontSize: 14, fontWeight: '500', color: Editorial.ink },
  socialTextLight: { color: '#ffffff' },

  login: { alignSelf: 'center', marginTop: 24 },
  loginText: { fontSize: 13, color: Editorial.textCaption },
  loginBold: { color: Editorial.ink, fontWeight: '500' },
});
