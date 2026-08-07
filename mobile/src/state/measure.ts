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
 *   - STEP1  "다음"  → PUT   /users/me/body/basic/  { gender, height, weight }  (saveBasic)
 *   - 결과 진입      → GET   /users/me/body/  로 저장된 상세치수를 불러오고,
 *                      없으면 키·몸무게 기반 제안값(mock)을 초기값으로 보여준다 (estimate)
 *   - STEP2  "측정 시작하기" → POST /body/photos/(multipart) → 트랜잭션 폴링 →
 *              폴링 응답에 담겨 오는 추론 치수를 그대로 사용 (startPhotoMeasurement)
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

/**
 * GET /body/ 조회. 실패는 그대로 던진다.
 * 미입력 사용자도 200 에 전 필드 null 로 내려오므로(views.BodyMeasurementView),
 * 여기서 나는 예외는 전부 진짜 오류(세션 만료·오프라인·서버 장애)다.
 * 예전엔 이걸 삼켜 null 로 바꿨는데, 그러면 호출부가 "저장된 값 없음"과 구분하지 못해
 * 화면이 조용히 빈 칸·mock 값으로 넘어갔다.
 */
async function fetchBody(): Promise<BodyDto> {
  return api.get<BodyDto>(BodyEndpoints.me);
}

/** 못 불러와도 플로우를 mock 으로 이어야 하는 자리 전용. 삼키되 원인은 로그로 남긴다. */
async function fetchBodyOrNull(): Promise<BodyDto | null> {
  try {
    return await fetchBody();
  } catch (e) {
    console.warn('[measure] 저장된 신체치수를 불러오지 못했습니다', e);
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

/**
 * STEP1 프리필용 — 저장된 키·몸무게 (미입력이면 각각 null).
 * 조회 자체가 실패하면 던진다. 호출부가 "값이 없음"과 "못 불러옴"을 구분해 안내해야 한다.
 */
export async function fetchBodyBasic(): Promise<{
  height: number | null;
  weight: number | null;
}> {
  const dto = await fetchBody();
  return { height: toNum(dto.height), weight: toNum(dto.weight) };
}

// ── 사진 기반 측정 (POST photos → 폴링) ─────────────────────────
/** POST /body/photos/ 접수 응답 (202). */
type PhotoTxResponse = { transaction_id: string; status: string };

/** GET /body/photos/{id}/ 조회 응답 — 무사진 추정 응답과 같은 형식(BodyEstimationResultSerializer). */
type BodyEstimationResult = {
  status: 'in_progress' | 'succeeded' | 'failed';
  source: 'basic_info' | 'photo';
  transaction_id: string | null;
  measurement: BodyDto;
  /** 실패했을 때만 사유가 들어온다. */
  error_message: string | null;
};

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/* 폴링 상한은 서버가 포기하는 시점보다 넉넉해야 한다.
   서버 VLM 호출 타임아웃이 기본 120초이고 응답이 잘리면 한 번 더 부르므로 최악 240초인데,
   예전엔 60초에 끊었다 — 서버는 측정 중인데 화면만 "실패"로 뜨고, 그 뒤 성공한 값이
   조용히 저장돼 "실패했다면서 값은 바뀌어 있는" 상태가 됐다. */
const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 150; // 약 5분
/** 조회가 연속으로 이만큼 실패하면 포기 — 네트워크 순단 한 번에 측정 전체를 버리지 않는다. */
const POLL_MAX_CONSECUTIVE_ERRORS = 3;

/* 상한을 넘겨 화면만 먼저 포기한 트랜잭션. 서버는 사용자당 진행중 1건만 허용하므로
   다시 시도할 때 사진을 새로 올리면 400 만 받는다 — 올리지 말고 이어서 기다려야 한다. */
let pendingTransactionId: string | null = null;

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

/**
 * 측정 트랜잭션을 종료 상태(succeeded/failed)까지 폴링해 응답 전체를 돌려준다.
 * 실패 사유(error_message)와 추정 결과(measurement)가 이 응답에 다 들어 있어서,
 * 호출부가 사유를 그대로 보여주고 별도 GET 없이 치수를 쓸 수 있다.
 * 상한 안에 안 끝나면 null — 실패가 아니라 "서버에서 아직 진행 중"이라 안내 문구가 다르다.
 */
async function pollTransaction(transactionId: string): Promise<BodyEstimationResult | null> {
  let consecutiveErrors = 0;
  for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
    try {
      const tx = await api.get<BodyEstimationResult>(BodyEndpoints.photo(transactionId));
      consecutiveErrors = 0;
      if (tx.status === 'succeeded' || tx.status === 'failed') return tx;
    } catch (e) {
      /* 4xx 는 기다린다고 풀리지 않는다(트랜잭션 없음·세션 만료) — 사유를 그대로 올린다.
         5xx·네트워크 순단은 다음 차례에 다시 물어본다. */
      if (e instanceof ApiError && e.status < 500) throw e;
      if (++consecutiveErrors >= POLL_MAX_CONSECUTIVE_ERRORS) throw e;
    }
    await delay(POLL_INTERVAL_MS);
  }
  return null;
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
    pendingTransactionId = null;
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
    /* 서버는 gender·height·weight 를 **셋 다** 요구하고, gender 는 male|female 만 받는다.
       예전엔 gender 를 안 보내 매번 400 이 났다.
       성별을 안 고른 상태로는 저장할 방법이 없으므로 요청을 보내지 않는다 —
       어차피 400 이 될 요청을 던져 에러 토스트만 띄우느니 로컬 입력만 들고 진행한다.
       (화면에서 성별을 고르게 막아 두어 여기까진 잘 오지 않는다) */
    if (input.sex === 'none') return;
    await api.put(BodyEndpoints.basic, {
      gender: input.sex,
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
      const measures = mergeMeasures(await fetchBodyOrNull(), mockEstimate(input));
      setState({
        status: 'success',
        /* 이 경로는 사진을 쓰지 않는다. 촬영까지 갔다가 실패해 되돌아오면 photos 는 남아 있는데,
           그걸 보고 usedPhotos 를 켜면 사진으로 잰 적 없는 값이 "사진 기반 결과"로 표시된다. */
        result: { measures, sizes: mockSizes(measures.chest), usedPhotos: false },
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
   * 성공하면 폴링 응답에 담겨 온 상세치수를 그대로 쓴다.
   * 실패·지연은 원인을 구분해 알린다 (서버 사유 그대로 / 아직 진행 중).
   */
  async startPhotoMeasurement(): Promise<void> {
    const { front, side } = state.photos;
    if (!front || !side) {
      setState({ status: 'error', result: null, error: '정면·측면 사진이 모두 필요해요.' });
      return;
    }
    setState({ status: 'loading', error: null, result: null });
    try {
      // 앞선 시도가 상한만 넘긴 거라면 그 트랜잭션을 이어서 기다린다.
      const transactionId =
        pendingTransactionId ?? (await uploadBodyPhotos(front, side)).transaction_id;
      pendingTransactionId = transactionId;

      const outcome = await pollTransaction(transactionId);
      if (!outcome) {
        // 서버는 아직 측정 중이다(10분까지 유지) — 실패로 단정하지 않는다.
        setState({
          status: 'error',
          error: '측정이 아직 끝나지 않았어요. 잠시 후 다시 시도해주세요.',
        });
        return;
      }
      pendingTransactionId = null;
      if (outcome.status !== 'succeeded') {
        // 서버가 실패 사유를 error_message 로 준다. 고정 문구로 덮으면 원인을 앱에서 알 길이 없다.
        setState({
          status: 'error',
          error: outcome.error_message ?? '사진 측정에 실패했어요. 다시 시도해주세요.',
        });
        return;
      }
      /* 추론된 상세치수는 조회 응답에 함께 온다 — 따로 GET /body/ 를 부르지 않는다.
         그 GET 이 실패하면 mock 값이 "사진으로 측정한 결과"로 둔갑했었다. */
      const measures = mergeMeasures(outcome.measurement, mockEstimate(state.input ?? DEFAULT_INPUT));
      setState({
        status: 'success',
        result: { measures, sizes: mockSizes(measures.chest), usedPhotos: true },
      });
    } catch (e) {
      // 이어서 기다릴 수 없는 상태(트랜잭션 없음·세션 만료 등)이므로 다음 시도는 새로 올린다.
      pendingTransactionId = null;
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
