import { Icon, type IconName } from '@/components/icon';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;

type Key = 'location' | 'photo' | 'notification';
const PERMS: {
  key: Key;
  icon: IconName;
  title: string;
  purpose: string;
  keep: string;
  required: boolean;
}[] = [
  {
    key: 'location',
    icon: 'location',
    title: '위치',
    purpose: '현재 날씨·기온에 맞는 코디를 추천하는 데 사용해요.',
    keep: '실시간 조회만 · 저장 안 함',
    required: true,
  },
  {
    key: 'photo',
    icon: 'photo',
    title: '사진',
    purpose: '옷장 아이템 등록과 체형 측정 사진에 사용해요.',
    keep: '체형 사진은 90일 후 자동 삭제',
    required: true,
  },
  {
    key: 'notification',
    icon: 'bell',
    title: '알림',
    purpose: '아침에 오늘의 룩과 날씨 변화를 알려드려요.',
    keep: '언제든 설정에서 끌 수 있어요',
    required: false,
  },
];

// A6 권한 동의 — 항목별 동의 → 스타일 온보딩(A7)
export default function Permissions() {
  const { contentStyle } = useBreakpoint();
  const [granted, setGranted] = useState<Record<Key, boolean>>({
    location: true,
    photo: true,
    notification: false,
  });

  const requiredOk = PERMS.filter((p) => p.required).every((p) => granted[p.key]);

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}
          showsVerticalScrollIndicator={false}>
          <Text style={styles.eyebrow}>STEP 1 · 권한</Text>
          <Text style={styles.title}>이런 정보가 필요해요</Text>
          <Text style={styles.lead}>
            더 정확한 추천을 위한 권한이에요.{'\n'}필수 항목만 켜도 시작할 수 있어요.
          </Text>

          <View style={styles.list}>
            {PERMS.map((p) => (
              <View key={p.key} style={styles.card}>
                <View style={styles.cardHead}>
                  <View style={styles.iconWrap}>
                    <Icon name={p.icon} tintColor={INK} size={20} />
                  </View>
                  <View style={styles.cardTitleWrap}>
                    <Text style={styles.cardTitle}>
                      {p.title}
                      <Text style={p.required ? styles.req : styles.opt}>
                        {p.required ? '  필수' : '  선택'}
                      </Text>
                    </Text>
                  </View>
                  <Switch
                    value={granted[p.key]}
                    onValueChange={(v) =>
                      setGranted((g) => ({ ...g, [p.key]: v }))
                    }
                    trackColor={{ false: ink(0.12), true: INK }}
                    ios_backgroundColor={ink(0.12)}
                  />
                </View>
                <Text style={styles.purpose}>{p.purpose}</Text>
                <View style={styles.keepRow}>
                  <View style={styles.keepDot} />
                  <Text style={styles.keep}>{p.keep}</Text>
                </View>
              </View>
            ))}
          </View>

          <Text style={styles.foot}>
            권한은 나중에 마이 &gt; 설정에서 언제든 바꿀 수 있어요.
          </Text>
        </ScrollView>

        <View style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
          <Pressable
            style={[styles.cta, !requiredOk && styles.ctaDisabled]}
            disabled={!requiredOk}
            onPress={() => router.push('/style-onboarding')}>
            <Text style={styles.ctaText}>
              {requiredOk ? '허용하고 계속' : '필수 권한을 켜주세요'}
            </Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  content: { paddingHorizontal: 24, paddingTop: 20, paddingBottom: 24 },

  eyebrow: { fontSize: 11, letterSpacing: 1.5, color: ink(0.4), fontWeight: '600' },
  title: { fontFamily: Fonts.serif, fontSize: 28, color: INK, marginTop: 10 },
  lead: { fontSize: 14, color: ink(0.5), lineHeight: 21, marginTop: 12 },

  list: { marginTop: 26, gap: 12 },
  card: {
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 18,
    padding: 16,
    gap: 10,
  },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: '#f3ece2',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitleWrap: { flex: 1 },
  cardTitle: { fontSize: 15, fontWeight: '600', color: INK },
  req: { fontSize: 11, fontWeight: '500', color: '#5E2B2F' },
  opt: { fontSize: 11, fontWeight: '500', color: ink(0.35) },
  purpose: { fontSize: 13, color: ink(0.55), lineHeight: 19 },
  keepRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  keepDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: ink(0.3) },
  keep: { fontSize: 11.5, color: ink(0.4) },

  foot: { fontSize: 12, color: ink(0.38), lineHeight: 18, marginTop: 20, textAlign: 'center' },

  bottomBar: {
    paddingHorizontal: 24,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  cta: {
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaDisabled: { backgroundColor: ink(0.22) },
  ctaText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },
});
