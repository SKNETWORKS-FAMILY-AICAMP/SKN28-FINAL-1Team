import { Icon } from '@/components/icon';
import { EmptyState, useConfirm, useToast } from '@/components/ui';
import { goBack } from '@/lib/goBack';
import { mallLabel, openExternal, productUrl } from '@/lib/mall';
import { likesStore, useWishlist, type WishItem } from '@/state/likes';
import { formatBudget, parsePrice, usePrefs } from '@/state/prefs';
import { router } from 'expo-router';
import { useMemo } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ContentMax, Editorial, Fonts, ink } from '@/constants/theme';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = Editorial.ink;
const WINE = Editorial.wine;

/** 만원 단위 요약 — 총액은 자릿수가 길어 그대로 두면 읽는 데 시간이 걸린다. */
function formatTotal(won: number): string {
  if (won >= 10000) {
    const man = won / 10000;
    return `${Number.isInteger(man) ? man : man.toFixed(1)}만원`;
  }
  return `${won.toLocaleString('ko-KR')}원`;
}

/**
 * 위시리스트 — 추천받은 상품 중 담아 둔 것들.
 *
 * 여기서 하는 일은 둘이다: 담아 둔 걸 다시 보는 것, 그리고 사러 나가는 것.
 * 우리는 결제를 받지 않으므로 마지막 행동은 항상 외부 몰로 나가는 것으로 끝난다.
 */
export default function WishlistScreen() {
  const { contentStyle } = useBreakpoint();
  const tabInset = useBottomTabInset();
  const items = useWishlist();
  const { budget } = usePrefs();
  const toast = useToast();
  const confirm = useConfirm();

  const total = useMemo(
    () => items.reduce((sum, w) => sum + parsePrice(w.price), 0),
    [items],
  );
  /* 예산은 '한 벌에 쓸 돈' 기준으로 받아 둔 값이라 총액과 바로 비교하면 오해를 준다.
     그래서 넘었다고 경고하지 않고, 예산 안에 드는 상품이 몇 개인지만 알려준다. */
  const inBudgetCount = useMemo(
    () => (budget == null ? 0 : items.filter((w) => parsePrice(w.price) <= budget).length),
    [items, budget],
  );

  const remove = async (w: WishItem) => {
    if (await confirm({ title: `'${w.name}'을 위시리스트에서 뺄까요?`, destructive: true })) {
      likesStore.removeWish(w.id);
      toast('위시리스트에서 뺐어요');
    }
  };

  const clearAll = async () => {
    if (
      await confirm({
        title: '위시리스트를 비울까요?',
        message: `담아 둔 ${items.length}개가 모두 사라져요.`,
        destructive: true,
      })
    ) {
      likesStore.clearWishlist();
      toast('위시리스트를 비웠어요');
    }
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>위시리스트</Text>
          {items.length > 0 ? (
            <Pressable style={styles.headerRight} hitSlop={10} onPress={clearAll}>
              <Text style={styles.clearText}>비우기</Text>
            </Pressable>
          ) : null}
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.content,
          { paddingBottom: tabInset + 24 },
          contentStyle(ContentMax.narrow),
        ]}>
        {items.length === 0 ? (
          <EmptyState
            icon="heart"
            title="담아 둔 상품이 없어요"
            description="추천 룩의 구성 아이템을 눌러 비슷한 상품을 펼치면 하트로 담을 수 있어요."
            actionLabel="추천 룩 보러 가기"
            onAction={() => router.push('/look-detail')}
          />
        ) : (
          <>
            <View style={styles.summary}>
              <View>
                <Text style={styles.summaryLabel}>담은 상품</Text>
                <Text style={styles.summaryValue}>{items.length}개</Text>
              </View>
              <View style={styles.summaryDivider} />
              <View>
                <Text style={styles.summaryLabel}>합계</Text>
                <Text style={styles.summaryValue}>{formatTotal(total)}</Text>
              </View>
              {budget != null ? (
                <>
                  <View style={styles.summaryDivider} />
                  <View>
                    <Text style={styles.summaryLabel}>{formatBudget(budget)} 예산 내</Text>
                    <Text style={styles.summaryValue}>{inBudgetCount}개</Text>
                  </View>
                </>
              ) : null}
            </View>

            <View style={styles.list}>
              {items.map((w) => {
                const url = productUrl(w, w.mall);
                const inBudget = budget != null && parsePrice(w.price) <= budget;
                return (
                  <View key={w.id} style={styles.row}>
                    <Pressable
                      style={styles.rowMain}
                      onPress={() => openExternal(url)}
                      accessibilityLabel={`${w.brand} ${w.name} — ${mallLabel(url)}에서 보기`}>
                      <View
                        style={[styles.thumb, { backgroundColor: `rgba(28,25,23,${w.tone})` }]}
                      />
                      <View style={styles.rowBody}>
                        <Text style={styles.name} numberOfLines={1}>
                          {w.name}
                        </Text>
                        <Text style={styles.brand}>
                          {w.brand}
                          {w.slot ? ` · ${w.slot}` : ''}
                        </Text>
                        <View style={styles.priceRow}>
                          <Text style={styles.price}>{w.price}원</Text>
                          {inBudget ? (
                            <View style={styles.budgetTag}>
                              <Text style={styles.budgetTagText}>예산 내</Text>
                            </View>
                          ) : null}
                        </View>
                      </View>
                    </Pressable>

                    <View style={styles.rowActions}>
                      <Pressable
                        style={styles.iconBtn}
                        hitSlop={6}
                        onPress={() => remove(w)}
                        accessibilityLabel="위시리스트에서 빼기">
                        <Icon name="heart.fill" tintColor={WINE} size={17} />
                      </Pressable>
                      <Pressable
                        style={styles.buyBtn}
                        onPress={() => openExternal(url)}
                        accessibilityLabel={`${mallLabel(url)}에서 보기`}>
                        <Text style={styles.buyText}>{mallLabel(url)}</Text>
                        <Icon name="arrow.up.right.square" tintColor="#fff" size={12} />
                      </Pressable>
                    </View>
                  </View>
                );
              })}
            </View>

            <Text style={styles.footnote}>
              구매는 각 쇼핑몰에서 진행돼요. 가격·재고는 판매처 기준입니다.
            </Text>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },
  headerRight: { marginLeft: 'auto' },
  clearText: { fontSize: 13, color: Editorial.textCaption },

  content: { paddingHorizontal: 20, paddingTop: 8 },

  summary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 18,
    paddingVertical: 16,
    paddingHorizontal: 18,
    borderRadius: 16,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  summaryDivider: { width: 1, alignSelf: 'stretch', backgroundColor: ink(0.08) },
  summaryLabel: { fontSize: 11.5, color: Editorial.textCaption },
  summaryValue: { fontFamily: Fonts.serif, fontSize: 19, color: INK, marginTop: 3 },

  list: { marginTop: 18, gap: 12 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 16,
    padding: 12,
  },
  rowMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  thumb: { width: 60, height: 60, borderRadius: 12, backgroundColor: Editorial.bone },
  rowBody: { flex: 1, gap: 3 },
  name: { fontSize: 14, fontWeight: '500', color: INK },
  brand: { fontSize: 12, color: Editorial.textCaption },
  priceRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 1 },
  price: { fontSize: 13.5, fontWeight: '600', color: INK },
  budgetTag: {
    backgroundColor: '#e6efe6',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  budgetTagText: { fontSize: 9.5, color: '#3f6b3f', fontWeight: '700' },

  rowActions: { alignItems: 'flex-end', gap: 8 },
  iconBtn: { width: 30, height: 30, alignItems: 'center', justifyContent: 'center' },
  buyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    height: 30,
    paddingHorizontal: 11,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
  },
  buyText: { fontSize: 11.5, color: '#fff', fontWeight: '600' },

  footnote: {
    marginTop: 18,
    fontSize: 11.5,
    color: Editorial.textMuted,
    textAlign: 'center',
    lineHeight: 18,
  },
});
