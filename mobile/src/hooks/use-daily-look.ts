import { useCallback, useEffect, useRef, useState } from 'react';

import { getTodayLook, isDailyLookPending, type DailyLook } from '@/lib/dailyLookApi';

/** 서버가 poll_after_ms 를 안 주는 비정상 응답에 대비한 안전값 */
const FALLBACK_POLL_MS = 2_000;
/**
 * 무한 폴링 방지 상한. 생성은 보통 수 초~수십 초에 끝난다 — 이걸 넘겼다는 건
 * 워커가 멈춰 있다는 뜻이라 조용히 그만둔다. 홈 카드는 템플릿 폴백으로 이미
 * 성립해 있으므로 사용자에게 따로 알릴 것은 없고, 당겨서 새로고침하면 다시 본다.
 */
const MAX_POLL_MS = 3 * 60 * 1000;

type DailyLookHook = {
  look: DailyLook | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

/**
 * 오늘의 룩 훅 — 조회하고, 생성 중이면 서버가 알려준 간격(poll_after_ms)으로 폴링한다.
 *
 * 폴링 종료는 서버 계약(DailyLookTodayView 문서)을 따른다:
 *   SUCCEEDED → result 표시 / EMPTY → 재시도해도 같은 결과이므로 중단 /
 *   FAILED → 자동 재시도 없음. 화면을 벗어나면 멈추고, 서버 생성은 그대로 진행된다.
 * 재예약을 회차 카운터로 보장하는 구조는 use-outfit-analysis-detail 과 같다
 * (응답이 실패하거나 내용이 그대로면 효과가 다시 돌지 않아 폴링이 조용히 죽는 문제).
 */
export function useDailyLook(enabled = true): DailyLookHook {
  const [look, setLook] = useState<DailyLook | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  /* 폴링 회차. 응답이 실패하거나 내용이 같아도 이 값이 늘어 다음 회차가 예약된다. */
  const [pollCount, setPollCount] = useState(0);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAtRef = useRef(0);
  /* 화면을 떠난 뒤 도착한 응답으로 상태를 건드리지 않는다. */
  const aliveRef = useRef(true);

  const load = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    startedAtRef.current = Date.now();
    try {
      const res = await getTodayLook();
      if (!aliveRef.current) return;
      setLook(res);
    } catch (e) {
      if (!aliveRef.current) return;
      setLook(null);
      setError(e instanceof Error ? e.message : '오늘의 룩을 불러오지 못했어요');
    } finally {
      if (aliveRef.current) setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    aliveRef.current = true;
    load();
    return () => {
      aliveRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [load]);

  // 생성이 끝날 때까지만 다시 부른다 (EMPTY/FAILED 는 재시도해도 같다 — 서버 계약)
  useEffect(() => {
    if (!enabled || !isDailyLookPending(look)) return;
    if (Date.now() - startedAtRef.current > MAX_POLL_MS) return;

    timerRef.current = setTimeout(() => {
      if (!aliveRef.current) return;
      getTodayLook()
        .then((res) => {
          if (aliveRef.current) setLook(res);
        })
        // 일시적인 실패로 화면을 에러로 바꾸지 않는다 — 다음 회차에 복구된다.
        .catch(() => {})
        .finally(() => {
          if (aliveRef.current) setPollCount((n) => n + 1);
        });
    }, look?.poll_after_ms ?? FALLBACK_POLL_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [look, enabled, pollCount]);

  return { look, loading, error, reload: load };
}
