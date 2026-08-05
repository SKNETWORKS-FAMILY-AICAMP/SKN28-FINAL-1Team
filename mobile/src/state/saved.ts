import { useSyncExternalStore } from 'react';

import { CLOSET_ITEMS } from '@/constants/wardrobe';
import type { EntryItem } from '@/state/calendar';

/**
 * 내 룩북 — '오늘의 추천'에서 저장한 룩과 내가 옷장 옷으로 직접 기록한 룩이 함께 모인다.
 * 룩북 '둘러보기'(남들이 올린 피드, state/lookbook.ts)와는 별개의 컬렉션이다.
 * 백엔드가 붙으면 이 스토어를 저장 API 로 교체한다(필드명 유지).
 */

/**
 * 룩이 어디서 왔는지. 목록에서 한 그리드에 섞이므로 카드 배지로 이걸 구분한다.
 * - 'ai': 앱이 추천해 준 룩을 저장한 것
 * - 'closet': 내 옷장(·친구 옷장) 옷으로 내가 직접 기록한 것
 */
export type LookOrigin = 'ai' | 'closet';

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
  origin: LookOrigin;
  /** 이 룩을 이룬 옷 — 직접 기록한 룩(origin 'closet')에만 있다 */
  items?: EntryItem[];
  /** 그날의 일정 — '팀 회의', '친구 결혼식' */
  note?: string;
  /** 이어져 있는 착장 기록의 날짜 'YYYY-MM-DD'. 룩북↔캘린더를 잇는 한쪽 끈이다. */
  entryDate?: string;
  tags: string[];
  savedAt: number;
};

/**
 * 같은 룩을 두 번 저장하지 않도록 사진으로 식별.
 * 사진이 없는 룩(옷·일정만 기록한 것)은 서로 다른 룩이라도 키가 같아지므로 중복 판정에서 뺀다.
 */
function keyOf(look: { image?: string; asset?: number }): string | null {
  if (look.image) return look.image;
  if (look.asset != null) return `asset:${look.asset}`;
  return null;
}

// 데모용 시드 — 이전에 저장해 둔 룩(피드와 같은 사진을 써서 로드 보장).
const SEED_SAVED: SavedLook[] = [
  {
    id: 's1',
    image: 'https://i.pinimg.com/736x/c1/ae/c8/c1aec88282cee841eca0f6e0da5d1174.jpg',
    comment: '차분한 출근 룩',
    memo: '회사 발표 있는 날 입기 좋았음. 로퍼 대신 부츠도 잘 어울릴 듯.',
    reason: '8도의 쌀쌀한 날씨에 맞춰 니트와 코트로 보온성을 확보하고, 미니멀 무드에 맞게 톤을 절제한 오피스 코디예요.',
    origin: 'ai',
    tags: ['출근', '미니멀'],
    savedAt: 2,
  },
  {
    id: 's2',
    image: 'https://i.pinimg.com/736x/32/7a/f3/327af326d108881015d4eea726f1cb51.jpg',
    comment: '포근한 데일리',
    origin: 'ai',
    tags: ['출근'],
    savedAt: 1,
  },
  /* 내 옷장 옷으로 직접 기록한 룩 — 캘린더 7/7 기록과 서로를 가리킨다(state/calendar.ts SEED_ENTRIES). */
  {
    id: 's3',
    image: 'https://i.pinimg.com/736x/55/26/0d/55260de328aec1e50740655fd4b5fdc5.jpg',
    comment: '기념일 저녁 약속',
    origin: 'closet',
    note: '기념일 저녁 약속',
    entryDate: '2026-07-07',
    items: CLOSET_ITEMS.filter((i) => ['1', '4', '6'].includes(i.id)).map((i) => ({
      id: i.id,
      source: 'closet' as const,
      name: i.name,
      image: i.image,
    })),
    tags: ['데이트'],
    savedAt: 3,
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
  isSaved: (look: { image?: string; asset?: number }) => {
    const key = keyOf(look);
    return key != null && savedLooks.some((l) => keyOf(l) === key);
  },
  /**
   * 저장. 사진이 같은 룩이 이미 있으면 중복 추가하지 않고 기존 것을 돌려준다.
   * origin 기본값이 'ai' 인 이유: 이 함수를 부르는 기존 자리(홈·룩 상세)가 전부 추천 룩 저장이다.
   */
  addLook(input: {
    image?: string;
    asset?: number;
    comment?: string;
    tags?: string[];
    reason?: string;
    origin?: LookOrigin;
    items?: EntryItem[];
    note?: string;
    entryDate?: string;
  }) {
    const key = keyOf(input);
    /* 추천 룩 저장은 같은 카드를 여러 번 담지 않도록 사진으로 중복을 막는다.
       반면 직접 기록한 룩은 같은 사진을 다른 날짜에 다시 입을 수 있으므로,
       사진이 같더라도 각각의 착장 기록으로 남겨야 한다. */
    const existing =
      input.origin === 'closet' || key == null
        ? undefined
        : savedLooks.find((l) => keyOf(l) === key);
    if (existing) return existing;
    const look: SavedLook = {
      id: String(Date.now()),
      image: input.image,
      asset: input.asset,
      comment: input.comment,
      reason: input.reason,
      origin: input.origin ?? 'ai',
      items: input.items?.length ? input.items : undefined,
      note: input.note?.trim() || undefined,
      entryDate: input.entryDate,
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
