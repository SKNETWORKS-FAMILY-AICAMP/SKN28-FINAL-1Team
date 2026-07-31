import { useSyncExternalStore } from 'react';

import type { MallKey } from '@/lib/mall';

/**
 * 좋아요(룩) · 위시리스트(상품) 스토어.
 *
 * 둘을 한 파일에 두는 이유: 추천이 이 둘을 **같이** 읽는다.
 * 좋아요한 룩의 태그로 룩을 고르고, 찜한 상품의 브랜드로 상품 순서를 정한다(아래 affinity).
 * 나뉘어 있으면 추천 코드가 양쪽을 매번 다시 엮어야 한다.
 *
 * ⚠️ 백엔드에 좋아요/찜 API 가 아직 없다(`/api/v1/likes`·`/wishlist` 404 확인, 2026-07-31).
 *    prefs.ts·saved.ts 와 같이 메모리 보관이며 앱을 다시 켜면 비워진다.
 *    API 가 생기면 이 스토어의 함수 본문만 교체한다(필드명 유지).
 *
 * 저장(saved.ts)과는 다른 개념이다 —
 *   좋아요 = 룩북 피드에서 남의 룩에 누르는 호감 표시(추천 재료)
 *   저장   = 추천받은 룩을 내 '저장됨'에 담아두는 것
 * 아이콘도 갈라 뒀다(좋아요=하트 / 저장=북마크).
 */

/** 룩북 피드 룩 좋아요 */
export type LikedLook = {
  /** 피드 룩의 id (state/lookbook.ts LookPost.id) */
  id: string;
  image?: string;
  tags: string[];
  likedAt: number;
};

/** 찜한 상품 */
export type WishItem = {
  /** `브랜드::상품명` — 같은 상품을 두 번 담지 않기 위한 키 */
  id: string;
  name: string;
  brand: string;
  /** 화면 표기와 같은 형식의 가격 문자열 (예: '19,900') */
  price: string;
  /** 썸네일 placeholder 농도 (상품 사진이 없을 때) */
  tone: number;
  /** 외부 쇼핑몰 상품 주소. 없으면 브랜드·상품명으로 검색 주소를 만든다(lib/mall.ts) */
  link?: string;
  /** 어느 몰로 내보낼지. 생략하면 기본 몰. */
  mall?: MallKey;
  /** 어느 구성에서 담았는지 (상의/하의/…) — 위시리스트에서 맥락 표시용 */
  slot?: string;
  addedAt: number;
};

export function wishKey(p: { brand: string; name: string }): string {
  return `${p.brand}::${p.name}`;
}

let likedLooks: LikedLook[] = [];
let wishlist: WishItem[] = [];

const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const likesStore = {
  /* ── 좋아요 (룩) ── */
  getLikedLooks: () => likedLooks,
  isLiked: (id: string) => likedLooks.some((l) => l.id === id),
  /** 켜면 true, 끄면 false 를 돌려준다 — 호출부가 토스트 문구를 고를 수 있게. */
  toggleLook(look: { id: string; image?: string; tags?: string[] }): boolean {
    if (likedLooks.some((l) => l.id === look.id)) {
      likedLooks = likedLooks.filter((l) => l.id !== look.id);
      notify();
      return false;
    }
    likedLooks = [
      { id: look.id, image: look.image, tags: look.tags ?? [], likedAt: Date.now() },
      ...likedLooks,
    ];
    notify();
    return true;
  },

  /* ── 위시리스트 (상품) ── */
  getWishlist: () => wishlist,
  isWished: (p: { brand: string; name: string }) => wishlist.some((w) => w.id === wishKey(p)),
  toggleWish(p: Omit<WishItem, 'id' | 'addedAt'>): boolean {
    const id = wishKey(p);
    if (wishlist.some((w) => w.id === id)) {
      wishlist = wishlist.filter((w) => w.id !== id);
      notify();
      return false;
    }
    wishlist = [{ ...p, id, addedAt: Date.now() }, ...wishlist];
    notify();
    return true;
  },
  removeWish(id: string) {
    wishlist = wishlist.filter((w) => w.id !== id);
    notify();
  },
  clearWishlist() {
    wishlist = [];
    notify();
  },

  subscribe,
};

export function useLikedLooks() {
  return useSyncExternalStore(subscribe, likesStore.getLikedLooks, likesStore.getLikedLooks);
}

export function useWishlist() {
  return useSyncExternalStore(subscribe, likesStore.getWishlist, likesStore.getWishlist);
}

/* ── 취향 점수 (추천 재료) ─────────────────────────────────────
   "좋아요 누른 것 기반 추천"의 알맹이. 좋아요·찜을 **빈도**로 환산해
   룩은 태그로, 상품은 브랜드로 순위를 매긴다.
   최근에 누른 것에 가중치를 더 주지는 않는다 — 프로토타입 규모(좋아요 수십 개)에서는
   시간 가중치를 넣어도 순서가 거의 그대로라, 설명하기 쉬운 빈도만 쓴다. */

export type Scores = Record<string, number>;

/** 좋아요한 룩들의 태그 빈도. 예) { 출근: 2, 미니멀: 1 } */
export function tagScores(looks: LikedLook[]): Scores {
  const out: Scores = {};
  for (const look of looks) {
    for (const tag of look.tags) out[tag] = (out[tag] ?? 0) + 1;
  }
  return out;
}

/** 찜한 상품들의 브랜드 빈도. 예) { COS: 2, Uniqlo: 1 } */
export function brandScores(items: WishItem[]): Scores {
  const out: Scores = {};
  for (const item of items) out[item.brand] = (out[item.brand] ?? 0) + 1;
  return out;
}

/** 룩 하나가 취향과 얼마나 겹치는지 — 태그 점수의 합 */
export function matchScore(tags: readonly string[], scores: Scores): number {
  return tags.reduce((sum, tag) => sum + (scores[tag] ?? 0), 0);
}

/** 점수 높은 순 상위 n개 키 (추천 이유 문구에 쓴다) */
export function topKeys(scores: Scores, n: number): string[] {
  return Object.entries(scores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([key]) => key);
}
