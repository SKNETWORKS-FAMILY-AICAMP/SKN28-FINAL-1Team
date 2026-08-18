import { useSyncExternalStore } from 'react';

import { getDiscoveryLooks, type LookGender, type LookGenderFilter } from '@/lib/discoveryLookApi';
import { listPublicLookbooks, type LookbookPostDto } from '@/lib/lookbookApi';

export const ALLOWED_HASHTAGS = [
  '출근', '데이트', '나들이', '여행', '미니멀', '캐주얼', '빈티지', '스트릿', '하객룩',
] as const;
export type AllowedHashtag = (typeof ALLOWED_HASHTAGS)[number];

export type LookPost = {
  id: string;
  image: string;
  tags: string[];
  price?: string;
  variantId?: string;
  gender?: LookGender;
  createdAt: number;
};

let curatedLooks: LookPost[] = [];
let publicLooks: LookPost[] = [];
let looks: LookPost[] = [];
const listeners = new Set<() => void>();
let loadSequence = 0;
type LoadState = { loading: boolean; error: string | null; loaded: boolean };
let loadState: LoadState = { loading: false, error: null, loaded: false };

function notify() {
  looks = [...curatedLooks, ...publicLooks];
  listeners.forEach((listener) => listener());
}

export function isAllowedHashtag(value: string): value is AllowedHashtag {
  return (ALLOWED_HASHTAGS as readonly string[]).includes(value);
}

function toPublicLook(dto: LookbookPostDto): LookPost {
  return {
    id: dto.id,
    image: dto.image_url,
    tags: dto.hashtags ?? [],
    gender: dto.gender ?? undefined,
    createdAt: Date.parse(dto.created_at) || 0,
  };
}

export const lookbookStore = {
  getLooks: () => looks,
  getLoadState: () => loadState,

  async load(gender: LookGenderFilter = 'ALL'): Promise<void> {
    const sequence = ++loadSequence;
    loadState = { ...loadState, loading: true, error: null };
    notify();
    const [curatedResult, publicResult] = await Promise.allSettled([
      getDiscoveryLooks('', '', gender),
      listPublicLookbooks({ limit: 60, gender: gender === 'ALL' ? undefined : gender }),
    ]);
    if (sequence !== loadSequence) return;

    if (curatedResult.status === 'fulfilled') {
      curatedLooks = curatedResult.value.results.map((look) => ({
        id: look.id,
        variantId: look.id,
        image: look.image,
        tags: look.tags,
        price: `₩${look.total_price.toLocaleString('ko-KR')}`,
        gender: look.gender,
        createdAt: 0,
      }));
    }
    if (publicResult.status === 'fulfilled') {
      publicLooks = publicResult.value.results.map(toPublicLook);
    }
    const failureCount = [curatedResult, publicResult].filter((result) => result.status === 'rejected').length;
    loadState = {
      loading: false,
      error: failureCount === 2 ? '둘러보기를 불러오지 못했어요.' : failureCount === 1 ? '일부 룩을 불러오지 못했어요.' : null,
      loaded: curatedResult.status === 'fulfilled' || publicResult.status === 'fulfilled',
    };
    notify();
  },

  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useLookbook() {
  return useSyncExternalStore(lookbookStore.subscribe, lookbookStore.getLooks, lookbookStore.getLooks);
}

export const LOOKBOOK_FILTER_OPTIONS = ['전체', ...ALLOWED_HASHTAGS];
