import { router } from 'expo-router';
import { useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const KAKAO = '#FEE500';
const ink = (a: number) => `rgba(28,25,23,${a})`;

type TermKey = 'age' | 'service' | 'privacy' | 'marketing';
const TERMS: { key: TermKey; label: string; required: boolean }[] = [
  { key: 'age', label: '만 14세 이상입니다', required: true },
  { key: 'service', label: '서비스 이용약관 동의', required: true },
  { key: 'privacy', label: '개인정보 수집·이용 동의', required: true },
  { key: 'marketing', label: '마케팅 정보 수신 동의', required: false },
];

// A4 회원가입 — 이메일/비밀번호 + 약관 동의 → 권한 동의(A6)로 진입
export default function Signup() {
  const { contentStyle } = useBreakpoint();
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [show, setShow] = useState(false);
  const [agreed, setAgreed] = useState<Set<TermKey>>(new Set());

  const allChecked = agreed.size === TERMS.length;
  const requiredDone = TERMS.filter((t) => t.required).every((t) => agreed.has(t.key));

  const toggle = (key: TermKey) =>
    setAgreed((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const toggleAll = () =>
    setAgreed(allChecked ? new Set() : new Set(TERMS.map((t) => t.key)));

  const create = () => router.replace('/permissions');

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
                placeholder="8자 이상"
                placeholderTextColor={ink(0.32)}
                secureTextEntry={!show}
              />
              <Pressable hitSlop={8} onPress={() => setShow((s) => !s)}>
                <Text style={styles.showText}>{show ? '숨김' : '표시'}</Text>
              </Pressable>
            </View>
            <View style={styles.underline} />
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
            {pw2.length > 0 && pw2 !== pw ? (
              <Text style={styles.errText}>비밀번호가 일치하지 않아요</Text>
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
            style={[styles.cta, !requiredDone && styles.ctaDisabled]}
            disabled={!requiredDone}
            onPress={create}>
            <Text style={styles.ctaText}>회원가입</Text>
          </Pressable>

          {/* 또는 */}
          <View style={styles.divider}>
            <View style={styles.line} />
            <Text style={styles.orText}>또는</Text>
            <View style={styles.line} />
          </View>

          <Pressable style={[styles.social, { backgroundColor: KAKAO }]} onPress={create}>
            <Text style={styles.socialText}>카카오로 시작하기</Text>
          </Pressable>
          <Pressable style={[styles.social, { backgroundColor: INK }]} onPress={create}>
            <Text style={[styles.socialText, styles.socialTextLight]}>Apple로 시작하기</Text>
          </Pressable>

          {/* 로그인 이동 */}
          <Pressable style={styles.login} onPress={() => router.back()}>
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
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: { paddingHorizontal: 30, paddingTop: 12, paddingBottom: 30 },

  brand: { fontFamily: Fonts.serif, fontSize: 26, color: INK, marginTop: 12 },
  guide: { fontSize: 18, fontFamily: Fonts.serif, color: ink(0.9), marginTop: 30, lineHeight: 24 },

  field: { marginTop: 24 },
  label: { fontSize: 10, fontWeight: '500', color: ink(0.42), letterSpacing: 0.2 },
  input: { marginTop: 10, fontSize: 14, color: ink(0.9), padding: 0 },
  pwRow: { flexDirection: 'row', alignItems: 'center' },
  pwInput: { flex: 1 },
  showText: { fontSize: 12, color: ink(0.5) },
  underline: { marginTop: 10, height: 1, backgroundColor: ink(0.15) },
  underlineError: { backgroundColor: '#E23B2E' },
  errText: { marginTop: 6, fontSize: 11, color: '#E23B2E' },

  // 약관
  terms: { marginTop: 30, gap: 12 },
  termAll: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  termAllText: { fontSize: 14, fontWeight: '600', color: INK },
  termLine: { height: 1, backgroundColor: ink(0.1) },
  termRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  termText: { fontSize: 13, color: ink(0.6) },
  termReq: { color: ink(0.85), fontWeight: '500' },
  termOpt: { color: ink(0.4) },
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
  checkOn: { backgroundColor: INK, borderColor: INK },
  checkMark: { color: '#fff', fontSize: 13, fontWeight: '700' },
  checkMarkSm: { color: '#fff', fontSize: 11, fontWeight: '700' },

  cta: {
    height: 48,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 28,
  },
  ctaDisabled: { backgroundColor: ink(0.22) },
  ctaText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },

  divider: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 24 },
  line: { flex: 1, height: 1, backgroundColor: ink(0.12) },
  orText: { fontSize: 11, color: ink(0.4) },

  social: {
    height: 46,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  socialText: { fontSize: 14, fontWeight: '500', color: ink(0.9) },
  socialTextLight: { color: '#ffffff' },

  login: { alignSelf: 'center', marginTop: 24 },
  loginText: { fontSize: 13, color: ink(0.5) },
  loginBold: { color: ink(0.9), fontWeight: '500' },
});
