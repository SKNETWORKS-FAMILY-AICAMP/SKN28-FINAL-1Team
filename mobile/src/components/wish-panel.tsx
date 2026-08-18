import { router } from 'expo-router';
import { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { EmptyState, SmartImage, useConfirm, useToast } from '@/components/ui';
import { Editorial, Fonts, ink } from '@/constants/theme';
import { mallLabel, openExternal, productUrl } from '@/lib/mall';
import { likesStore, useWishlist, type WishItem } from '@/state/likes';
import { categoryBudget, parsePrice, usePrefs } from '@/state/prefs';

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
 * 찜한 상품 목록 본문.
 *
 * 두 자리에서 같은 것을 보여준다 — 옷장의 [찜] 탭과 마이에서 들어오는 `/wishlist` 화면.
 * 화면 껍데기(헤더·스크롤)는 각자 쓰고, 여기는 목록만 그린다.
 *
 * 여기서 하는 일은 둘이다: 담아 둔 걸 다시 보는 것, 그리고 사러 나가는 것.
 * 우리는 결제를 받지 않으므로 마지막 행동은 항상 외부 몰로 나가는 것으로 끝난다.
 */
export function WishPanel() {
  const items = useWishlist();
  const { effectiveCategoryBudgets } = usePrefs();
  const toast = useToast();
  const confirm = useConfirm();

  const total = useMemo(
    () => items.reduce((sum, w) => sum + parsePrice(w.price), 0),
    [items],
  );
  const inBudgetCount = useMemo(
    () => items.filter((w) => {
      const budget = categoryBudget(effectiveCategoryBudgets, w.slot ?? '');
      return budget != null && parsePrice(w.price) <= budget;
    }).length,
    [items, effectiveCategoryBudgets],
  );
  const hasBudget = Object.keys(effectiveCategoryBudgets).length > 0;

  const remove = async (w: WishItem) => {
    if (await confirm({ title: `'${w.name}'을 찜에서 뺄까요?`, destructive: true })) {
      likesStore.removeWish(w.id);
      toast('찜에서 뺐어요');
    }
  };

  const clearAll = async () => {
    if (
      await confirm({
        title: '찜한 상품을 비울까요?',
        message: `담아 둔 ${items.length}개가 모두 사라져요.`,
        destructive: true,
      })
    ) {
      likesStore.clearWishlist();
      toast('찜을 비웠어요');
    }
  };

  if (items.length === 0) {
    return (
      <EmptyState
        icon="heart"
        title="담아 둔 상품이 없어요"
        description="추천받은 코디에서 새로 살 상품에 하트를 누르면 여기 모여요."
        actionLabel="추천받으러 가기"
        onAction={() => router.push('/chat-mode')}
        style={styles.empty}
      />
    );
  }

  return (
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
        {hasBudget ? (
          <>
            <View style={styles.summaryDivider} />
            <View>
              <Text style={styles.summaryLabel}>카테고리 예산 내</Text>
              <Text style={styles.summaryValue}>{inBudgetCount}개</Text>
            </View>
          </>
        ) : null}
        {/* 비우기는 요약 오른쪽 끝에 둔다 — 두 화면이 같은 자리에서 같은 일을 하도록. */}
        <Pressable style={styles.clearBtn} hitSlop={10} onPress={clearAll}>
          <Text style={styles.clearText}>비우기</Text>
        </Pressable>
      </View>

      <View style={styles.list}>
        {items.map((w) => {
          const url = productUrl(w, w.mall);
          const budget = categoryBudget(effectiveCategoryBudgets, w.slot ?? '');
          const inBudget = budget != null && parsePrice(w.price) <= budget;
          /* 브랜드는 추천 API 가 안 내려준다 — 없으면 담은 자리(상의/하의…)로 대신한다.
             빈 줄을 남기면 카드가 어긋나 보인다. */
          const caption = [w.brand, w.slot].filter(Boolean).join(' · ');
          return (
            <View key={w.id} style={styles.row}>
              <Pressable
                style={styles.rowMain}
                onPress={() => openExternal(url)}
                accessibilityLabel={`${w.brand} ${w.name} — ${mallLabel(url)}에서 보기`}>
                {w.image ? (
                  <SmartImage uri={w.image} width={60} height={60} radius={12} />
                ) : (
                  <View style={[styles.thumb, { backgroundColor: `rgba(28,25,23,${w.tone})` }]} />
                )}
                <View style={styles.rowBody}>
                  <Text style={styles.name} numberOfLines={1}>
                    {w.name}
                  </Text>
                  {caption ? <Text style={styles.brand}>{caption}</Text> : null}
                  <View style={styles.priceRow}>
                    {/* 추천 상품에 가격이 비어 오는 경우가 있다 — '원'만 남으면 0원으로 읽힌다. */}
                    <Text style={styles.price}>{w.price ? `${w.price}원` : '가격 미확인'}</Text>
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
                  accessibilityLabel="찜에서 빼기">
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
  );
}

const styles = StyleSheet.create({
  empty: { marginTop: 40 },

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
  clearBtn: { marginLeft: 'auto' },
  clearText: { fontSize: 12.5, color: Editorial.textCaption },

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
