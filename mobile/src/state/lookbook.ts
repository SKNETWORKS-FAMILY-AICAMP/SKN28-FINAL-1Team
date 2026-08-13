import { useSyncExternalStore } from 'react';

import { listPublicLookbooks, type LookbookPostDto } from '@/lib/lookbookApi';

/** 사용자가 선택할 수 있는 해시태그 (관리자 정의 목록) */
export const ALLOWED_HASHTAGS = ['출근', '데이트', '나들이', '여행', '미니멀', '캐주얼'] as const;

export type AllowedHashtag = (typeof ALLOWED_HASHTAGS)[number];

export type LookPost = {
  id: string;
  image: string;
  tags: AllowedHashtag[];
  price?: string;
  /**
   * 누르면 열리는 룩 상세(constants/today-look.ts LOOK_VARIANTS 의 id).
   *
   * 피드 6개가 룩 3종을 나눠 가리키고 있어 **일부는 겹친다.** 룩 API 가 붙으면
   * 게시물마다 자기 룩을 들고 오므로 이 필드가 그대로 그 값이 된다.
   */
  variantId?: string;
  createdAt: number;
};

const SEED_LOOKS: LookPost[] = [
  {
    id: '1',
    variantId: 'daily',
    image: 'https://i.pinimg.com/736x/c1/ae/c8/c1aec88282cee841eca0f6e0da5d1174.jpg',
    tags: ['출근', '미니멀'],
    price: '₩189,000',
    createdAt: 1,
  },
  {
    id: '2',
    variantId: 'date',
    image: 'https://i.pinimg.com/736x/55/26/0d/55260de328aec1e50740655fd4b5fdc5.jpg',
    tags: ['데이트', '캐주얼'],
    price: '₩97,000',
    createdAt: 2,
  },
  {
    id: '3',
    variantId: 'daily',
    image: 'https://i.pinimg.com/736x/32/7a/f3/327af326d108881015d4eea726f1cb51.jpg',
    tags: ['출근'],
    price: '₩245,000',
    createdAt: 3,
  },
  {
    id: '4',
    variantId: 'outdoor',
    image: 'https://i.pinimg.com/736x/b4/cd/22/b4cd22015add333e10cd2ba06067406b.jpg',
    tags: ['나들이', '캐주얼'],
    price: '₩132,000',
    createdAt: 4,
  },
  {
    id: '5',
    variantId: 'outdoor',
    image: 'https://i.pinimg.com/736x/ec/96/f3/ec96f39eb800d19290736c17f0253ed9.jpg',
    tags: ['여행', '캐주얼'],
    price: '₩88,000',
    createdAt: 5,
  },
  {
    id: '6',
    variantId: 'date',
    image: 'https://i.pinimg.com/736x/91/06/91/910691d6e2034af20a8667c7d8781f24.jpg',
    tags: ['데이트'],
    price: '₩156,000',
    createdAt: 6,
  },
];

/** 사용자가 전체공개한 룩 — 서버에서 온다. */
let publicLooks: LookPost[] = [];
/** 보이는 목록 = 공개된 남의 룩 + 앱 기본 룩. 같은 참조를 유지해야 해서 캐시한다. */
let looks: LookPost[] = [...SEED_LOOKS];
const listeners = new Set<() => void>();

type LoadState = { loading: boolean; error: string | null; loaded: boolean };
let loadState: LoadState = { loading: false, error: null, loaded: false };

function rebuild() {
  /* 공개된 룩이 앞, 앱 기본 룩이 뒤. 기본 룩은 시간이 지나도 자리를 지켜야 해서
     최신순 정렬에 섞지 않는다 — 둘러보기의 바닥이라는 뜻이다. */
  looks = [...publicLooks, ...SEED_LOOKS];
}

function notify() {
  rebuild();
  listeners.forEach((l) => l());
}

export function isAllowedHashtag(value: string): value is AllowedHashtag {
  return (ALLOWED_HASHTAGS as readonly string[]).includes(value);
}

/** 서버 룩 → 피드 카드. 우리가 정한 해시태그만 남긴다(칩 필터가 그 목록이라). */
function toFeedLook(dto: LookbookPostDto): LookPost {
  return {
    id: dto.id,
    image: dto.image_url,
    tags: (dto.hashtags ?? []).filter(isAllowedHashtag),
    createdAt: Date.parse(dto.created_at) || 0,
  };
}

export const lookbookStore = {
  getLooks: () => looks,
  getLoadState: () => loadState,

  /**
   * 둘러보기 피드를 받아 온다. 비회원도 볼 수 있어 로그인 여부를 따지지 않는다.
   * 실패해도 앱 기본 룩은 그대로 남으므로 화면이 비지 않는다.
   */
  async load(): Promise<void> {
    loadState = { ...loadState, loading: true, error: null };
    notify();
    try {
      const page = await listPublicLookbooks({ limit: 60 });
      publicLooks = page.results.map(toFeedLook);
      loadState = { loading: false, error: null, loaded: true };
    } catch (error) {
      loadState = {
        loading: false,
        error: error instanceof Error ? error.message : '둘러보기를 불러오지 못했어요.',
        loaded: loadState.loaded,
      };
    }
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

/** 필터 칩용 — '전체' + 허용 해시태그 */
export const LOOKBOOK_FILTER_OPTIONS = ['전체', ...ALLOWED_HASHTAGS];
