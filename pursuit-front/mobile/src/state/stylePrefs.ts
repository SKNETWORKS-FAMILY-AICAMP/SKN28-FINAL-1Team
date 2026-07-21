import { useSyncExternalStore } from 'react';

import { PURSUIT_CATEGORIES, type PursuitCategoryKey } from '@/constants/pursuitOptions';

/**
 * 추구미 선호도(preferred/avoided) 경량 스토어.
 * prefs.ts 와 동일한 "모듈 스토어 + useSyncExternalStore" 패턴.
 * (프로토타입: 메모리 보관. 앱 재시작 시 초기화 — 추후 백엔드 "내 선호도 조회/저장" API 연동 시
 *  이 스토어의 get/save 를 GET/PUT 호출로 교체한다.)
 *
 * 카테고리별 string[] 배열 구조는 final.md 결정 사항을 그대로 따른다:
 *   - preferred / avoided 를 분리하고 카테고리별 배열로 저장한다.
 *   - 모든 항목은 선택하지 않아도 저장할 수 있다 (빈 배열/빈 상태 저장 허용).
 *   - 같은 카테고리 안에서 동일 옵션이 preferred/avoided 에 동시에 들어가지 않는다.
 */

export type PursuitSelections = Record<PursuitCategoryKey, string[]>;

export interface PursuitPreferences {
  preferred: PursuitSelections;
  avoided: PursuitSelections;
}

export type PursuitMode = 'preferred' | 'avoided';

function emptySelections(): PursuitSelections {
  return PURSUIT_CATEGORIES.reduce((acc, { key }) => {
    acc[key] = [];
    return acc;
  }, {} as PursuitSelections);
}

function emptyPreferences(): PursuitPreferences {
  return { preferred: emptySelections(), avoided: emptySelections() };
}

let state: PursuitPreferences = emptyPreferences();
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const stylePrefsStore = {
  get: () => state,
  /** 내 선호도 저장/수정 (mock). 실제로는 PUT/PATCH API 응답을 그대로 반영. */
  save(next: PursuitPreferences) {
    state = next;
    emit();
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

/** 저장된 추구미 선호도 구독 (내 선호도 조회 mock) */
export function useStylePrefs() {
  return useSyncExternalStore(stylePrefsStore.subscribe, stylePrefsStore.get, stylePrefsStore.get);
}

/** 얕은 복제 — setState 시 이전 참조를 변형하지 않기 위해 사용 */
export function clonePreferences(prefs: PursuitPreferences): PursuitPreferences {
  return {
    preferred: { ...prefs.preferred },
    avoided: { ...prefs.avoided },
  };
}

/**
 * 카테고리 안에서 옵션 하나를 토글한다.
 * - 현재 모드가 'preferred' 면 preferred 배열을 토글하고, avoided 에서는 제거한다.
 * - 현재 모드가 'avoided' 면 avoided 배열을 토글하고, preferred 에서는 제거한다.
 * → 같은 카테고리 안에서 동일 옵션이 두 배열에 동시에 들어가는 상황을 원천 차단한다.
 */
export function toggleOption(
  prefs: PursuitPreferences,
  mode: PursuitMode,
  category: PursuitCategoryKey,
  code: string,
): PursuitPreferences {
  const next = clonePreferences(prefs);
  const preferredList = next.preferred[category];
  const avoidedList = next.avoided[category];

  if (mode === 'preferred') {
    next.preferred[category] = preferredList.includes(code)
      ? preferredList.filter((c) => c !== code)
      : [...preferredList, code];
    next.avoided[category] = avoidedList.filter((c) => c !== code);
  } else {
    next.avoided[category] = avoidedList.includes(code)
      ? avoidedList.filter((c) => c !== code)
      : [...avoidedList, code];
    next.preferred[category] = preferredList.filter((c) => c !== code);
  }

  return next;
}

/** 카테고리별 선택 개수 (선택/비선택 힌트 표시용) */
export function categoryCount(prefs: PursuitPreferences, category: PursuitCategoryKey): number {
  return prefs.preferred[category].length + prefs.avoided[category].length;
}

/** 전체 선택 개수 — 하나라도 선택했는지 확인용 */
export function totalCount(prefs: PursuitPreferences): number {
  return PURSUIT_CATEGORIES.reduce((sum, { key }) => sum + categoryCount(prefs, key), 0);
}
