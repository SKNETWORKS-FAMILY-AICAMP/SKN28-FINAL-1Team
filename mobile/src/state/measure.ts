import { useSyncExternalStore } from 'react';
import { Platform } from 'react-native';

import { BodyEndpoints } from '@/constants/config';
import { ApiError, api } from '@/lib/apiClient';

/**
 * 체형측정 플로우(STEP1 입력 → STEP2 촬영 → STEP3 결과) 전역 상태.
 *
 * expo-router 는 세 화면이 서로 다른 라우트라 화면 간 공유 부모가 없다.
 * authStore 와 동일한 경량 모듈 스토어(useSyncExternalStore) 로 스텝 간 데이터를 잇는다.
 *
 * 백엔드 연동(팀레포 main, users/body):
 *   - STEP1  "다음"  → PUT   /users/me/body/basic/  { height, weight }  (saveBasic)
 *   - 결과 진입      → GET   /users/me/body/  로 저장된 상세치수를 불러오고,
 *                      없으면 키·몸무게 기반 제안값(mock)을 초기값으로 보여준다 (estimate)
 *   - STEP2  "측정 시작하기" → POST /body/photos/(multipart) → 트랜잭션 폴링 →
 *              성공 시 GET /body/ 로 추론된 치수 로드 (startPhotoMeasurement)
 *   - STEP3  "완료"  → PATCH /users/me/body/detail/  로 수정한 둘레를 저장 (saveDetail)
 * basic/detail 저장은 best-effort — 실패해도 로컬 상태로 플로우는 계속되고, 화면이 토스트로 알린다.
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

// ── 백엔드 신체치수(GET /body/) ────────────────────────────────
// DRF DecimalField 는 문자열("170.0")로 내려올 수 있어 숫자로 정규화한다. 미입력은 null.
type BodyDto = {
  height: string | number | null;
  weight: string | number | null;
  chest: string | number | null;
  waist: string | number | null;
  hip: string | number | null;
  shoulder: string | number | null;
  thigh: string | number | null;
  calf: string | number | null;
  arm: string | number | null;
  updated_at: string | null;
};

function toNum(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/** GET /body/ 조회. 미로그인/오프라인/미입력이면 null (플로우는 mock 로 진행). */
async function fetchBody(): Promise<BodyDto | null> {
  try {
    return await api.get<BodyDto>(BodyEndpoints.me);
  } catch {
    return null;
  }
}

/** 저장된 상세치수를 mock 제안값 위에 덮어쓴다 (저장값 우선, 빈 칸은 mock 유지). */
function mergeMeasures(dto: BodyDto | null, base: Measurement): Measurement {
  if (!dto) return base;
  return {
    shoulder: toNum(dto.shoulder) ?? base.shoulder,
    chest: toNum(dto.chest) ?? base.chest,
    waist: toNum(dto.waist) ?? base.waist,
    hip: toNum(dto.hip) ?? base.hip,
  };
}

/** STEP1 프리필용 — 저장된 키·몸무게 (없으면 null). */
export async function fetchBodyBasic(): Promise<{
  height: number | null;
  weight: number | null;
} | null> {
  const dto = await fetchBody();
  if (!dto) return null;
  return { height: toNum(dto.height), weight: toNum(dto.weight) };
}

// ── 사진 기반 측정 (POST photos → 폴링) ─────────────────────────
type PhotoTxResponse = { transaction_id: string; status: string };

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** FormData 파일 파트 추가 — 웹은 Blob, 네이티브는 {uri,name,type}. */
async function appendImage(
  form: FormData,
  field: string,
  uri: string,
  name: string,
): Promise<void> {
  if (Platform.OS === 'web') {
    const blob = await (await fetch(uri)).blob();
    form.append(field, blob, name);
  } else {
    // RN 네이티브 FormData 파일 파트 형식
    form.append(field, { uri, name, type: 'image/jpeg' } as unknown as Blob);
  }
}

/** 정면·측면 사진을 multipart 로 업로드 → 측정 트랜잭션 생성(202). */
async function uploadBodyPhotos(frontUri: string, sideUri: string): Promise<PhotoTxResponse> {
  const form = new FormData();
  await appendImage(form, 'front_image', frontUri, 'front.jpg');
  await appendImage(form, 'side_image', sideUri, 'side.jpg');
  return api.post<PhotoTxResponse>(BodyEndpoints.photos, form);
}

/** 측정 트랜잭션을 성공/실패까지 2초 간격 폴링 (최대 ~60초). 타임아웃은 실패로 본다. */
async function pollTransaction(transactionId: string): Promise<'succeeded' | 'failed'> {
  for (let i = 0; i < 30; i++) {
    const tx = await api.get<PhotoTxResponse>(BodyEndpoints.photo(transactionId));
    if (tx.status === 'succeeded') return 'succeeded';
    if (tx.status === 'failed') return 'failed';
    await delay(2000);
  }
  return 'failed';
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

  /**
   * STEP1 "다음" — 키·몸무게를 서버에 저장(PUT basic)하고 로컬 입력도 반영한다.
   * 로컬 반영을 먼저 하므로 저장이 실패해도(오프라인 등) 플로우는 이어지고,
   * 실패는 throw 하여 화면이 토스트로 알리게 한다.
   */
  async saveBasic(input: MeasureInput): Promise<void> {
    setState({ input });
    await api.put(BodyEndpoints.basic, {
      height: input.height,
      weight: input.weight,
    });
  },

  setPhoto(key: keyof MeasurePhotos, uri: string): void {
    setState({ photos: { ...state.photos, [key]: uri } });
  },

  /**
   * 치수 추정 실행. STEP2 완료(또는 건너뛰기) 시 호출하고, 결과는 STEP3 가 구독한다.
   * 화면이 언마운트돼도 이 스토어에 결과가 남으므로, 나갔다 돌아와도 결과가 유지된다.
   */
  async estimate(): Promise<void> {
    /* 키·몸무게도 없고 사진도 없으면 추정할 근거가 하나도 없다.
       기본값(170/63)으로 대신 계산하면 사용자가 준 적 없는 수치를 결과로 보여주게 된다. */
    const hasPhotos = Boolean(state.photos.front || state.photos.side);
    if (!state.input && !hasPhotos) {
      setState({
        status: 'error',
        result: null,
        error: '키·몸무게를 입력하거나 사진을 등록해야 치수를 추정할 수 있어요.',
      });
      return;
    }

    const input = state.input ?? DEFAULT_INPUT;
    setState({ status: 'loading', error: null, result: null });
    try {
      // 사진 추론은 다음 단계. 서버에 저장된 상세치수가 있으면 그걸 초기값으로,
      // 없으면 키·몸무게 기반 제안값(mock)을 보여준다. 사용자가 STEP3에서 수정하면
      // saveDetail 로 PATCH 된다. GET 실패(오프라인 등)해도 mock 로 진행한다.
      const measures = mergeMeasures(await fetchBody(), mockEstimate(input));
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

  /**
   * STEP2 "측정 시작하기" — 정면·측면 사진 업로드 → 측정 트랜잭션 폴링 →
   * 성공 시 백엔드가 채운 상세치수를 GET /body/ 로 불러온다.
   * (백엔드 추론은 현재 10초 mock 이지만, 업로드·폴링 흐름은 실제로 동작한다.)
   */
  async startPhotoMeasurement(): Promise<void> {
    const { front, side } = state.photos;
    if (!front || !side) {
      setState({ status: 'error', result: null, error: '정면·측면 사진이 모두 필요해요.' });
      return;
    }
    setState({ status: 'loading', error: null, result: null });
    try {
      const tx = await uploadBodyPhotos(front, side);
      const outcome = await pollTransaction(tx.transaction_id);
      if (outcome !== 'succeeded') {
        setState({ status: 'error', error: '사진 측정에 실패했어요. 다시 시도해주세요.' });
        return;
      }
      // 추론된 상세치수를 불러온다. 비어 있는 값은 키·몸무게 기반 제안값으로 보완.
      const measures = mergeMeasures(await fetchBody(), mockEstimate(state.input ?? DEFAULT_INPUT));
      setState({
        status: 'success',
        result: { measures, sizes: mockSizes(measures.chest), usedPhotos: true },
      });
    } catch (e) {
      setState({
        status: 'error',
        error: e instanceof ApiError ? e.message : '사진 측정에 실패했어요. 다시 시도해주세요.',
      });
    }
  },

  /** STEP3 에서 사용자가 직접 수정한 치수를 반영 (로컬만) */
  updateMeasures(measures: Measurement): void {
    if (!state.result) return;
    setState({ result: { ...state.result, measures } });
  },

  /**
   * STEP3 "완료" — 수정한 둘레를 서버에 저장(PATCH detail)한다.
   * UI에 있는 4개(shoulder/chest/waist/hip)만 보내고 thigh/calf/arm 은 건드리지 않는다.
   * 로컬 반영을 먼저 하므로 저장 실패해도 결과는 유지되고, 실패는 throw 로 알린다.
   */
  async saveDetail(measures: Measurement): Promise<void> {
    if (state.result) setState({ result: { ...state.result, measures } });
    await api.patch(BodyEndpoints.detail, {
      shoulder: measures.shoulder,
      chest: measures.chest,
      waist: measures.waist,
      hip: measures.hip,
    });
  },
};

export function useMeasure(): MeasureState {
  return useSyncExternalStore(
    measureStore.subscribe,
    measureStore.getState,
    measureStore.getState,
  );
}
