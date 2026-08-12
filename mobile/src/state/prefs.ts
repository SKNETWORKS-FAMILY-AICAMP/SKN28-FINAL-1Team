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
  budget: number | null; // 원 단위 (예: 100000)
  personalColor: string | null; // 예: '가을 웜'
};

let state: Prefs = { nickname: null, budget: null, personalColor: null };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const prefsStore = {
  get: () => state,
  setNickname(name: string | null) {
    state = { ...state, nickname: name && name.trim() ? name.trim() : null };
    emit();
  },
  /** 화면 표시만 바꾼다. 서버에 남기려면 saveBudget 을 쓴다. */
  setBudget(n: number | null) {
    state = { ...state, budget: n };
    emit();
  },

  /** 서버에 저장해 둔 예산을 읽어 온다. 비로그인·데모는 서버를 부르지 않는다. */
  async loadBudget(): Promise<void> {
    if (!isAuthed()) return;
    try {
      const { monthly_budget } = await api.get<{ monthly_budget: number | null }>(BudgetEndpoint);
      state = { ...state, budget: monthly_budget };
      emit();
    } catch {
      /* 예산은 없어도 화면이 도는 값이다 — 못 받아 왔다고 에러를 띄우지 않는다.
         '예산을 설정하면…' 안내가 그대로 보이고, 저장은 여전히 된다. */
    }
  },

  /**
   * 예산 저장(전체 교체). 지울 때는 키를 빼지 않고 명시적으로 null 을 보낸다.
   * 서버가 1만원 단위·1만원 이상만 받으므로 보내기 전에 맞춰 준다.
   */
  async saveBudget(n: number | null): Promise<void> {
    const value = n == null ? null : normalizeBudget(n);
    if (isAuthed()) await api.put(BudgetEndpoint, { monthly_budget: value });
    state = { ...state, budget: value };
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
