import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import {
  LayoutAnimation,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  UIManager,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Icon } from '@/components/icon';
import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

if (
  Platform.OS === 'android' &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const INK = '#1c1917';
const WINE = '#5E2B2F';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const STYLES = [
  '미니멀', '캐주얼', '스트릿', '클래식', '러블리',
  '시크', '스포티', '빈티지', '로맨틱', '아메카지', '모던', '보이시',
];
const PREFERRED_COLORS = ['베이지', '화이트', '블랙', '네이비', '브라운', '그레이', '파스텔', '원색'];
const AVOID_COLORS = ['형광', '네온', '쨍한 원색', '올블랙', '파스텔'];
const PREFERRED_FITS = ['레귤러', '슬림', '오버', '루즈', '크롭'];
const AVOID_FITS = ['오버핏', '스키니', '크롭', '노출', '타이트'];

type ChipTone = 'prefer' | 'avoid';

function Chip({
  label,
  on,
  tone,
  onPress,
}: {
  label: string;
  on: boolean;
  tone: ChipTone;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.chip,
        on && (tone === 'prefer' ? styles.chipPreferOn : styles.chipAvoidOn),
      ]}>
      <Text style={[styles.chipText, on && styles.chipTextOn]}>{label}</Text>
    </Pressable>
  );
}

function ChipRow({
  title,
  hint,
  items,
  selected,
  tone,
  onToggle,
}: {
  title: string;
  hint?: string;
  items: string[];
  selected: Set<string>;
  tone: ChipTone;
  onToggle: (v: string) => void;
}) {
  return (
    <View style={styles.subSection}>
      <View style={styles.subHead}>
        <Text style={styles.subTitle}>{title}</Text>
        {selected.size > 0 ? (
          <Text style={styles.subCount}>{selected.size}개</Text>
        ) : hint ? (
          <Text style={styles.subHint}>{hint}</Text>
        ) : null}
      </View>
      <View style={styles.wrap}>
        {items.map((s) => (
          <Chip
            key={s}
            label={s}
            tone={tone}
            on={selected.has(s)}
            onPress={() => onToggle(s)}
          />
        ))}
      </View>
    </View>
  );
}

function PreferenceGroup({
  title,
  desc,
  count,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  desc: string;
  count: number;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.group}>
      <Pressable style={styles.groupHead} onPress={onToggle}>
        <Text style={styles.groupTitle}>{title}</Text>
        <Text style={styles.groupDesc} numberOfLines={1}>
          {expanded ? desc : count > 0 ? `${count}개 선택` : '선택 안 함'}
        </Text>
        <Icon
          name="chevron.down"
          tintColor={ink(0.4)}
          size={16}
          style={expanded ? styles.chevronOpen : undefined}
        />
      </Pressable>
      {expanded ? <View style={styles.groupBody}>{children}</View> : null}
    </View>
  );
}

// A7 스타일 온보딩 — 무드 + 색상/핏 그룹 → 홈 진입
export default function StyleOnboarding() {
  const { contentStyle } = useBreakpoint();
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const [liked, setLiked] = useState<Set<string>>(new Set());
  const [preferredColors, setPreferredColors] = useState<Set<string>>(new Set());
  const [avoidedColors, setAvoidedColors] = useState<Set<string>>(new Set());
  const [preferredFits, setPreferredFits] = useState<Set<string>>(new Set());
  const [avoidedFits, setAvoidedFits] = useState<Set<string>>(new Set());

  const [openSection, setOpenSection] = useState<'mood' | 'color' | 'fit' | null>('mood');

  const toggleSection = (key: 'mood' | 'color' | 'fit') => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setOpenSection((prev) => (prev === key ? null : key));
  };

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, v: string) => {
    const next = new Set(set);
    next.has(v) ? next.delete(v) : next.add(v);
    setter(next);
  };

  const finish = () => {
    if (returnTo === 'my') router.replace('/(tabs)/my');
    else router.replace('/(tabs)/home');
  };

  const selectedCount =
    liked.size +
    preferredColors.size +
    avoidedColors.size +
    preferredFits.size +
    avoidedFits.size;
  const hasSelection = selectedCount > 0;

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <ScrollView
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}
          showsVerticalScrollIndicator={false}>
          <Text style={styles.eyebrow}>STEP 2 · 스타일</Text>
          <Text style={styles.title}>어떤 무드를 추구하세요?</Text>
          <Text style={styles.lead}>고를수록 추천이 정확해져요. 여러 개 골라도 좋아요.</Text>

          {/* 1. 무드 — 페이지 주제 */}
          <View style={[styles.group, styles.firstGroup]}>
            <Pressable style={styles.sectionHead} onPress={() => toggleSection('mood')}>
              <Text style={styles.groupTitle}>추구하는 무드</Text>
              <Text style={styles.count}>{liked.size}개 선택</Text>
              <Icon
                name="chevron.down"
                tintColor={ink(0.4)}
                size={16}
                style={openSection === 'mood' ? styles.chevronOpen : undefined}
              />
            </Pressable>
            {openSection === 'mood' ? (
              <View style={[styles.wrap, styles.moodWrap]}>
                {STYLES.map((s) => (
                  <Chip
                    key={s}
                    label={s}
                    tone="prefer"
                    on={liked.has(s)}
                    onPress={() => toggle(liked, setLiked, s)}
                  />
                ))}
              </View>
            ) : null}
          </View>

          {/* 2. 색상 — 좋아하는 / 피하는 */}
          <PreferenceGroup
            title="색상"
            desc="입고 싶은 톤과 피하고 싶은 톤을 골라주세요"
            count={preferredColors.size + avoidedColors.size}
            expanded={openSection === 'color'}
            onToggle={() => toggleSection('color')}>
            <ChipRow
              title="좋아하는 색"
              hint="선택"
              items={PREFERRED_COLORS}
              selected={preferredColors}
              tone="prefer"
              onToggle={(v) => toggle(preferredColors, setPreferredColors, v)}
            />
            <View style={styles.groupDivider} />
            <ChipRow
              title="피하고 싶은 색"
              hint="선택"
              items={AVOID_COLORS}
              selected={avoidedColors}
              tone="avoid"
              onToggle={(v) => toggle(avoidedColors, setAvoidedColors, v)}
            />
          </PreferenceGroup>

          {/* 3. 핏 — 원하는 / 피하는 */}
          <PreferenceGroup
            title="핏"
            desc="선호하는 실루엣과 피하고 싶은 핏을 골라주세요"
            count={preferredFits.size + avoidedFits.size}
            expanded={openSection === 'fit'}
            onToggle={() => toggleSection('fit')}>
            <ChipRow
              title="원하는 핏"
              hint="선택"
              items={PREFERRED_FITS}
              selected={preferredFits}
              tone="prefer"
              onToggle={(v) => toggle(preferredFits, setPreferredFits, v)}
            />
            <View style={styles.groupDivider} />
            <ChipRow
              title="피하고 싶은 핏"
              hint="선택"
              items={AVOID_FITS}
              selected={avoidedFits}
              tone="avoid"
              onToggle={(v) => toggle(avoidedFits, setAvoidedFits, v)}
            />
          </PreferenceGroup>
        </ScrollView>

        <View style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
          <Pressable style={styles.skip} onPress={finish}>
            <Text style={styles.skipText}>나중에</Text>
          </Pressable>
          <Pressable style={styles.cta} onPress={finish}>
            <Text style={styles.ctaText}>{hasSelection ? '저장하기' : '시작하기'}</Text>
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

  moodBlock: { marginTop: 28, gap: 14 },
  sectionHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: INK },
  count: { flex: 1, fontSize: 12, color: ink(0.4), textAlign: 'right' },
  moodWrap: { rowGap: 9, marginTop: 14 },

  group: {
    marginTop: 16,
    backgroundColor: '#fcffff',
    borderRadius: 18,
    padding: 18,
    borderWidth: 1,
    borderColor: ink(0.06),
  },
  firstGroup: { marginTop: 28 },
  groupHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  groupTitle: { fontSize: 16, fontWeight: '600', color: INK, flexShrink: 0 },
  groupDesc: { flex: 1, fontSize: 12.5, color: ink(0.45), lineHeight: 17 },
  groupBody: { marginTop: 14 },
  groupDivider: { height: 1, backgroundColor: ink(0.08), marginVertical: 14 },
  chevronOpen: { transform: [{ rotate: '180deg' }] },

  subSection: { gap: 12 },
  subHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  subTitle: { fontSize: 14, fontWeight: '600', color: ink(0.75) },
  subCount: { fontSize: 12, color: ink(0.4), fontWeight: '500' },
  subHint: { fontSize: 12, color: ink(0.3) },

  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 },

  chip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    backgroundColor: '#ffffff',
  },
  chipPreferOn: { backgroundColor: WINE, borderColor: WINE },
  chipAvoidOn: { backgroundColor: INK, borderColor: INK },
  chipText: { fontSize: 13.5, color: ink(0.6), fontWeight: '500' },
  chipTextOn: { color: '#ffffff' },

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
  ctaDisabled: { backgroundColor: ink(0.22) },
  ctaText: { color: '#ffffff', fontSize: 15, fontWeight: '500' },
});
