import { useSyncExternalStore } from 'react';

import {
  createLookbookFromPhoto,
  createLookbookFromWardrobe,
  deleteLookbook,
  getLookbook,
  getLookbookProcessingStatus,
  listLookbooks,
  patchLookbook,
  type LookbookPostDto,
  type LookbookStatus,
} from '@/lib/lookbookApi';
import { authStore } from '@/state/auth';
import { CLOSET_ITEMS } from '@/constants/wardrobe';
import type { EntryItem } from '@/state/calendar';

/**
 * 내 룩북 — '오늘의 추천'에서 저장한 룩과 내가 옷장 옷으로 직접 기록한 룩이 함께 모인다.
 * 룩북 '둘러보기'(남들이 올린 피드, state/lookbook.ts)와는 별개의 컬렉션이다.
 *
 * `GET/POST /api/v1/lookbooks/` 로 서버에 남는다. 서버 스키마에 자리가 없는 것들
 * (comment·memo·reason·origin)은 캘린더 스토어와 같은 방식으로 로컬 오버레이에 둔다 —
 * 앱을 껐다 켜면 사라지는 값이라는 뜻이다.
 *
 * 서버에 올릴 수 없는 룩(번들 목업 이미지만 있는 것)은 예전처럼 로컬에만 담는다.
 * 비로그인은 서버를 부르지 않는다 — 시드가 그대로 보인다.
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
  /**
   * 사진으로 올린 룩은 옷 추출이 끝나야 COMPLETED 다. 로컬에만 있는 룩은 없다.
   * 처리 중에는 카드에 '옷 정리 중'을 띄우고 삭제를 막는 데 쓴다.
   */
  status?: LookbookStatus;
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

/** 데모 시드의 id — 서버 룩을 받아 오면 이것들만 걷어낸다. */
const SEED_IDS = new Set(SEED_SAVED.map((l) => l.id));

/** 서버에서 받은 룩. 로그인 상태에서만 채워진다. */
let serverLooks: SavedLook[] = [];
/** 서버에 올릴 수 없어 이 기기에만 남는 룩 — 번들 목업 이미지만 있는 추천 룩과 비로그인 시드. */
let localLooks: SavedLook[] = [...SEED_SAVED];
/** 둘을 합쳐 최신순으로 세운 것. useSyncExternalStore 가 같은 참조를 받아야 해서 캐시한다. */
let savedLooks: SavedLook[] = [...localLooks];

type LoadState = { loading: boolean; error: string | null; loaded: boolean };
let loadState: LoadState = { loading: false, error: null, loaded: false };

/**
 * 서버 스키마에 자리가 없는 것들. 룩 id 로 붙여 둔다.
 *
 * 백엔드 LookbookPost 가 가진 자유 텍스트는 `schedule`(일정) 하나뿐이라
 * 룩 제목(comment)·내 메모(memo)·추천 이유(reason)를 실을 곳이 없다.
 * origin 도 마찬가지다 — source_type(사진/옷장)은 '누가 만든 룩인지'와 다른 축이다.
 */
type Overlay = {
  comment?: string;
  memo?: string;
  reason?: string;
  origin?: LookOrigin;
  /** 캘린더 쪽에서 먼저 만든 기록과 이어 붙인 경우 — 서버는 이 연결을 모른다. */
  entryDate?: string;
};
const overlays: Record<string, Overlay> = {};

const listeners = new Set<() => void>();

function rebuild() {
  savedLooks = [...serverLooks, ...localLooks].sort((a, b) => b.savedAt - a.savedAt);
}

function notify() {
  rebuild();
  listeners.forEach((l) => l());
}

/** 서버 응답 + 로컬 오버레이 → 화면이 쓰는 룩 */
function toLook(dto: LookbookPostDto): SavedLook {
  const overlay = (overlays[dto.id] ??= {});
  const items: EntryItem[] = dto.wardrobe_items.map((link) => ({
    id: link.wardrobe_item_id,
    source: 'closet',
    name: (link.snapshot.item_name as string) || '이름 없는 아이템',
    image: link.image_url || undefined,
  }));

  return {
    id: dto.id,
    image: dto.image_url || undefined,
    comment: overlay.comment ?? dto.schedule ?? undefined,
    memo: overlay.memo,
    reason: overlay.reason,
    /* 오버레이가 비었으면(다른 기기·재시작) 담긴 옷으로 짐작한다 — 옷이 걸려 있으면
       내가 고른 룩, 사진뿐이면 추천 룩 쪽에 가깝다. 정확한 구분은 서버 필드가 필요하다. */
    origin: overlay.origin ?? (items.length > 0 ? 'closet' : 'ai'),
    items: items.length ? items : undefined,
    note: dto.schedule || undefined,
    entryDate: dto.calendar?.date ?? overlay.entryDate,
    tags: dto.hashtags ?? [],
    status: dto.status,
    savedAt: Date.parse(dto.created_at) || 0,
  };
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
  /**
   * 내 룩북을 서버에서 받아 온다. 비로그인·데모 세션은 서버를 부르지 않고 시드를 그대로 둔다.
   *
   * 한 번 받아 오면 데모 시드는 걷어낸다 — 내 룩과 남의 데모 룩이 한 그리드에 섞이면
   * 어느 것이 진짜 내 기록인지 읽히지 않는다.
   */
  async load(): Promise<void> {
    if (!isAuthed()) {
      loadState = { loading: false, error: null, loaded: true };
      notify();
      return;
    }
    loadState = { ...loadState, loading: true, error: null };
    notify();
    try {
      const page = await listLookbooks({ limit: 100 });
      serverLooks = page.results.map(toLook);
      if (!loadState.loaded) localLooks = localLooks.filter((l) => !SEED_IDS.has(l.id));
      loadState = { loading: false, error: null, loaded: true };
      notify();
      /* 앱을 껐다 켜거나 한참 만에 들어오면 아직 처리 중인 룩이 있을 수 있다 —
         그때도 스스로 채워지도록 여기서 다시 지켜보기를 건다. */
      for (const dto of page.results) {
        if (isProcessing(dto.status)) watchProcessing(dto.id);
      }
    } catch (error) {
      loadState = {
        loading: false,
        error: error instanceof Error ? error.message : '룩북을 불러오지 못했어요.',
        loaded: loadState.loaded,
      };
      notify();
    }
  },

  async addLook(input: {
    image?: string;
    asset?: number;
    comment?: string;
    tags?: string[];
    reason?: string;
    origin?: LookOrigin;
    items?: EntryItem[];
    note?: string;
    entryDate?: string;
    /**
     * `entryDate` 날짜의 캘린더 기록을 **서버가 함께 만들지** 여부.
     *
     * 룩북에서 '캘린더에도 기록하기'를 켠 경우에만 true 다. 반대로 캘린더 화면에서
     * '룩북에도 올리기'로 들어온 경우는 캘린더 기록을 캘린더 쪽이 따로 만들므로 false —
     * 여기서도 만들면 같은 날짜에 두 번 등록해 409 가 난다.
     */
    createCalendar?: boolean;
    /** 그 날짜에 이미 캘린더 기록이 있을 때 덮어쓸지 — 사용자에게 물은 뒤에만 true */
    overwriteCalendar?: boolean;
  }): Promise<SavedLook> {
    const key = keyOf(input);
    /* 추천 룩 저장은 같은 카드를 여러 번 담지 않도록 사진으로 중복을 막는다.
       반면 직접 기록한 룩은 같은 사진을 다른 날짜에 다시 입을 수 있으므로,
       사진이 같더라도 각각의 착장 기록으로 남겨야 한다. */
    const existing =
      input.origin === 'closet' || key == null
        ? undefined
        : savedLooks.find((l) => keyOf(l) === key);
    if (existing) return existing;

    const origin = input.origin ?? 'ai';
    const serverItems = input.items?.filter((item) => item.source === 'closet') ?? [];

    /* 서버로 보낼 수 있는가 — 올릴 사진(원격 주소 포함)이나 내 옷장 옷이 있어야 한다.
       번들 목업 이미지(asset)뿐인 룩은 올릴 실체가 없어 이 기기에만 담는다. */
    const canUpload = isAuthed() && (Boolean(input.image) || serverItems.length > 0);
    if (!canUpload) return addLocalLook(input, origin);

    const meta = {
      schedule: (input.note ?? input.comment ?? '').trim(),
      hashtags: input.tags ?? [],
      ...(input.createCalendar && input.entryDate
        ? { calendarDate: input.entryDate, overwriteCalendar: input.overwriteCalendar }
        : null),
    };
    const dto = input.image
      ? await createLookbookFromPhoto({
          photoUri: input.image,
          wardrobeItemIds: serverItems.map((item) => item.id),
          ...meta,
        })
      : await createLookbookFromWardrobe({
          wardrobeItemIds: serverItems.map((item) => item.id),
          ...meta,
        });

    // 서버에 자리가 없는 값들은 여기서 붙여 둔다 — toLook 이 이걸 다시 얹는다.
    overlays[dto.id] = {
      comment: input.comment,
      reason: input.reason,
      origin,
      entryDate: input.entryDate,
    };
    const look = toLook(dto);
    serverLooks = [look, ...serverLooks];
    notify();
    if (isProcessing(dto.status)) watchProcessing(dto.id);
    return look;
  },

  async removeLook(id: string) {
    const local = localLooks.find((l) => l.id === id);
    if (local) {
      localLooks = localLooks.filter((l) => l.id !== id);
      notify();
      return;
    }
    await deleteLookbook(id);
    serverLooks = serverLooks.filter((l) => l.id !== id);
    delete overlays[id];
    notify();
  },

  /**
   * 메모·태그 수정. 사진과 저장 시각은 건드리지 않는다.
   * 태그는 서버에 남고, 메모는 서버에 자리가 없어 오버레이에만 남는다.
   */
  async updateLook(id: string, patch: { memo?: string; tags?: string[] }) {
    const memo = patch.memo?.trim() || undefined;
    const isLocal = localLooks.some((l) => l.id === id);

    if (!isLocal) {
      overlays[id] = { ...overlays[id], memo };
      if (patch.tags) {
        const dto = await patchLookbook(id, { hashtags: patch.tags });
        serverLooks = serverLooks.map((l) => (l.id === id ? toLook(dto) : l));
        notify();
        return;
      }
      serverLooks = serverLooks.map((l) => (l.id === id ? { ...l, memo } : l));
      notify();
      return;
    }

    localLooks = localLooks.map((l) =>
      l.id === id ? { ...l, memo, tags: patch.tags ?? l.tags } : l,
    );
    notify();
  },

  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  getLoadState: () => loadState,
};

/** 서버에 올릴 수 없는 룩 — 예전과 같은 로컬 저장. */
function addLocalLook(
  input: {
    image?: string;
    asset?: number;
    comment?: string;
    tags?: string[];
    reason?: string;
    items?: EntryItem[];
    note?: string;
    entryDate?: string;
  },
  origin: LookOrigin,
): SavedLook {
  const look: SavedLook = {
    id: `local-${Date.now()}`,
    image: input.image,
    asset: input.asset,
    comment: input.comment,
    reason: input.reason,
    origin,
    items: input.items?.length ? input.items : undefined,
    note: input.note?.trim() || undefined,
    entryDate: input.entryDate,
    tags: input.tags ?? [],
    savedAt: Date.now(),
  };
  localLooks = [look, ...localLooks];
  notify();
  return look;
}

function isAuthed(): boolean {
  const { status, isDemo } = authStore.getState();
  // 데모 세션은 서버 토큰이 없다 — 부르면 401 이라 로컬로 남긴다.
  return status === 'authed' && !isDemo;
}

function isProcessing(status: LookbookStatus): boolean {
  return status === 'REGISTERED' || status === 'PROCESSING';
}

const PROCESSING_POLL_MS = 3_000;
const MAX_PROCESSING_POLL_MS = 3 * 60_000;
const watching = new Set<string>();

/**
 * 사진으로 올린 룩은 옷 추출이 끝나야 담긴 옷이 채워진다.
 *
 * 화면이 아니라 스토어가 맡는 이유는 캘린더와 같다 — 올리고 목록으로 돌아가는 게
 * 정상 흐름이라, 화면에 걸면 그 화면을 벗어나는 순간 추적이 끊긴다.
 */
function watchProcessing(lookbookId: string) {
  if (watching.has(lookbookId)) return;
  watching.add(lookbookId);
  const startedAt = Date.now();

  const tick = async () => {
    // 지켜보는 사이에 지워졌으면 그만둔다.
    if (!serverLooks.some((l) => l.id === lookbookId)) {
      watching.delete(lookbookId);
      return;
    }
    if (Date.now() - startedAt > MAX_PROCESSING_POLL_MS) {
      watching.delete(lookbookId);
      return;
    }

    try {
      const status = await getLookbookProcessingStatus(lookbookId);
      if (status.is_terminal) {
        watching.delete(lookbookId);
        // 상태만으로는 어떤 옷이 나왔는지 모른다 — 룩을 다시 받아야 목록이 채워진다.
        const fresh = await getLookbook(lookbookId);
        serverLooks = serverLooks.map((l) => (l.id === lookbookId ? toLook(fresh) : l));
        notify();
        return;
      }
      const current = serverLooks.find((l) => l.id === lookbookId);
      if (current && current.status !== status.status) {
        serverLooks = serverLooks.map((l) =>
          l.id === lookbookId ? { ...l, status: status.status } : l,
        );
        notify();
      }
    } catch {
      // 일시적인 실패로 추적을 끝내지 않는다 — 다음 회차에 복구된다.
    }
    setTimeout(() => void tick(), PROCESSING_POLL_MS);
  };

  setTimeout(() => void tick(), PROCESSING_POLL_MS);
}

export function useSavedLooks() {
  return useSyncExternalStore(savedLookStore.subscribe, savedLookStore.getLooks, savedLookStore.getLooks);
}

/** 목록 로딩 상태 — '내 룩북' 탭이 로딩·에러 화면을 그리는 데 쓴다. */
export function useSavedLooksState(): LoadState {
  return useSyncExternalStore(
    savedLookStore.subscribe,
    savedLookStore.getLoadState,
    savedLookStore.getLoadState,
  );
}
