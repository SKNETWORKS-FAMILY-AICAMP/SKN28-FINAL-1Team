import { useSyncExternalStore } from 'react';

/**
 * 저장한 룩 — '오늘의 추천'이나 룩 상세에서 사용자가 '저장'한 룩 모음.
 * 룩북 '둘러보기'(남들이 올린 피드, state/lookbook.ts)와는 별개의 컬렉션이다.
 * 백엔드가 붙으면 이 스토어를 저장 API 로 교체한다(필드명 유지).
 */
export type SavedLook = {
  id: string;
  /** 원격 사진 URL (SmartImage uri) */
  image?: string;
  /** 번들 목업 사진 (require 결과, SmartImage asset) — image 가 없을 때 */
  asset?: number;
  comment?: string;
  /** 사용자가 직접 남긴 메모 — "회사 발표 있는 날 입기 좋았음" 같은 것 */
  memo?: string;
  /**
   * 추천받을 때 들었던 이유. 추천 룩 API(C4)가 붙으면 저장 시점에 같이 담긴다.
   * 없으면 상세에서 그 칸을 그리지 않는다 — 모든 룩에 같은 이유를 보여주면 그건 거짓말이다.
   */
  reason?: string;
  tags: string[];
  savedAt: number;
};

/** 같은 룩을 두 번 저장하지 않도록 이미지로 식별 */
function keyOf(look: { image?: string; asset?: number }): string {
  return look.image ?? `asset:${look.asset ?? ''}`;
}

// 데모용 시드 — 이전에 저장해 둔 룩(피드와 같은 사진을 써서 로드 보장).
const SEED_SAVED: SavedLook[] = [
  {
    id: 's1',
    image: 'https://i.pinimg.com/736x/c1/ae/c8/c1aec88282cee841eca0f6e0da5d1174.jpg',
    comment: '차분한 출근 룩',
    memo: '회사 발표 있는 날 입기 좋았음. 로퍼 대신 부츠도 잘 어울릴 듯.',
    reason: '8도의 쌀쌀한 날씨에 맞춰 니트와 코트로 보온성을 확보하고, 미니멀 무드에 맞게 톤을 절제한 오피스 코디예요.',
    tags: ['출근', '미니멀'],
    savedAt: 2,
  },
  {
    id: 's2',
    image: 'https://i.pinimg.com/736x/32/7a/f3/327af326d108881015d4eea726f1cb51.jpg',
    comment: '포근한 데일리',
    tags: ['출근'],
    savedAt: 1,
  },
];

let savedLooks: SavedLook[] = [...SEED_SAVED];
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

export const savedLookStore = {
  getLooks: () => savedLooks,
  getLook: (id: string) => savedLooks.find((l) => l.id === id),
  isSaved: (look: { image?: string; asset?: number }) =>
    savedLooks.some((l) => keyOf(l) === keyOf(look)),
  /** 저장. 이미 있으면 중복 추가하지 않고 기존 것을 돌려준다. */
  addLook(input: {
    image?: string;
    asset?: number;
    comment?: string;
    tags?: string[];
    reason?: string;
  }) {
    const existing = savedLooks.find((l) => keyOf(l) === keyOf(input));
    if (existing) return existing;
    const look: SavedLook = {
      id: String(Date.now()),
      image: input.image,
      asset: input.asset,
      comment: input.comment,
      reason: input.reason,
      tags: input.tags ?? [],
      savedAt: Date.now(),
    };
    savedLooks = [look, ...savedLooks];
    notify();
    return look;
  },
  removeLook(id: string) {
    savedLooks = savedLooks.filter((l) => l.id !== id);
    notify();
  },
  /** 메모·태그 수정. 사진과 저장 시각은 건드리지 않는다. */
  updateLook(id: string, patch: { memo?: string; tags?: string[] }) {
    savedLooks = savedLooks.map((l) =>
      l.id === id
        ? { ...l, memo: patch.memo?.trim() || undefined, tags: patch.tags ?? l.tags }
        : l,
    );
    notify();
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useSavedLooks() {
  return useSyncExternalStore(savedLookStore.subscribe, savedLookStore.getLooks, savedLookStore.getLooks);
}
