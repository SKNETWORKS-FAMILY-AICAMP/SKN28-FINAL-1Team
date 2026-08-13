import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { goBack } from '@/lib/goBack';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import {
  BUDGET_CATEGORIES,
  type BudgetCategory,
  type CategoryBudgets,
  prefsStore,
  usePrefs,
} from '@/state/prefs';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = Editorial.ink;

function toInputs(values: CategoryBudgets): Record<BudgetCategory, string> {
  return Object.fromEntries(
    BUDGET_CATEGORIES.map((category) => [
      category,
      values[category] == null ? '' : String(values[category]! / 10_000),
    ]),
  ) as Record<BudgetCategory, string>;
}

export default function Budget() {
  const { contentStyle } = useBreakpoint();
  const prefs = usePrefs();
  const [inputs, setInputs] = useState(() => toInputs(prefs.categoryBudgets));
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  const change = (category: BudgetCategory, text: string) => {
    setInputs((current) => ({ ...current, [category]: text.replace(/[^0-9]/g, '') }));
  };

  const save = async () => {
    if (saving) return;
    const values = Object.fromEntries(
      BUDGET_CATEGORIES.flatMap((category) => {
        const manwon = Number(inputs[category]);
        return manwon > 0 ? [[category, manwon * 10_000]] : [];
      }),
    ) as CategoryBudgets;

    setSaving(true);
    try {
      await prefsStore.saveBudget(values);
    } catch (error) {
      toast(error instanceof Error ? error.message : '예산을 저장하지 못했어요', {
        variant: 'error',
      });
      return;
    } finally {
      setSaving(false);
    }
    toast('카테고리별 예산을 저장했어요', { variant: 'success' });
    goBack('/(tabs)/my');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>예산 설정</Text>
          <View style={{ width: 20 }} />
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
        <Text style={styles.title}>상품 한 개에 얼마까지 사용할 수 있나요?</Text>
        <Text style={styles.lead}>
          카테고리별 최대 가격을 만원 단위로 입력해주세요. 비워 둔 카테고리는 표시된 기본값을 적용해요.
        </Text>

        <View style={styles.list}>
          {BUDGET_CATEGORIES.map((category) => (
            <View key={category} style={styles.row}>
              <Text style={styles.category}>{category}</Text>
              <View style={[styles.inputRow, inputs[category] && styles.inputRowActive]}>
                <TextInput
                  style={styles.input}
                  value={inputs[category]}
                  onChangeText={(text) => change(category, text)}
                  placeholder={`기본 ${prefs.effectiveCategoryBudgets[category]! / 10_000}`}
                  placeholderTextColor={ink(0.3)}
                  keyboardType="number-pad"
                  accessibilityLabel={`${category} 상품 1개 최대 예산`}
                />
                <Text style={styles.unit}>만원</Text>
              </View>
            </View>
          ))}
        </View>
      </ScrollView>

      <View style={styles.bottomDivider} />
      <View style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
        <Pressable style={[styles.cta, saving && styles.ctaDisabled]} onPress={save} disabled={saving}>
          <Text style={styles.ctaText}>{saving ? '저장 중…' : '저장'}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingTop: 8, paddingBottom: 10,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },
  content: { paddingHorizontal: 24, paddingTop: 12, paddingBottom: 28 },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK, lineHeight: 32 },
  lead: { fontSize: 14, color: Editorial.textCaption, lineHeight: 21, marginTop: 12 },
  list: { marginTop: 28, gap: 12 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 16 },
  category: { flex: 1, fontSize: 15, fontWeight: '600', color: INK },
  inputRow: {
    width: 150, height: 48, flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1, borderColor: ink(0.12), borderRadius: 12,
    paddingHorizontal: 14, backgroundColor: '#fafaf9',
  },
  inputRowActive: { borderColor: Editorial.selected, backgroundColor: Editorial.surface },
  input: { flex: 1, fontSize: 16, textAlign: 'right', color: INK, padding: 0 },
  unit: { fontSize: 13, color: Editorial.textCaption, fontWeight: '600' },
  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { backgroundColor: Editorial.page, paddingHorizontal: 24, paddingTop: 12, paddingBottom: 12 },
  cta: { height: 52, borderRadius: 999, backgroundColor: Editorial.cta, alignItems: 'center', justifyContent: 'center' },
  ctaDisabled: { opacity: 0.6 },
  ctaText: { color: '#fff', fontSize: 15, fontWeight: '500' },
});
