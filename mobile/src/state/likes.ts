import { useSyncExternalStore } from 'react';

import type { MallKey } from '@/lib/mall';
import { imageUrlOf } from '@/lib/recommendApi';
import { getWishlist as readStored, saveWishlist as writeStored } from '@/lib/secureStore';
import { addWish, listWishlist, removeWish, type ApiWishItem } from '@/lib/wishlistApi';
import { authStore } from '@/state/auth';

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
 * **찜(상품)은 서버에 있다** (`/api/v1/wishlist/`, 2026-08-18). 로그인 상태면 서버가 원본이고,
 *   기기 저장(secureStore)은 두 가지 자리에서만 쓴다:
 *     ① 비로그인·데모 세션 ② 서버 왕복이 실패했을 때 (담은 것이 화면에서 사라지지 않게)
 *   그래서 목록에는 서버 행(`wishId` 있음)과 기기 행(없음)이 섞일 수 있다.
 *
 * ⚠️ 룩 위시(`liked*`)는 아직 서버에 자리가 없어 기기 보관 그대로다.
 *
 * 룩 저장(saved.ts)과의 관계 — 화면에서는 **둘 다 '위시' 한 목록으로 합쳐 보인다.**
 *   위시(여기)      = 둘러보기 피드에서 하트로 담은 룩
 *   저장(saved.ts)  = 추천에서 담아둔 룩(✨)
 * 위시는 내 룩북 안의 한 갈래다 — 내 룩북 = [올린 룩][위시], 둘러보기는 남의 룩만 있는 피드.
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
  /** 목록 안에서의 키. 서버 행이면 `wishId`, 기기 행이면 `브랜드::상품명`. */
  id: string;
  /** 서버에 있는 찜이면 그 행 id. 없으면 이 기기에만 있는 항목이다. */
  wishId?: string;
  /** 카탈로그 상품 식별자 — 하트가 켜졌는지 판단하는 기준(이름은 추천마다 달라진다). */
  sourceId?: string;
  name: string;
  /** 브랜드. 추천 API 는 브랜드를 안 내려줘 **빈 문자열일 수 있다** — 화면은 있을 때만 그린다. */
  brand: string;
  /** 화면 표기와 같은 형식의 가격 문자열 (예: '19,900') */
  price: string;
  /** 썸네일 placeholder 농도 (상품 사진이 없을 때) */
  tone: number;
  /** 상품 사진. 목업 룩의 '비슷한 상품'에는 없고, 추천 API 상품에는 있다. */
  image?: string;
  /** 외부 쇼핑몰 상품 주소. 없으면 브랜드·상품명으로 검색 주소를 만든다(lib/mall.ts) */
  link?: string;
  /** 어느 몰로 내보낼지. 생략하면 기본 몰. */
  mall?: MallKey;
  /** 어느 구성에서 담았는지 (상의/하의/…) — 찜 목록에서 맥락 표시용 */
  slot?: string;
  addedAt: number;
};

/** 서버 행 → 화면이 쓰는 모양. 가격은 문자열로 바꾼다(화면 표기와 같은 형식). */
export function fromApiWish(w: ApiWishItem): WishItem {
  return {
    id: w.wish_id,
    wishId: w.wish_id,
    sourceId: w.source_id || undefined,
    name: w.display_name,
    brand: w.brand,
    price: w.price_snapshot != null ? w.price_snapshot.toLocaleString('ko-KR') : '',
    tone: 0.06,
    image: imageUrlOf(w.image_ref) ?? undefined,
    link: w.purchase_url || undefined,
    slot: w.slot || undefined,
    addedAt: Date.parse(w.added_at) || Date.now(),
  };
}

export function wishKey(p: { brand: string; name: string }): string {
  return `${p.brand}::${p.name}`;
}

let likedLooks: LikedLook[] = [];
let wishlist: WishItem[] = [];
/** 세션 변화를 한 번만 구독하기 위한 자리 (bootstrap 이 여러 번 불려도 하나만 남는다) */
let authWatch: (() => void) | null = null;
let wasMember = false;

const listeners = new Set<() => void>();
/* 바뀔 때마다 기기에 적는다. 저장은 기다리지 않는다 — 화면은 이미 새 값을 그렸고,
   저장이 늦거나 실패해도 이번 세션의 동작은 달라지지 않는다. */
const notify = () => {
  listeners.forEach((l) => l());
  void persist();
};

async function persist(): Promise<void> {
  try {
    await writeStored(JSON.stringify({ likedLooks, wishlist }));
  } catch {
    // 저장 실패는 조용히 넘긴다(다음 변경 때 다시 시도된다)
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const likesStore = {
  /**
   * 앱이 뜰 때 한 번 — 기기에 적어 둔 찜·위시를 되살린다.
   * 사용자가 이미 무언가 담은 뒤라면 덮어쓰지 않는다(복원이 방금 한 동작을 지우면 안 된다).
   */
  async bootstrap(): Promise<void> {
    if (likedLooks.length > 0 || wishlist.length > 0) return;
    try {
      const raw = await readStored();
      if (raw && likedLooks.length === 0 && wishlist.length === 0) {
        const saved = JSON.parse(raw) as { likedLooks?: LikedLook[]; wishlist?: WishItem[] };
        likedLooks = Array.isArray(saved.likedLooks) ? saved.likedLooks : [];
        wishlist = Array.isArray(saved.wishlist) ? saved.wishlist : [];
        listeners.forEach((l) => l());
      }
    } catch {
      // 저장값이 깨졌으면 빈 목록으로 시작한다
    }
    await likesStore.sync();
    /* 세션이 늦게 정해질 수 있다(토큰 복원·소셜 로그인) — 회원이 되는 순간 한 번 더 받아온다.
       구독을 남겨 두면 로그아웃 후 다시 로그인해도 남의 찜이 남지 않는다. */
    if (!authWatch) {
      authWatch = authStore.subscribe(() => {
        const { status, isDemo } = authStore.getState();
        const member = status === 'authed' && !isDemo;
        if (member === wasMember) return;
        wasMember = member;
        if (member) void likesStore.sync();
      });
    }
  },

  /**
   * 서버의 찜을 받아 온다. 로그인 회원만 서버에 자리가 있다.
   *
   * 서버 목록이 원본이지만, 이 기기에서만 담은 것(목업 룩의 '비슷한 상품'이나
   * 왕복이 실패해 서버에 못 올라간 것)은 지우지 않고 뒤에 남긴다 — 사용자가 담아 둔 것이
   * 로그인 한 번에 사라지면 담기를 신뢰할 수 없다.
   */
  async sync(): Promise<void> {
    const { status, isDemo } = authStore.getState();
    if (status !== 'authed' || isDemo) return;
    try {
      const rows = await listWishlist();
      const server = rows.map(fromApiWish);
      const serverSources = new Set(server.map((w) => w.sourceId).filter(Boolean));
      const localOnly = wishlist.filter(
        (w) => !w.wishId && !(w.sourceId && serverSources.has(w.sourceId)),
      );
      wishlist = [...server, ...localOnly];
      notify();
    } catch {
      // 서버가 없거나 못 받았으면 기기에 있는 것으로 계속 쓴다
    }
  },

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
  /** 추천 상품용 — 카탈로그 식별자로 본다. 같은 상품이면 어느 카드에서 보든 하트가 켜진다. */
  isWishedSource: (sourceId: string | null | undefined) =>
    !!sourceId && wishlist.some((w) => w.sourceId === sourceId),

  /**
   * 추천 카드의 상품을 담거나 뺀다. 켜면 true.
   *
   * 화면을 먼저 바꾸고 서버에 알린다 — 하트는 누른 즉시 켜져야 한다.
   * 서버가 없거나 실패하면 담은 것은 기기에 남긴다(다음 sync 에서 서버 것으로 대체된다).
   */
  async toggleRecWish(
    ref: { resultId: string; cardId: string; itemId: string; sourceId?: string | null },
    snapshot: Omit<WishItem, 'id' | 'addedAt'>,
  ): Promise<boolean> {
    const found = wishlist.find(
      (w) =>
        (ref.sourceId && w.sourceId === ref.sourceId) ||
        w.id === wishKey({ brand: snapshot.brand, name: snapshot.name }),
    );
    if (found) {
      likesStore.removeWish(found.id);
      return false;
    }

    const localId = wishKey({ brand: snapshot.brand, name: snapshot.name });
    wishlist = [
      { ...snapshot, id: localId, sourceId: ref.sourceId ?? undefined, addedAt: Date.now() },
      ...wishlist,
    ];
    notify();

    const { status, isDemo } = authStore.getState();
    if (status !== 'authed' || isDemo) return true;
    try {
      const saved = fromApiWish(await addWish(ref.resultId, ref.cardId, ref.itemId));
      wishlist = [saved, ...wishlist.filter((w) => w.id !== localId)];
      notify();
    } catch {
      // 서버에 못 올렸어도 담긴 상태는 유지한다 — 다음 sync 가 맞춰 준다
    }
    return true;
  },
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
    const target = wishlist.find((w) => w.id === id);
    wishlist = wishlist.filter((w) => w.id !== id);
    notify();
    // 서버 행이면 지우고 온다. 실패해도 화면은 되돌리지 않는다 — 다음 sync 에서 되살아난다.
    if (target?.wishId) void removeWish(target.wishId).catch(() => {});
  },
  clearWishlist() {
    const serverRows = wishlist.filter((w) => w.wishId);
    wishlist = [];
    notify();
    for (const row of serverRows) void removeWish(row.wishId!).catch(() => {});
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
