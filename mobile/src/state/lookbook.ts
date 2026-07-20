import { useSyncExternalStore } from 'react';

/** 사용자가 선택할 수 있는 해시태그 (관리자 정의 목록) */
export const ALLOWED_HASHTAGS = ['출근', '데이트', '나들이', '여행', '미니멀', '캐주얼'] as const;

export type AllowedHashtag = (typeof ALLOWED_HASHTAGS)[number];

export type LookPost = {
  id: string;
  image: string;
  tags: AllowedHashtag[];
  price?: string;
  createdAt: number;
};

const SEED_LOOKS: LookPost[] = [
  {
    id: '1',
    image: 'https://i.pinimg.com/736x/c1/ae/c8/c1aec88282cee841eca0f6e0da5d1174.jpg',
    tags: ['출근', '미니멀'],
    price: '₩189,000',
    createdAt: 1,
  },
  {
    id: '2',
    image: 'https://i.pinimg.com/736x/55/26/0d/55260de328aec1e50740655fd4b5fdc5.jpg',
    tags: ['데이트', '캐주얼'],
    price: '₩97,000',
    createdAt: 2,
  },
  {
    id: '3',
    image: 'https://i.pinimg.com/736x/32/7a/f3/327af326d108881015d4eea726f1cb51.jpg',
    tags: ['출근'],
    price: '₩245,000',
    createdAt: 3,
  },
  {
    id: '4',
    image: 'https://i.pinimg.com/736x/b4/cd/22/b4cd22015add333e10cd2ba06067406b.jpg',
    tags: ['나들이', '캐주얼'],
    price: '₩132,000',
    createdAt: 4,
  },
  {
    id: '5',
    image: 'https://i.pinimg.com/736x/ec/96/f3/ec96f39eb800d19290736c17f0253ed9.jpg',
    tags: ['여행', '캐주얼'],
    price: '₩88,000',
    createdAt: 5,
  },
  {
    id: '6',
    image: 'https://i.pinimg.com/736x/91/06/91/910691d6e2034af20a8667c7d8781f24.jpg',
    tags: ['데이트'],
    price: '₩156,000',
    createdAt: 6,
  },
];

let looks: LookPost[] = [...SEED_LOOKS];
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

export function isAllowedHashtag(value: string): value is AllowedHashtag {
  return (ALLOWED_HASHTAGS as readonly string[]).includes(value);
}

export const lookbookStore = {
  getLooks: () => looks,
  addLook(input: { image: string; tags: AllowedHashtag[]; price?: string }) {
    const post: LookPost = {
      id: String(Date.now()),
      image: input.image,
      tags: input.tags,
      price: input.price,
      createdAt: Date.now(),
    };
    looks = [post, ...looks];
    notify();
    return post;
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
