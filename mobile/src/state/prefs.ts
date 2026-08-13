import { useSyncExternalStore } from 'react';

import { BudgetEndpoint } from '@/constants/config';
import { api } from '@/lib/apiClient';
import { authStore } from '@/state/auth';

/**
 * 개인화 설정(예산·퍼스널컬러) 경량 스토어.
 * draft-item.ts / auth.ts 와 동일한 "모듈 스토어 + useSyncExternalStore" 패턴.
 *
 * **예산만 서버에 남는다**(`/api/v1/users/me/budget/`). 별명·퍼스널컬러는 아직 서버에
 * 자리가 없어 메모리 보관이라 앱을 껐다 켜면 사라진다.
 */
export type Prefs = {
  nickname: string | null; // 프로필 편집에서 정한 표시 이름 (미설정이면 계정 별명으로 폴백)
  categoryBudgets: CategoryBudgets;
  effectiveCategoryBudgets: CategoryBudgets;
  personalColor: string | null; // 예: '가을 웜'
};

export const BUDGET_CATEGORIES = [
  '상의',
  '하의',
  '아우터',
  '원피스/세트',
  '신발',
  '가방',
  '액세서리',
] as const;
export type BudgetCategory = (typeof BUDGET_CATEGORIES)[number];
export type CategoryBudgets = Partial<Record<BudgetCategory, number>>;
export const DEFAULT_CATEGORY_BUDGETS: CategoryBudgets = {
  상의: 100_000,
  하의: 150_000,
  아우터: 300_000,
  '원피스/세트': 200_000,
  신발: 200_000,
  가방: 200_000,
  액세서리: 50_000,
};

type BudgetResponse = {
  category_budgets: CategoryBudgets;
  effective_category_budgets: CategoryBudgets;
};

let state: Prefs = {
  nickname: null,
  categoryBudgets: {},
  effectiveCategoryBudgets: DEFAULT_CATEGORY_BUDGETS,
  personalColor: null,
};
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const prefsStore = {
  get: () => state,
  setNickname(name: string | null) {
    state = { ...state, nickname: name && name.trim() ? name.trim() : null };
    emit();
  },
  /** 서버에 저장해 둔 예산을 읽어 온다. 비로그인·데모는 서버를 부르지 않는다. */
  async loadBudget(): Promise<void> {
    if (!isAuthed()) return;
    try {
      const response = await api.get<BudgetResponse>(BudgetEndpoint);
      state = {
        ...state,
        categoryBudgets: response.category_budgets,
        effectiveCategoryBudgets: response.effective_category_budgets,
      };
      emit();
    } catch {
      /* 예산은 없어도 화면이 도는 값이다 — 못 받아 왔다고 에러를 띄우지 않는다.
         '예산을 설정하면…' 안내가 그대로 보이고, 저장은 여전히 된다. */
    }
  },

  /**
   * 카테고리별 예산 저장(전체 교체). 빈 객체는 모든 예산을 기본값으로 되돌린다.
   */
  async saveBudget(values: CategoryBudgets): Promise<void> {
    const normalized = Object.fromEntries(
      Object.entries(values).map(([category, amount]) => [category, normalizeBudget(amount)]),
    ) as CategoryBudgets;
    const response = isAuthed()
      ? await api.put<BudgetResponse>(BudgetEndpoint, { category_budgets: normalized })
      : {
          category_budgets: normalized,
          effective_category_budgets: { ...DEFAULT_CATEGORY_BUDGETS, ...normalized },
        };
    state = {
      ...state,
      categoryBudgets: response.category_budgets,
      effectiveCategoryBudgets: response.effective_category_budgets,
    };
    emit();
  },
  setPersonalColor(c: string | null) {
    state = { ...state, personalColor: c };
    emit();
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

/* 앱 시작 시점(_layout)에는 아직 로그인 전일 수 있다. 로그인 직후에도 예산이 채워지도록
   세션 변화를 지켜본다 — 로그아웃하면 다시 받을 수 있게 표시를 되돌린다. */
let budgetLoaded = false;
authStore.subscribe(() => {
  if (isAuthed()) {
    if (!budgetLoaded) {
      budgetLoaded = true;
      void prefsStore.loadBudget();
    }
    return;
  }
  budgetLoaded = false;
});

function isAuthed(): boolean {
  const { status, isDemo } = authStore.getState();
  // 데모 세션은 서버 토큰이 없다 — 부르면 401 이라 화면 안에서만 유지한다.
  return status === 'authed' && !isDemo;
}

/** 서버가 받는 범위로 맞춘다 — 1만원 단위, 1만원 이상. */
export const MIN_BUDGET = 10_000;
function normalizeBudget(n: number): number {
  return Math.max(MIN_BUDGET, Math.round(n / MIN_BUDGET) * MIN_BUDGET);
}

/** 슬롯/대분류에 해당하는 상품 1개 예산. 레거시 '잡화' 슬롯은 가방으로 본다. */
export function categoryBudget(values: CategoryBudgets, rawCategory: string): number | null {
  const category = rawCategory === '잡화'
    ? '가방'
    : BUDGET_CATEGORIES.find((candidate) => rawCategory.startsWith(candidate));
  return category ? values[category] ?? null : null;
}

/** 개인화 설정 구독 (예산·퍼스널컬러) */
export function usePrefs() {
  return useSyncExternalStore(prefsStore.subscribe, prefsStore.get, prefsStore.get);
}

/** 예산을 "10만원" 형태로 표시. 미설정이면 null */
export function formatBudget(n: number | null): string | null {
  if (n == null) return null;
  const man = n / 10000;
  return `${Number.isInteger(man) ? man : man.toFixed(0)}만원`;
}

/** "89,000" 같은 가격 문자열을 숫자로 (콤마 제거) */
export function parsePrice(price: string): number {
  return Number(price.replace(/[^0-9]/g, '')) || 0;
}
