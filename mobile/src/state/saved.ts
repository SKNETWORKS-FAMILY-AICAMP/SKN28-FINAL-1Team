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
  isSaved: (look: { image?: string; asset?: number }) =>
    savedLooks.some((l) => keyOf(l) === keyOf(look)),
  /** 저장. 이미 있으면 중복 추가하지 않고 기존 것을 돌려준다. */
  addLook(input: { image?: string; asset?: number; comment?: string; tags?: string[] }) {
    const existing = savedLooks.find((l) => keyOf(l) === keyOf(input));
    if (existing) return existing;
    const look: SavedLook = {
      id: String(Date.now()),
      image: input.image,
      asset: input.asset,
      comment: input.comment,
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
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useSavedLooks() {
  return useSyncExternalStore(savedLookStore.subscribe, savedLookStore.getLooks, savedLookStore.getLooks);
}
