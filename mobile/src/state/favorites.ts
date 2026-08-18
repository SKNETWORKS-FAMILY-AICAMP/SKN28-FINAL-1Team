import { useSyncExternalStore } from 'react';

import { getClosetFavorites, saveClosetFavorites } from '@/lib/secureStore';

/**
 * 옷장 즐겨찾기(별).
 *
 * **찜(state/likes.ts)과 다른 것이다.** 찜은 아직 안 산 상품이고, 여기는 이미 가진 옷이다.
 * 그래서 아이콘도 가른다 — 상품은 하트, 옷장 옷은 별. 한 아이콘이 화면마다 다른 뜻이면
 * 누르기 전에 무슨 일이 생길지 알 수 없다.
 *
 * ⚠️ **서버에 자리가 없다.** `WardrobeItem` 에 favorite 류 필드가 없어(2026-08-18 확인)
 *    기기에만 남는다 → **추천에는 반영되지 않는다.** 추천을 고르는 것은 백엔드다.
 *    여기서 하는 일은 하나뿐이다: 내 옷장에서 자주 입는 옷을 위로 모아 보는 것.
 *    서버 필드가 생기면 toggle 을 API 호출로 바꾸고 이 파일의 저장부를 지운다.
 */

let ids = new Set<string>();
let snapshot: string[] = [];

const listeners = new Set<() => void>();

/** useSyncExternalStore 는 같은 참조를 요구한다 — Set 을 매번 배열로 만들면 무한 루프가 된다. */
function refresh() {
  snapshot = [...ids];
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

async function persist(): Promise<void> {
  try {
    await saveClosetFavorites(JSON.stringify([...ids]));
  } catch {
    // 저장 실패는 조용히 넘긴다(다음 변경 때 다시 시도된다)
  }
}

export const favoritesStore = {
  /** 앱이 뜰 때 한 번. 이미 담긴 게 있으면 덮어쓰지 않는다. */
  async bootstrap(): Promise<void> {
    if (ids.size > 0) return;
    try {
      const raw = await getClosetFavorites();
      if (!raw) return;
      const saved = JSON.parse(raw) as string[];
      if (!Array.isArray(saved) || ids.size > 0) return;
      ids = new Set(saved);
      refresh();
    } catch {
      // 저장값이 깨졌으면 빈 목록으로 시작한다
    }
  },

  getIds: () => snapshot,
  isFavorite: (id: string) => ids.has(id),

  /** 켜면 true, 끄면 false 를 돌려준다 — 호출부가 토스트 문구를 고를 수 있게. */
  toggle(id: string): boolean {
    const on = !ids.has(id);
    if (on) ids.add(id);
    else ids.delete(id);
    refresh();
    void persist();
    return on;
  },

  subscribe,
};

/** 즐겨찾기한 옷 id 목록. 화면은 보통 `has` 로만 쓰지만 개수 표시에도 쓴다. */
export function useFavorites(): string[] {
  return useSyncExternalStore(subscribe, favoritesStore.getIds, favoritesStore.getIds);
}
