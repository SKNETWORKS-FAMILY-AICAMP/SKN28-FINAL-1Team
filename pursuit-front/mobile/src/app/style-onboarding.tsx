import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { SvgProps } from 'react-native-svg';

import { Fonts } from '@/constants/theme';
import {
  PURSUIT_CATEGORIES,
  PURSUIT_CATEGORY_OPTIONS,
  type PursuitCategoryKey,
  type PursuitOption,
} from '@/constants/pursuitOptions';
import {
  categoryCount,
  clonePreferences,
  stylePrefsStore,
  toggleOption,
  totalCount,
  type PursuitMode,
  type PursuitPreferences,
} from '@/state/stylePrefs';

const INK = '#1c1917';
const BLUE = '#007AFF';
const RED = '#FF3B30';
const ink = (a: number) => `rgba(28,25,23,${a})`;

type ChipTone = 'prefer' | 'avoid';

function Chip({
  label,
  on,
  tone,
  colorHex,
  icon: IconComp,
  onPress,
}: {
  label: string;
  on: boolean;
  tone?: ChipTone;
  colorHex?: string;
  icon?: React.FC<SvgProps>;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.chip,
        on && (tone === 'avoid' ? styles.chipAvoidOn : styles.chipPreferOn),
      ]}>
      {colorHex ? (
        <View
          style={[
            styles.colorDot,
            { backgroundColor: colorHex },
            colorHex.toLowerCase() === '#ffffff' && styles.colorDotBorder,
          ]}
        />
      ) : null}
      {IconComp ? <IconComp width={16} height={16} style={styles.chipIcon} /> : null}
      <Text style={[styles.chipText, on && styles.chipTextOn]}>{label}</Text>
    </Pressable>
  );
}

// 카테고리 하나의 옵션 목록 — 선택 여부에 따라 선호(파란색)/회피(빨간색) 톤이 칩마다 따로 표시된다.
// 어떤 톤이 적용되는지는 칩을 누를 당시의 전역 모드(선호해요/피하고 싶어요)로 결정된다.
function OptionChips({
  options,
  preferredSet,
  avoidedSet,
  onToggle,
}: {
  options: PursuitOption[];
  preferredSet: Set<string>;
  avoidedSet: Set<string>;
  onToggle: (code: string) => void;
}) {
  return (
    <View style={styles.wrap}>
      {options.map((opt) => {
        const isPreferred = preferredSet.has(opt.code);
        const isAvoided = avoidedSet.has(opt.code);
        return (
          <Chip
            key={opt.code}
            label={opt.label}
            colorHex={opt.colorHex}
            icon={opt.icon}
            on={isPreferred || isAvoided}
            tone={isAvoided ? 'avoid' : 'prefer'}
            onPress={() => onToggle(opt.code)}
          />
        );
      })}
    </View>
  );
}

// 카테고리 섹션 — 아코디언 없이 제목 + 옵션을 항상 펼쳐서 보여준다.
function CategorySection({
  title,
  count,
  first,
  children,
}: {
  title: string;
  count: number;
  first?: boolean;
  children: React.ReactNode;
}) {
  return (
    <View style={[styles.group, first && styles.firstGroup]}>
      <View style={styles.groupHead}>
        <Text style={styles.groupTitle}>{title}</Text>
        {count > 0 ? (
          <Text style={styles.groupCount} numberOfLines={1}>
            {count}개 선택
          </Text>
        ) : null}
      </View>
      <View style={styles.groupBody}>{children}</View>
    </View>
  );
}

// A7 스타일 온보딩 — 12개 카테고리 추구미 선호도(선호해요/피하고 싶어요) → My 페이지 또는 홈 진입
// 같은 화면이 온보딩(STEP 2)과 My 페이지의 "추구미·선호도" 편집을 겸한다 (returnTo 로 구분).
export default function StyleOnboarding() {
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const isEditMode = returnTo === 'my';

  const [mode, setMode] = useState<PursuitMode>('preferred');
  // 저장된 선호도를 불러와(내 선호도 조회 mock) 초안으로 편집한다. 저장을 눌러야 스토어에 반영된다.
  const [prefs, setPrefs] = useState<PursuitPreferences>(() =>
    clonePreferences(stylePrefsStore.get()),
  );

  const handleToggleOption = (category: PursuitCategoryKey, code: string) => {
    setPrefs((prev) => toggleOption(prev, mode, category, code));
  };

  const finish = (shouldSave: boolean) => {
    if (shouldSave) stylePrefsStore.save(prefs);
    if (returnTo === 'my') router.replace('/(tabs)/my');
    else router.replace('/(tabs)/home');
  };

  const selectedCount = totalCount(prefs);
  const hasSelection = selectedCount > 0;

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}>
          <Text style={styles.eyebrow}>{isEditMode ? 'MY · 추구미' : 'STEP 2 · 스타일'}</Text>
          <Text style={styles.title}>
            {isEditMode ? '추구미 선호도 편집' : '어떤 무드를 추구하세요?'}
          </Text>
          <Text style={styles.lead}>
            {isEditMode
              ? '선호하는 항목과 피하고 싶은 항목을 카테고리별로 골라주세요.'
              : '고를수록 추천이 정확해져요. 여러 개 골라도 좋아요.'}
          </Text>

          {/* 전역 모드 토글 — 아래 칩을 누르면 지금 선택된 모드로 선호/회피가 기록된다 */}
          <View style={styles.modeRow}>
            <Pressable
              onPress={() => setMode('preferred')}
              style={[styles.modeBtn, mode === 'preferred' && styles.modePreferOn]}>
              <Text style={[styles.modeText, mode === 'preferred' && styles.modeTextOn]}>
                💙 선호해요
              </Text>
            </Pressable>
            <Pressable
              onPress={() => setMode('avoided')}
              style={[styles.modeBtn, mode === 'avoided' && styles.modeAvoidOn]}>
              <Text style={[styles.modeText, mode === 'avoided' && styles.modeTextOn]}>
                🚫 피하고 싶어요
              </Text>
            </Pressable>
          </View>

          {PURSUIT_CATEGORIES.map(({ key, title }, i) => (
            <CategorySection
              key={key}
              title={title}
              count={categoryCount(prefs, key)}
              first={i === 0}>
              <OptionChips
                options={PURSUIT_CATEGORY_OPTIONS[key]}
                preferredSet={new Set(prefs.preferred[key])}
                avoidedSet={new Set(prefs.avoided[key])}
                onToggle={(code) => handleToggleOption(key, code)}
              />
            </CategorySection>
          ))}
        </ScrollView>

        <View style={styles.bottomBar}>
          <Pressable style={styles.skip} onPress={() => finish(false)}>
            <Text style={styles.skipText}>{isEditMode ? '취소' : '나중에'}</Text>
          </Pressable>
          <Pressable style={styles.cta} onPress={() => finish(true)}>
            <Text style={styles.ctaText}>
              {isEditMode ? '저장하기' : hasSelection ? '저장하기' : '시작하기'}
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
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK, marginTop: 10, lineHeight: 30 },
  lead: { fontSize: 14, color: ink(0.5), lineHeight: 21, marginTop: 12 },

  modeRow: { flexDirection: 'row', gap: 10, marginTop: 20 },
  modeBtn: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
  },
  modePreferOn: { backgroundColor: BLUE, borderColor: BLUE },
  modeAvoidOn: { backgroundColor: RED, borderColor: RED },
  modeText: { fontSize: 13.5, fontWeight: '600', color: ink(0.6) },
  modeTextOn: { color: '#ffffff' },

  group: {
    marginTop: 16,
  },
  firstGroup: { marginTop: 24 },
  groupHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  groupTitle: { fontSize: 16, fontWeight: '600', color: INK, flexShrink: 0 },
  groupCount: { fontSize: 12.5, color: ink(0.45), fontWeight: '600', flexShrink: 0 },
  groupBody: { marginTop: 14 },

  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 },

  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    backgroundColor: '#ffffff',
  },
  chipPreferOn: { backgroundColor: BLUE, borderColor: BLUE },
  chipAvoidOn: { backgroundColor: RED, borderColor: RED },
  chipText: { fontSize: 13.5, color: ink(0.6), fontWeight: '500' },
  chipTextOn: { color: '#ffffff' },
  chipIcon: { marginRight: 6 },
  colorDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 6,
  },
  colorDotBorder: { borderWidth: 1, borderColor: ink(0.2) },

  bottomBar: {
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 24,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
  },
  skip: {
    height: 52,
    paddingHorizontal: 22,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  skipText: { fontSize: 14, color: ink(0.55), fontWeight: '500' },
  cta: {
    flex: 1,
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },
});
