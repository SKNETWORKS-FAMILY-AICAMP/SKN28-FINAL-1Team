import { useCallback, useEffect, useRef, useState } from 'react';

import {
  deleteWardrobeItem,
  getUploadJob,
  getWardrobeItem,
  listWardrobeItems,
  patchWardrobeItem,
  uploadWardrobePhoto,
  type UploadJob,
  type WardrobeApiItem,
  type WardrobeItemPatch,
  type WardrobeItemQuery,
} from '@/lib/wardrobeApi';

/**
 * 옷장 데이터 훅. 전송은 lib/wardrobeApi.ts, 상태·폴링은 여기.
 * useHome 과 같은 모양({ data, loading, error, reload })을 유지한다.
 */

type ItemsResult = {
  items: WardrobeApiItem[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  /** 서버 왕복 없이 목록에서 지운다 — 삭제 직후 화면이 먼저 반응하도록 */
  removeLocal: (itemId: string) => void;
  /** 수정 결과를 목록에 반영 */
  replaceLocal: (item: WardrobeApiItem) => void;
};

export function useWardrobeItems(query: WardrobeItemQuery = {}, enabled = true): ItemsResult {
  const [items, setItems] = useState<WardrobeApiItem[]>([]);
  // 끄고 시작하면 첫 화면이 로딩으로 깜빡이지 않는다(비회원 등).
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  /* 첫 setState 를 await 뒤로 미룬다 — effect 안에서 동기적으로 상태를 바꾸면
     렌더 중 갱신이 되어 react-hooks 규칙에 걸리고, 한 프레임 낭비된다. */
  const load = useCallback(async () => {
    if (!enabled) return;
    try {
      const next = await listWardrobeItems(query);
      setItems(next);
      setError(null);
    } catch (e) {
      setItems([]);
      setError(e instanceof Error ? e.message : '옷장을 불러오지 못했어요');
    } finally {
      setLoading(false);
    }
    // 객체 참조가 아니라 실제 조건값이 바뀔 때만 재요청
  }, [query.category_large, query.confirmed, enabled]);

  useEffect(() => {
    /* 마운트 시 데이터 가져오기 — 규칙은 load() 안의 setState 를 정적으로 잡지만,
       상태는 응답이 온 뒤에 바뀐다(렌더 중 갱신이 아니다). use-home.ts 도 같은 형태. */
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  /** 다시 시도 — 사용자 조작에서 부르므로 여기선 로딩 표시를 켜도 된다. */
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    await load();
  }, [load]);

  const removeLocal = useCallback((itemId: string) => {
    setItems((prev) => prev.filter((i) => i.id !== itemId));
  }, []);

  const replaceLocal = useCallback((item: WardrobeApiItem) => {
    setItems((prev) => prev.map((i) => (i.id === item.id ? item : i)));
  }, []);

  return { items, loading, error, reload, removeLocal, replaceLocal };
}

type ItemResult = {
  item: WardrobeApiItem | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  /** 수정 결과를 화면에 즉시 반영 */
  setItem: (item: WardrobeApiItem) => void;
};

/** 아이템 한 벌. 상세 화면에서 쓴다. */
export function useWardrobeItem(itemId: string | undefined): ItemResult {
  const [item, setItem] = useState<WardrobeApiItem | null>(null);
  const [loading, setLoading] = useState(Boolean(itemId));
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!itemId) {
      setError('아이템을 찾을 수 없어요');
      setLoading(false);
      return;
    }
    try {
      setItem(await getWardrobeItem(itemId));
      setError(null);
    } catch (e) {
      setItem(null);
      setError(e instanceof Error ? e.message : '아이템을 불러오지 못했어요');
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    await load();
  }, [load]);

  return { item, loading, error, reload, setItem };
}

/** 폴링 간격·한도 — 누끼+캡셔닝이 GPU 큐를 타므로 즉시 끝나지 않는다. */
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 120_000;

export type UploadPhase = 'idle' | 'uploading' | 'processing' | 'done' | 'failed';

type UploadResult = {
  phase: UploadPhase;
  /** DONE 일 때 이 사진에서 나온 아이템들 (1장 → N벌) */
  items: WardrobeApiItem[];
  error: string | null;
  jobId: string | null;
  /** 사진 한 장을 올리고 처리가 끝날 때까지 따라간다 */
  start: (uri: string, opts?: { name?: string; mimeType?: string }) => Promise<void>;
  reset: () => void;
};

/**
 * 사진 업로드 → job 폴링 → 결과 아이템.
 *
 * 등록이 비동기라 화면은 세 단계를 보여줘야 한다:
 *   uploading(사진 전송) → processing(누끼·분류 대기) → done(확인·수정할 아이템 N개)
 * 결과 아이템은 confirmed=false 이므로, 사용자가 태그를 확인하고 PATCH 로 확정해야
 * 옷장에 정식으로 들어간다.
 */
export function useWardrobeUpload(): UploadResult {
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [items, setItems] = useState<WardrobeApiItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  /* 화면을 떠난 뒤에도 폴링이 계속 돌면(그리고 setState 하면) 안 된다. */
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const reset = useCallback(() => {
    setPhase('idle');
    setItems([]);
    setError(null);
    setJobId(null);
  }, []);

  const start = useCallback(async (uri: string, opts?: { name?: string; mimeType?: string }) => {
    setPhase('uploading');
    setItems([]);
    setError(null);
    setJobId(null);

    let id: string;
    try {
      const accepted = await uploadWardrobePhoto(uri, opts);
      if (!alive.current) return;
      id = accepted.job_id;
      setJobId(id);
      setPhase('processing');
    } catch (e) {
      if (!alive.current) return;
      setPhase('failed');
      setError(e instanceof Error ? e.message : '사진을 올리지 못했어요');
      return;
    }

    const startedAt = Date.now();
    /* 재귀 setTimeout — setInterval 은 응답이 간격보다 느릴 때 요청이 겹친다. */
    const poll = async () => {
      if (!alive.current) return;

      let job: UploadJob;
      try {
        job = await getUploadJob(id);
      } catch (e) {
        if (!alive.current) return;
        setPhase('failed');
        setError(e instanceof Error ? e.message : '처리 상태를 확인하지 못했어요');
        return;
      }
      if (!alive.current) return;

      if (job.status === 'DONE') {
        setItems(job.items);
        setPhase('done');
        return;
      }
      if (job.status === 'FAILED') {
        setPhase('failed');
        setError(job.error_message || '사진을 처리하지 못했어요. 다시 시도해 주세요.');
        return;
      }
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        setPhase('failed');
        setError('처리가 오래 걸리고 있어요. 잠시 후 옷장에서 확인해 주세요.');
        return;
      }
      setTimeout(poll, POLL_INTERVAL_MS);
    };

    setTimeout(poll, POLL_INTERVAL_MS);
  }, []);

  return { phase, items, error, jobId, start, reset };
}

/** 태그 확인·수정 후 확정. 화면에서 바로 쓰도록 얇게 감쌌다. */
export async function confirmWardrobeItem(
  itemId: string,
  patch: WardrobeItemPatch = {},
): Promise<WardrobeApiItem> {
  return patchWardrobeItem(itemId, { ...patch, confirmed: true });
}

export { deleteWardrobeItem, patchWardrobeItem };
