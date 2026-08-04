import { useSyncExternalStore } from 'react';

import { CLOSET_ITEMS, SHARED_CLOSET_ITEMS, type WardrobeItem, type WardrobeSource } from '@/constants/wardrobe';
import type { AllowedHashtag } from '@/state/lookbook';

/**
 * 착장 캘린더 기록 — 날짜 하나에 기록 하나.
 *
 * 한 기록은 '그날의 룩 사진'과 '입은 옷 목록'을 **함께** 담는다. 둘은 배타적 선택이 아니라
 * 같은 하루를 다른 각도로 남긴 것이라, 사진만 있는 날도 옷만 있는 날도 유효하다.
 * 옷은 내 옷장·앱 카탈로그·친구 옷장 어디서 왔는지(source)까지 같이 저장해 나중에 되짚을 수 있게 한다.
 *
 * 저장은 아직 메모리(룩북 스토어와 동일) — 백엔드가 붙으면 이 스토어의 함수만 API 호출로 바꾼다.
 */

export type EntryItem = {
  id: string;
  source: WardrobeSource;
  name: string;
  image?: string;
  /** 친구 옷장에서 가져온 옷의 주인 */
  owner?: string;
};

export type CalendarEntry = {
  /** 'YYYY-MM-DD' */
  date: string;
  photo?: string;
  items: EntryItem[];
  /**
   * 그날 무슨 일정이었는지 — '팀 회의', '친구 결혼식'처럼 자유롭게 적는다.
   * 해시태그(무드·상황)와 따로 두는 이유: 태그는 고르는 것이고 일정은 그날에만 있는 사실이다.
   * "왜 이 옷을 입었나"를 나중에 되짚는 단서라 남의 태그 체계에 끼워 맞출 수 없다.
   */
  note?: string;
  tags: AllowedHashtag[];
  /** 함께 쓰는 옷장 친구에게 공개 여부 */
  shared: boolean;
  /**
   * 같이 만들어진 룩북 룩(state/saved.ts SavedLook.id).
   * 한 번 이어 붙이면 끊지 않는다 — 룩북에서 그 룩을 지우면 여기 값만 남는데,
   * 캘린더 화면은 실제 룩을 찾지 못하면 연결 줄을 그리지 않는다.
   */
  lookId?: string;
  /** 외부 공유 링크용 코드 — 기록당 한 번 만들어 고정한다(링크가 매번 바뀌면 안 되므로) */
  shareCode: string;
  updatedAt: number;
};

const WEEKDAY_LABELS = ['일', '월', '화', '수', '목', '금', '토'];

const pad = (n: number) => String(n).padStart(2, '0');

/** (2026, 7, 8) → '2026-07-08' */
export function toDateKey(year: number, month: number, day: number): string {
  return `${year}-${pad(month)}-${pad(day)}`;
}

export function todayKey(): string {
  const now = new Date();
  return toDateKey(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

/** '2026-07-08' → { year, month, day } */
export function parseDateKey(key: string) {
  const [year, month, day] = key.split('-').map(Number);
  return { year, month, day };
}

/** '2026-07-08' → '7월 8일 (수)' */
export function formatDateLabel(key: string): string {
  const { year, month, day } = parseDateKey(key);
  const weekday = WEEKDAY_LABELS[new Date(year, month - 1, day).getDay()];
  return `${month}월 ${day}일 (${weekday})`;
}

function makeShareCode(): string {
  return Math.random().toString(36).slice(2, 10);
}

/** 공유 링크 — 친구가 링크만으로 이 착장을 볼 수 있는 주소(백엔드 연동 전 목업 도메인) */
export function lookShareUrl(code: string): string {
  return `https://cozy.app/look/${code}`;
}

/** 옷장/카탈로그 아이템 → 기록에 담기는 형태 */
export function toEntryItem(item: WardrobeItem, source: WardrobeSource): EntryItem {
  return { id: item.id, source, name: item.name, image: item.image, owner: item.owner };
}

/** 기록 안에서 옷을 구분하는 키 — 소스가 다르면 id 가 겹쳐도 다른 옷이다 */
export function entryItemKey(item: { source: WardrobeSource; id: string }): string {
  return `${item.source}:${item.id}`;
}

function seed(
  date: string,
  photo: string,
  tags: AllowedHashtag[],
  picks: EntryItem[],
  note?: string,
  shared = false,
  lookId?: string,
): CalendarEntry {
  return {
    date,
    photo,
    items: picks,
    note,
    tags,
    shared,
    lookId,
    shareCode: makeShareCode(),
    updatedAt: 0,
  };
}

const mine = (id: string) => toEntryItem(CLOSET_ITEMS.find((i) => i.id === id)!, 'closet');
const friend = (id: string) => toEntryItem(SHARED_CLOSET_ITEMS.find((i) => i.id === id)!, 'shared');

const SEED_ENTRIES: CalendarEntry[] = [
  seed(
    '2026-07-03',
    'https://i.pinimg.com/736x/c1/ae/c8/c1aec88282cee841eca0f6e0da5d1174.jpg',
    ['출근', '미니멀'],
    [mine('2'), mine('3')],
    '분기 보고 발표',
  ),
  seed(
    '2026-07-07',
    'https://i.pinimg.com/736x/55/26/0d/55260de328aec1e50740655fd4b5fdc5.jpg',
    ['데이트'],
    [mine('1'), mine('4'), mine('6')],
    '기념일 저녁 약속',
    true,
    's3',
  ),
  seed(
    '2026-07-12',
    'https://i.pinimg.com/736x/b4/cd/22/b4cd22015add333e10cd2ba06067406b.jpg',
    ['나들이', '캐주얼'],
    [mine('3'), mine('4')],
  ),
  seed(
    '2026-07-20',
    'https://i.pinimg.com/736x/ec/96/f3/ec96f39eb800d19290736c17f0253ed9.jpg',
    ['여행'],
    [friend('s1'), mine('5')],
    '제주 2박 3일',
  ),
];

let entries: Record<string, CalendarEntry> = Object.fromEntries(
  SEED_ENTRIES.map((e) => [e.date, e]),
);

const listeners = new Set<() => void>();

function notify() {
  entries = { ...entries };
  listeners.forEach((l) => l());
}

export const calendarStore = {
  getEntries: () => entries,
  getEntry: (date: string): CalendarEntry | undefined => entries[date],

  /** 새 기록 저장 또는 기존 기록 덮어쓰기. shareCode 와 룩북 연결은 기존 것을 유지한다. */
  saveEntry(input: {
    date: string;
    photo?: string;
    items: EntryItem[];
    note?: string;
    tags: AllowedHashtag[];
    shared: boolean;
    lookId?: string;
  }): CalendarEntry {
    const prev = entries[input.date];
    const next: CalendarEntry = {
      date: input.date,
      photo: input.photo,
      items: input.items,
      note: input.note?.trim() || undefined,
      tags: input.tags,
      shared: input.shared,
      lookId: input.lookId ?? prev?.lookId,
      shareCode: prev?.shareCode ?? makeShareCode(),
      updatedAt: Date.now(),
    };
    entries[input.date] = next;
    notify();
    return next;
  },

  removeEntry(date: string) {
    delete entries[date];
    notify();
  },

  setShared(date: string, shared: boolean) {
    const prev = entries[date];
    if (!prev) return;
    entries[date] = { ...prev, shared };
    notify();
  },

  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useCalendarEntries(): Record<string, CalendarEntry> {
  return useSyncExternalStore(
    calendarStore.subscribe,
    calendarStore.getEntries,
    calendarStore.getEntries,
  );
}

export function useCalendarEntry(date: string): CalendarEntry | undefined {
  return useCalendarEntries()[date];
}
