import { useSyncExternalStore } from 'react';

import { getClosetFavorites, saveClosetFavorites } from '@/lib/secureStore';
import { patchWardrobeItem } from '@/lib/wardrobeApi';
import { authStore } from '@/state/auth';

/**
 * 옷장 즐겨찾기(별).
 *
 * **찜(state/likes.ts)과 다른 것이다.** 찜은 아직 안 산 상품이고, 여기는 이미 가진 옷이다.
 * 그래서 아이콘도 가른다 — 상품은 하트, 옷장 옷은 별. 한 아이콘이 화면마다 다른 뜻이면
 * 누르기 전에 무슨 일이 생길지 알 수 없다.
 *
 * **서버가 들고 있다** — `WardrobeItem.is_favorite`, 아이템 PATCH 로 켜고 끈다.
 * 이 스토어는 그 값을 화면 쪽에 얹어 두는 자리다: 목록을 다시 받아오기 전에도 별이 즉시 켜지고,
 * 비로그인·데모 세션에서는 기기 저장(secureStore)만으로 동작한다.
 *
 * ⚠️ 즐겨찾기는 **추천에 반영되지 않는다.** 추천을 고르는 것은 백엔드이고, 지금은 이 값을
 *    읽지 않는다. 하는 일은 하나다: 내 옷장에서 자주 입는 옷만 모아 보는 것.
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

  /**
   * 옷장 목록을 받아올 때마다 서버 값으로 맞춘다.
   * 서버가 원본이라 목록에 없는 옷의 별은 지우지 않는다(공유 옷장 등 다른 목록에서 온 id).
   */
  hydrate(items: { id: string; is_favorite?: boolean }[]): void {
    let changed = false;
    for (const item of items) {
      const on = !!item.is_favorite;
      if (on && !ids.has(item.id)) {
        ids.add(item.id);
        changed = true;
      } else if (!on && ids.has(item.id)) {
        ids.delete(item.id);
        changed = true;
      }
    }
    if (changed) {
      refresh();
      void persist();
    }
  },

  /**
   * 켜면 true, 끄면 false 를 돌려준다 — 호출부가 토스트 문구를 고를 수 있게.
   * 별은 누른 즉시 켜지고 서버에는 뒤따라 알린다. 서버가 거절하면 되돌린다 —
   * 안 켜진 것이 켜진 척 남아 있으면 다음 목록 갱신에서 이유 없이 꺼진다.
   */
  toggle(id: string): boolean {
    const on = !ids.has(id);
    if (on) ids.add(id);
    else ids.delete(id);
    refresh();
    void persist();

    const { status, isDemo } = authStore.getState();
    if (status === 'authed' && !isDemo) {
      void patchWardrobeItem(id, { is_favorite: on }).catch(() => {
        if (on) ids.delete(id);
        else ids.add(id);
        refresh();
        void persist();
      });
    }
    return on;
  },

  subscribe,
};

/** 즐겨찾기한 옷 id 목록. 화면은 보통 `has` 로만 쓰지만 개수 표시에도 쓴다. */
export function useFavorites(): string[] {
  return useSyncExternalStore(subscribe, favoritesStore.getIds, favoritesStore.getIds);
}
