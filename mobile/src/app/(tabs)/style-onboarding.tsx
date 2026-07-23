import { router, useLocalSearchParams } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useMemo, useState } from 'react';
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
import { useToast } from '@/components/ui';
import {
  CATEGORY_OPTIONS,
  CATEGORY_ICONS,
  CATEGORY_ORDER,
  CATEGORY_TITLES,
  type CategoryKey,
  type PreferenceMode,
  type PreferenceOption,
} from '@/constants/pursuit-options';
import { ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

const INK = Editorial.ink;

/* 선호는 앱 기조색(잉크), 기피는 팀 설계의 빨강을 쓴다.
   기피만 팔레트 밖 색인 이유는 '피하고 싶다'가 경고 성격이라 한눈에 구분돼야 하기 때문이다. */
const PREFER = Editorial.ink;
const AVOID = '#FF3B30';

/** 카테고리별 선택 코드 집합 */
type Selection = Record<CategoryKey, Set<string>>;

const emptySelection = (): Selection =>
  CATEGORY_ORDER.reduce((acc, key) => {
    acc[key] = new Set<string>();
    return acc;
  }, {} as Selection);

/* ── 칩 ────────────────────────────────────────────────── */

function Chip({
  option,
  on,
  mode,
  onPress,
}: {
  option: PreferenceOption;
  on: boolean;
  mode: PreferenceMode;
  onPress: () => void;
}) {
  const onStyle = mode === 'preferred' ? styles.chipPreferOn : styles.chipAvoidOn;
  const IconCmp = option.icon;
  return (
    <Pressable onPress={onPress} style={[styles.chip, on && onStyle]}>
      {option.colorHex ? (
        <View style={[styles.swatch, { backgroundColor: option.colorHex }]} />
      ) : IconCmp ? (
        // SVG 아이콘은 stroke 가 짙은 고정색이라, 선택 시 어두워지는 칩에서도
        // 보이도록 흰 타일 위에 얹는다.
        <View style={styles.chipIcon}>
          <IconCmp width={18} height={18} />
        </View>
      ) : null}
      <Text style={[styles.chipText, on && styles.chipTextOn]}>{option.label}</Text>
    </Pressable>
  );
}

/* ── 접히는 카테고리 ────────────────────────────────────── */

function CategorySection({
  icon,
  title,
  count,
  expanded,
  onToggle,
  children,
}: {
  icon?: string;
  title: string;
  count: number;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.group}>
      <Pressable style={styles.groupHead} onPress={onToggle}>
        {icon ? <Text style={styles.groupIcon}>{icon}</Text> : null}
        <Text style={styles.groupTitle}>{title}</Text>
        <Text style={styles.groupCount}>{count > 0 ? `${count}개 선택` : '선택 안 함'}</Text>
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

/**
 * A7 추구미·선호도.
 * 선호/기피 두 모드로 나눠 카테고리별 선택지를 고른다 — 카테고리·코드 체계는 팀 설계를 따른다.
 */
export default function StyleOnboarding() {
  const { contentStyle } = useBreakpoint();
  const toast = useToast();
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();

  const [mode, setMode] = useState<PreferenceMode>('preferred');
  const [preferred, setPreferred] = useState<Selection>(emptySelection);
  const [avoided, setAvoided] = useState<Selection>(emptySelection);
  /* 접을 수는 있되 처음에는 전부 펼쳐 둔다 — 어떤 항목이 있는지 한 번에 보이는 편이 고르기 쉽다. */
  const [openKeys, setOpenKeys] = useState<Set<CategoryKey>>(() => new Set(CATEGORY_ORDER));

  const current = mode === 'preferred' ? preferred : avoided;
  const setCurrent = mode === 'preferred' ? setPreferred : setAvoided;
  const other = mode === 'preferred' ? avoided : preferred;
  const setOther = mode === 'preferred' ? setAvoided : setPreferred;

  const toggleSection = (key: CategoryKey) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleOption = (key: CategoryKey, code: string, label: string) => {
    const adding = !current[key].has(code);

    setCurrent((prev) => {
      const next = { ...prev, [key]: new Set(prev[key]) };
      if (next[key].has(code)) next[key].delete(code);
      else next[key].add(code);
      return next;
    });

    /* 같은 항목을 선호와 기피에 동시에 둘 수는 없다 — 추천이 가산점을 줘야 할지
       감점을 줘야 할지 판단할 수 없는 모순된 데이터가 된다.
       반대쪽에서 자동으로 빼되, 조용히 사라지면 혼란스러우므로 이유를 알린다. */
    if (adding && other[key].has(code)) {
      setOther((prev) => {
        const next = { ...prev, [key]: new Set(prev[key]) };
        next[key].delete(code);
        return next;
      });
      toast(
        mode === 'preferred'
          ? `'${label}' 을(를) 기피 목록에서 뺐어요`
          : `'${label}' 을(를) 선호 목록에서 뺐어요`,
      );
    }
  };

  const totalFor = (sel: Selection) =>
    CATEGORY_ORDER.reduce((n, key) => n + sel[key].size, 0);

  const preferredCount = useMemo(() => totalFor(preferred), [preferred]);
  const avoidedCount = useMemo(() => totalFor(avoided), [avoided]);
  const hasSelection = preferredCount + avoidedCount > 0;

  const finish = () => {
    // TODO(backend): 선택값 저장 API 연동. 지금은 화면 이동만 한다.
    if (returnTo === 'my') router.replace('/(tabs)/my');
    else router.replace('/(tabs)/home');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        {/* 마이 하위 화면들과 동일한 헤더 (뒤로가기 + 가운데 제목) */}
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>추구미·선호도</Text>
          <View style={{ width: 20 }} />
        </View>

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
          <Text style={styles.title}>어떤 옷을 좋아하세요?</Text>
          <Text style={styles.lead}>
            고를수록 추천이 정확해져요. 피하고 싶은 것도 함께 알려주면 더 좋아요.
          </Text>

          {/* 선호 / 기피 모드 */}
          <View style={styles.modeRow}>
            <Pressable
              style={[styles.modeBtn, mode === 'preferred' && styles.modeBtnPreferOn]}
              onPress={() => setMode('preferred')}>
              <Text style={[styles.modeText, mode === 'preferred' && styles.modeTextOn]}>
                선호해요
              </Text>
              {preferredCount > 0 ? (
                <View style={[styles.modeBadge, mode === 'preferred' && styles.modeBadgeOn]}>
                  <Text
                    style={[styles.modeBadgeText, mode === 'preferred' && styles.modeBadgeTextOn]}>
                    {preferredCount}
                  </Text>
                </View>
              ) : null}
            </Pressable>
            <Pressable
              style={[styles.modeBtn, mode === 'avoided' && styles.modeBtnAvoidOn]}
              onPress={() => setMode('avoided')}>
              <Text style={[styles.modeText, mode === 'avoided' && styles.modeTextOn]}>
                피하고 싶어요
              </Text>
              {avoidedCount > 0 ? (
                <View style={[styles.modeBadge, mode === 'avoided' && styles.modeBadgeOn]}>
                  <Text style={[styles.modeBadgeText, mode === 'avoided' && styles.modeBadgeTextOn]}>
                    {avoidedCount}
                  </Text>
                </View>
              ) : null}
            </Pressable>
          </View>

          {CATEGORY_ORDER.map((key) => (
            <CategorySection
              key={key}
              icon={CATEGORY_ICONS[key]}
              title={CATEGORY_TITLES[key]}
              count={current[key].size}
              expanded={openKeys.has(key)}
              onToggle={() => toggleSection(key)}>
              <View style={styles.wrap}>
                {CATEGORY_OPTIONS[key].map((opt) => (
                  <Chip
                    key={opt.code}
                    option={opt}
                    mode={mode}
                    on={current[key].has(opt.code)}
                    onPress={() => toggleOption(key, opt.code, opt.label)}
                  />
                ))}
              </View>
            </CategorySection>
          ))}
        </ScrollView>

        <View style={styles.bottomDivider} />
        <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
          <Pressable style={styles.skipBtn} onPress={finish}>
            <Text style={styles.skipText}>나중에</Text>
          </Pressable>
          <Pressable style={styles.cta} onPress={finish}>
            <Text style={styles.ctaText}>{hasSelection ? '저장하고 시작하기' : '시작하기'}</Text>
          </Pressable>
        </SafeAreaView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.white },
  safe: { flex: 1 },
  content: { paddingHorizontal: 24, paddingTop: 10, paddingBottom: 28 },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingTop: 8,
    paddingBottom: 10,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },
  title: { fontFamily: Fonts.serif, fontSize: 26, color: INK },
  lead: { fontSize: 13, color: ink(0.5), lineHeight: 20, marginTop: 8 },

  // 선호 / 기피 전환
  modeRow: { flexDirection: 'row', gap: 8, marginTop: 22 },
  modeBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    height: 44,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  modeBtnPreferOn: { backgroundColor: PREFER, borderColor: PREFER },
  modeBtnAvoidOn: { backgroundColor: AVOID, borderColor: AVOID },
  modeText: { fontSize: 14, fontWeight: '600', color: ink(0.55) },
  modeTextOn: { color: Editorial.white },
  modeBadge: {
    minWidth: 20,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 999,
    backgroundColor: ink(0.1),
  },
  modeBadgeOn: { backgroundColor: 'rgba(255,255,255,0.25)' },
  modeBadgeText: { fontSize: 11, fontWeight: '700', color: ink(0.55), textAlign: 'center' },
  modeBadgeTextOn: { color: Editorial.white },

  // 카테고리
  group: {
    marginTop: 12,
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 16,
    overflow: 'hidden',
  },
  groupHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 15,
  },
  groupIcon: { fontSize: 15 },
  groupTitle: { fontSize: 14, fontWeight: '600', color: INK },
  groupCount: { flex: 1, fontSize: 12, color: ink(0.4), textAlign: 'right' },
  chevronOpen: { transform: [{ rotate: '180deg' }] },
  groupBody: { paddingHorizontal: 16, paddingBottom: 16 },

  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 36,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  chipPreferOn: { backgroundColor: PREFER, borderColor: PREFER },
  chipAvoidOn: { backgroundColor: AVOID, borderColor: AVOID },
  chipText: { fontSize: 13, color: ink(0.65), fontWeight: '500' },
  chipTextOn: { color: Editorial.white },
  // 색상 칩의 색 견본 — 흰색 계열도 보이도록 얇은 테두리를 둔다.
  swatch: {
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: ink(0.18),
  },
  // 형태 아이콘 타일 — 흰 배경으로 선택/미선택 양쪽에서 아이콘이 보이게 한다.
  chipIcon: {
    width: 22,
    height: 22,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Editorial.white,
  },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: Editorial.white,
    paddingHorizontal: 24,
    paddingTop: 12,
  },
  skipBtn: {
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
  ctaText: { fontSize: 15, fontWeight: '600', color: Editorial.white },
});
