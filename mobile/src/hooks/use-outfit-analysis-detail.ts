import { useCallback, useEffect, useRef, useState } from 'react';

import { getOwnedOutfitAnalysis, type OutfitAnalysisOwnedDetail } from '@/lib/outfitHistoryApi';

/** 옷장 등록은 GPU 파이프라인이라 몇 분이 걸린다 — 평가 폴링(3초)보다 느슨하게 본다. */
const WARDROBE_POLL_MS = 5_000;
/** 무한 폴링 방지. 옷장 처리 예상(약 5분)에 여유를 둔 상한이다. */
const MAX_POLL_MS = 8 * 60 * 1000;

type Result = {
  analysis: OutfitAnalysisOwnedDetail | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

function wardrobePending(analysis: OutfitAnalysisOwnedDetail | null): boolean {
  const status = analysis?.wardrobe?.status;
  return status === 'PENDING' || status === 'PROCESSING';
}

/**
 * 분석 기록 상세.
 *
 * 옷장 연계가 진행 중이면 같은 엔드포인트를 다시 부른다 — 백엔드가 상세 응답에 옷장 job 상태를
 * 함께 실어주므로 옷장 API 를 따로 폴링할 필요가 없다.
 * 화면을 벗어나면 멈춘다. 서버 작업은 그대로 진행되고, 다시 들어오면 그때 상태를 받는다.
 */
export function useOutfitAnalysisDetail(analysisId: string | undefined): Result {
  const [analysis, setAnalysis] = useState<OutfitAnalysisOwnedDetail | null>(null);
  const [loading, setLoading] = useState(Boolean(analysisId));
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAtRef = useRef(0);
  /* 화면을 떠난 뒤 도착한 응답으로 상태를 건드리지 않는다. */
  const aliveRef = useRef(true);

  const load = useCallback(async () => {
    if (!analysisId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getOwnedOutfitAnalysis(analysisId);
      if (!aliveRef.current) return;
      setAnalysis(res);
    } catch (e) {
      if (!aliveRef.current) return;
      setAnalysis(null);
      setError(e instanceof Error ? e.message : '분석 기록을 불러오지 못했어요');
    } finally {
      if (aliveRef.current) setLoading(false);
    }
  }, [analysisId]);

  useEffect(() => {
    aliveRef.current = true;
    startedAtRef.current = Date.now();
    load();
    return () => {
      aliveRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [load]);

  // 옷장 등록이 끝날 때까지만 다시 부른다
  useEffect(() => {
    if (!wardrobePending(analysis)) return;
    if (Date.now() - startedAtRef.current > MAX_POLL_MS) return;

    timerRef.current = setTimeout(() => {
      if (!aliveRef.current || !analysisId) return;
      getOwnedOutfitAnalysis(analysisId)
        .then((res) => {
          if (aliveRef.current) setAnalysis(res);
        })
        // 일시적인 실패로 화면을 에러로 바꾸지 않는다 — 다음 회차에 복구된다
        .catch(() => {});
    }, WARDROBE_POLL_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [analysis, analysisId]);

  return { analysis, loading, error, reload: load };
}
