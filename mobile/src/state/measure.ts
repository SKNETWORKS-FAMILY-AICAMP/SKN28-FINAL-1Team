import { useSyncExternalStore } from 'react';

/**
 * 체형측정 플로우(STEP1 입력 → STEP2 촬영 → STEP3 결과) 전역 상태.
 *
 * expo-router 는 세 화면이 서로 다른 라우트라 화면 간 공유 부모가 없다.
 * authStore 와 동일한 경량 모듈 스토어(useSyncExternalStore) 로 스텝 간 데이터를 잇는다.
 *
 * ⚠️ 현재 `estimate()` 는 입력 기반 mock 이다.
 * TODO(backend): 체형측정 API 확정 시 mock 만 실제 호출로 교체.
 *   - 동기:   POST /api/v1/measure  → { measures, sizes }
 *   - 비동기: POST → { job_id } → GET /api/v1/measure/{job_id} 폴링 (#4 백그라운드)
 */

export type Sex = 'female' | 'male' | 'none';

export type MeasureInput = { height: number; weight: number; sex: Sex };
/** 사진 URI (없으면 null). 지금은 실제 카메라 대신 mock URI 를 넣는다. */
export type MeasurePhotos = { front: string | null; side: string | null };

export type Measurement = {
  shoulder: number; // 어깨너비
  chest: number; // 가슴둘레
  waist: number; // 허리둘레
  hip: number; // 엉덩이둘레
};
export type SizeMatch = { brand: string; size: string; fit: string };

export type MeasureResult = {
  measures: Measurement;
  sizes: SizeMatch[];
  usedPhotos: boolean; // 사진을 써서 추정했는지 (안내문 분기용)
};

type EstimateStatus = 'idle' | 'loading' | 'success' | 'error';

type MeasureState = {
  input: MeasureInput | null;
  photos: MeasurePhotos;
  status: EstimateStatus;
  result: MeasureResult | null;
  error: string | null;
};

const EMPTY: MeasureState = {
  input: null,
  photos: { front: null, side: null },
  status: 'idle',
  result: null,
  error: null,
};

// 입력을 건너뛰고 결과로 직접 진입한 경우의 안전 기본값 (170cm/63kg).
const DEFAULT_INPUT: MeasureInput = { height: 170, weight: 63, sex: 'none' };

let state: MeasureState = EMPTY;
const listeners = new Set<() => void>();

function setState(next: Partial<MeasureState>): void {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

const round1 = (n: number) => Math.round(n * 10) / 10;

/**
 * mock 추정: 170cm/63kg 기준값에서 입력 편차만큼 보정한다.
 * 실제 값이 아니라 플로우 검증용 자리채움 (→ API 로 대체될 함수).
 */
function mockEstimate(input: MeasureInput): Measurement {
  const dh = input.height - 170;
  const dw = input.weight - 63;
  return {
    shoulder: round1(41.2 + dh * 0.12 + dw * 0.05),
    chest: round1(92.5 + dw * 0.7 + dh * 0.1),
    waist: round1(78.0 + dw * 0.8 + dh * 0.05),
    hip: round1(95.8 + dw * 0.6 + dh * 0.1),
  };
}

function mockSizes(chest: number): SizeMatch[] {
  const tier = chest < 90 ? 'S' : chest < 98 ? 'M' : 'L';
  const up = tier === 'S' ? 'M' : tier === 'M' ? 'L' : 'XL';
  return [
    { brand: '무신사 스탠다드', size: tier, fit: '딱 맞음' },
    { brand: '유니클로', size: up, fit: '여유 있음' },
    { brand: 'COS', size: tier, fit: '딱 맞음' },
  ];
}

export const measureStore = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  getState(): MeasureState {
    return state;
  },

  /** 새 측정 플로우 시작 — 이전 데이터 초기화 (STEP1 진입 시 호출) */
  reset(): void {
    setState({ ...EMPTY, photos: { front: null, side: null } });
  },

  setInput(input: MeasureInput): void {
    setState({ input });
  },

  setPhoto(key: keyof MeasurePhotos, uri: string): void {
    setState({ photos: { ...state.photos, [key]: uri } });
  },

  /**
   * 치수 추정 실행. STEP2 완료(또는 건너뛰기) 시 호출하고, 결과는 STEP3 가 구독한다.
   * 화면이 언마운트돼도 이 스토어에 결과가 남으므로, 나갔다 돌아와도 결과가 유지된다.
   */
  async estimate(): Promise<void> {
    const input = state.input ?? DEFAULT_INPUT;
    setState({ status: 'loading', error: null, result: null });
    try {
      // TODO(backend): 아래 mock 을 실제 API 호출로 교체 (동기/비동기 job)
      await new Promise((resolve) => setTimeout(resolve, 1200));
      const measures = mockEstimate(input);
      const usedPhotos = Boolean(state.photos.front && state.photos.side);
      setState({
        status: 'success',
        result: { measures, sizes: mockSizes(measures.chest), usedPhotos },
      });
    } catch (e) {
      setState({
        status: 'error',
        error: e instanceof Error ? e.message : '치수 추정에 실패했어요.',
      });
    }
  },

  /** STEP3 에서 사용자가 직접 수정한 치수를 반영 */
  updateMeasures(measures: Measurement): void {
    if (!state.result) return;
    setState({ result: { ...state.result, measures } });
  },
};

export function useMeasure(): MeasureState {
  return useSyncExternalStore(
    measureStore.subscribe,
    measureStore.getState,
    measureStore.getState,
  );
}
