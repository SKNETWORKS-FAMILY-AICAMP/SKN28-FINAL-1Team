import { useCallback, useEffect, useRef, useState } from 'react';

import {
  getCalendarProcessingStatus,
  type CalendarProcessingStatus,
} from '@/lib/calendarApi';
import { calendarStore, toDateKey, useCalendarEntries, type CalendarEntry } from '@/state/calendar';

/**
 * 캘린더 데이터 훅. 전송은 lib/calendarApi.ts, 상태·폴링은 여기.
 * useWardrobeItems 와 같은 모양({ ..., loading, error, reload })을 유지한다.
 */

/** 사진 처리는 옷 추출까지 걸리므로 옷장 업로드와 같은 간격으로 본다. */
const PROCESSING_POLL_MS = 5_000;
/** 무한 폴링 방지 상한. 걸리면 stalled 로 알리고 사용자가 직접 새로고침하게 한다. */
const MAX_PROCESSING_POLL_MS = 10 * 60 * 1000;

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

type ProcessingResult = {
  status: CalendarProcessingStatus | null;
  /** 처리가 끝났다(성공이든 실패든). 폴링을 멈춰도 되는 시점. */
  done: boolean;
  /** 상한에 걸려 지켜보기를 멈췄다 — 무한 스피너 대신 새로고침을 권해야 한다. */
  stalled: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

/**
 * 사진 등록 후 옷 추출이 끝날 때까지 지켜본다.
 *
 * 옷만 고른 기록은 처음부터 끝난 상태라 `processing_required` 가 false 로 오고 폴링하지 않는다.
 * 화면을 벗어나면 멈춘다. 서버 작업은 그대로 진행되고, 다시 들어오면 그때 상태를 받는다.
 */
export function useCalendarProcessing(
  calendarId: string | undefined,
  enabled = true,
): ProcessingResult {
  const [status, setStatus] = useState<CalendarProcessingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stalled, setStalled] = useState(false);
  /* 폴링 회차. 응답이 실패하거나 내용이 같아도 이 값이 늘어 다음 회차가 예약된다.
     재예약을 status 변경에만 걸면 한 번 실패했을 때 조용히 멈춘다. */
  const [pollCount, setPollCount] = useState(0);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAtRef = useRef(0);
  /* 화면을 떠난 뒤 도착한 응답으로 상태를 건드리지 않는다. */
  const aliveRef = useRef(true);

  const active = Boolean(calendarId) && enabled;

  const load = useCallback(async () => {
    if (!calendarId || !enabled) return;
    setError(null);
    setStalled(false);
    startedAtRef.current = Date.now();
    try {
      const next = await getCalendarProcessingStatus(calendarId);
      if (aliveRef.current) setStatus(next);
    } catch (e) {
      if (!aliveRef.current) return;
      setError(e instanceof Error ? e.message : '처리 상태를 불러오지 못했어요');
    }
  }, [calendarId, enabled]);

  useEffect(() => {
    aliveRef.current = true;
    startedAtRef.current = Date.now();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    return () => {
      aliveRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [load]);

  const pending = Boolean(status && status.processing_required && !status.is_terminal);

  useEffect(() => {
    if (!active || !pending) return;
    if (Date.now() - startedAtRef.current > MAX_PROCESSING_POLL_MS) {
      setStalled(true);
      return;
    }

    timerRef.current = setTimeout(() => {
      if (!aliveRef.current || !calendarId) return;
      getCalendarProcessingStatus(calendarId)
        .then((next) => {
          if (aliveRef.current) setStatus(next);
        })
        // 일시적인 실패로 화면을 에러로 바꾸지 않는다 — 다음 회차에 복구된다.
        .catch(() => {})
        .finally(() => {
          if (aliveRef.current) setPollCount((n) => n + 1);
        });
    }, PROCESSING_POLL_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [active, pending, calendarId, pollCount]);

  return {
    status,
    done: Boolean(status && (!status.processing_required || status.is_terminal)),
    stalled,
    error,
    refresh: load,
  };
}
