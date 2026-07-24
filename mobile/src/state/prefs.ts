import { useSyncExternalStore } from 'react';

/**
 * 개인화 설정(예산·퍼스널컬러) 경량 스토어.
 * draft-item.ts / auth.ts 와 동일한 "모듈 스토어 + useSyncExternalStore" 패턴.
 * (프로토타입: 메모리 보관. 앱 재시작 시 초기화 — 추후 secureStore 연동 여지)
 */
export type Prefs = {
  budget: number | null; // 원 단위 (예: 100000)
  personalColor: string | null; // 예: '가을 웜'
};

let state: Prefs = { budget: null, personalColor: null };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const prefsStore = {
  get: () => state,
  setBudget(n: number | null) {
    state = { ...state, budget: n };
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
