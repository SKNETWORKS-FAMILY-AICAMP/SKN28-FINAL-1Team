import { useCallback, useEffect, useState } from 'react';

import { listCalendarEntries } from '@/lib/calendarApi';
import { calendarStore, toDateKey, useCalendarEntries, type CalendarEntry } from '@/state/calendar';

/**
 * 캘린더 데이터 훅 — "언제 불러올지"와 로딩·오류 표시를 맡는다.
 * 전송은 lib/calendarApi.ts, 기록 보관과 사진 처리 추적은 state/calendar.ts.
 * useWardrobeItems 와 같은 모양({ ..., loading, error, reload })을 유지한다.
 */

type RangeResult = {
  /** 날짜('YYYY-MM-DD') → 기록. 하루에 하나뿐이라 맵으로 둔다. */
  entries: Record<string, CalendarEntry>;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

/** 달의 1일과 말일을 'YYYY-MM-DD' 로 돌려준다. */
export function monthRange(year: number, month: number): { start: string; end: string } {
  const lastDay = new Date(year, month, 0).getDate();
  return { start: toDateKey(year, month, 1), end: toDateKey(year, month, lastDay) };
}

/**
 * 기간을 서버에서 받아 스토어에 채운다.
 *
 * 기록은 캘린더·날짜선택 시트·룩 작성기가 함께 보므로 데이터는 스토어가 들고,
 * 이 훅은 "언제 불러올지"와 로딩·오류 표시만 맡는다.
 */
export function useCalendarRange(
  startDate: string,
  endDate: string,
  enabled = true,
): RangeResult {
  const entries = useCalendarEntries();
  // 끄고 시작하면 첫 화면이 로딩으로 깜빡이지 않는다(비회원 등).
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!enabled) return;
    try {
      await calendarStore.loadRange(startDate, endDate);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '캘린더를 불러오지 못했어요');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, enabled]);

  useEffect(() => {
    /* 마운트 시 데이터 가져오기 — 상태는 응답이 온 뒤에 바뀐다(렌더 중 갱신이 아니다).
       use-wardrobe.ts 도 같은 형태. */
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const reload = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    await load();
  }, [load, enabled]);

  return { entries, loading, error, reload };
}

/** 월 그리드용 — 그 달 1일부터 말일까지. */
export function useCalendarMonth(year: number, month: number, enabled = true): RangeResult {
  const { start, end } = monthRange(year, month);
  return useCalendarRange(start, end, enabled);
}

/** 자주 입은 옷을 셀 때 돌아보는 기간. 계절이 바뀌면 옷도 바뀌므로 너무 길게 잡지 않는다. */
const FREQUENT_WINDOW_DAYS = 90;
/** 기록이 이보다 적으면 "자주"라고 부를 수 없다 — 한 번 입은 옷을 자주라 하면 거짓말이 된다. */
export const FREQUENT_MIN_RECORDS = 3;

export type FrequentItem = { id: string; name: string; image?: string; count: number };

type FrequentResult = {
  items: FrequentItem[];
  /** 돌아본 기간의 기록 수. FREQUENT_MIN_RECORDS 미만이면 화면은 인사이트를 감춘다. */
  recordCount: number;
  loading: boolean;
};

/**
 * 최근에 자주 입은 옷 몇 개.
 *
 * 빈 날에 "그날 뭘 입었는지" 채워 넣는 지름길로 쓴다 — 날짜가 비는 이유는 정보가 없어서가
 * 아니라 기록이 귀찮아서라, 읽을거리보다 입력을 줄이는 쪽이 쓸모 있다.
 *
 * 스토어를 거치지 않고 따로 조회한다. 스토어는 보고 있는 달만 담는데 빈도는 더 긴 기간을
 * 봐야 하고, 여기서 스토어를 채우면 달 이동과 서로 덮어쓴다.
 */
export function useFrequentItems(enabled = true, topN = 3): FrequentResult {
  const [items, setItems] = useState<FrequentItem[]>([]);
  const [recordCount, setRecordCount] = useState(0);
  const [loading, setLoading] = useState(enabled);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;

    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - FREQUENT_WINDOW_DAYS);
    const key = (d: Date) => toDateKey(d.getFullYear(), d.getMonth() + 1, d.getDate());

    listCalendarEntries(key(start), key(end))
      .then((list) => {
        if (!alive) return;
        const counts = new Map<string, FrequentItem>();
        for (const entry of list) {
          for (const link of entry.wardrobe_items) {
            const prev = counts.get(link.wardrobe_item_id);
            if (prev) {
              prev.count += 1;
              continue;
            }
            counts.set(link.wardrobe_item_id, {
              id: link.wardrobe_item_id,
              name: (link.snapshot.item_name as string) || '이름 없는 아이템',
              image: link.image_url || undefined,
              count: 1,
            });
          }
        }
        setItems(
          [...counts.values()].sort((a, b) => b.count - a.count).slice(0, topN),
        );
        setRecordCount(list.length);
      })
      // 인사이트는 곁다리라 실패해도 화면에 오류를 띄우지 않는다 — 조용히 감춘다.
      .catch(() => {})
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [enabled, topN]);

  return { items, recordCount, loading };
}
