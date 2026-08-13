import { useSyncExternalStore } from 'react';

import type { MallKey } from '@/lib/mall';

/**
 * 위시(룩) · 찜(상품) 스토어.
 *
 * ⚠️ **화면 이름과 코드 이름이 다르다.** 화면의 '위시'가 여기서는 `liked*`(룩),
 * 화면의 '찜'이 `wish*`(상품)다. 서버 API 가 생길 때 필드명을 맞출 예정이라 코드 쪽은 두었다.
 *
 * 둘을 한 파일에 두는 이유: 추천이 이 둘을 **같이** 읽는다.
 * 위시한 룩의 태그로 룩을 고르고, 찜한 상품의 브랜드로 상품 순서를 정한다(아래 affinity).
 * 나뉘어 있으면 추천 코드가 양쪽을 매번 다시 엮어야 한다.
 *
 * ⚠️ 백엔드에 위시/찜 API 가 아직 없다(`/api/v1/likes`·`/wishlist` 404 확인, 2026-07-31).
 *    prefs.ts·saved.ts 와 같이 메모리 보관이며 앱을 다시 켜면 비워진다.
 *    API 가 생기면 이 스토어의 함수 본문만 교체한다(필드명 유지).
 *
 * 룩 저장(saved.ts)과의 관계 — 화면에서는 **둘 다 '위시' 한 목록으로 합쳐 보인다.**
 *   위시(여기)      = 둘러보기 피드에서 하트로 담은 룩
 *   저장(saved.ts)  = 추천에서 담아둔 룩(✨). 내 룩북이 아니라 위시 쪽에 선다.
 * '내 룩북'에는 내가 올린 룩만 남는다.
 */

/** 둘러보기 피드 룩 위시(하트) */
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
  /** 어느 구성에서 담았는지 (상의/하의/…) — 찜 목록에서 맥락 표시용 */
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

  /* ── 찜 (상품) ── */
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

/* ── 취향 점수 ──
   좋아요·찜을 빈도로 환산해 순위를 매기는 자리. 룩 쪽(태그 빈도)은 프론트에서 뽑던 걸 걷어냈다 —
   좋아요는 화면에 목록을 만들지 않고, 무엇을 추천할지는 백엔드가 정한다.
   상품 쪽만 남는다: 룩 상세의 '관련 상품' 순서를 찜한 브랜드로 앞당기는 데 쓴다. */

export type Scores = Record<string, number>;

/** 찜한 상품들의 브랜드 빈도. 예) { COS: 2, Uniqlo: 1 } */
export function brandScores(items: WishItem[]): Scores {
  const out: Scores = {};
  for (const item of items) out[item.brand] = (out[item.brand] ?? 0) + 1;
  return out;
}
