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
 * 백엔드 연동 (api/apps/users/views.py):
 *   - STEP1  "다음"          → PUT  /body/basic/  { gender, height, weight }        (saveBasic)
 *   - STEP2  "사진 없이 진행" → POST /body/estimate/ { gender,height,weight }        (estimate)
 *   - STEP2  "측정 시작하기"  → POST /body/photos/ (multipart) → 폴링                (startPhotoMeasurement)
 *   - STEP3  "완료"          → PATCH /body/detail/ 로 수정한 상세 7개 저장           (saveDetail)
 *
 * 추정 수치는 **전부 서버(ml/body_measurement)가 만든다.** 예전에는 여기서 키·몸무게
 * 기반 선형식(mockEstimate)으로 자리채움 값을 만들어 보여줬는데, 서버에 실제 추정
 * API 가 생긴 뒤로도 그대로 남아 학습한 모델이 아니라 가짜 숫자가 화면에 나갔다.
 * 프론트에서 치수를 지어내지 않고, 추정에 실패하면 실패로 보여준다.
 */

export type Sex = 'female' | 'male' | 'none';

export type MeasureInput = { height: number; weight: number; sex: Sex };
/** 사진 URI (없으면 null) */
export type MeasurePhotos = { front: string | null; side: string | null };

/**
 * 서버가 추정하는 상세 치수 7개. 키 이름은 백엔드 BODY_DETAIL_FIELDS 와 1:1 이라
 * PATCH /body/detail/ 에 이 객체를 그대로 실어 보낼 수 있다.
 */
export type Measurement = {
  shoulder: number; // 어깨너비
  chest: number; // 가슴둘레
  waist: number; // 허리둘레
  hip: number; // 엉덩이둘레
  thigh: number; // 허벅지둘레
  calf: number; // 종아리둘레
  arm: number; // 팔뚝둘레
};

/** Measurement 의 키 목록 — DTO 변환·화면 순회에 함께 쓴다. */
export const MEASURE_KEYS = [
  'shoulder',
  'chest',
  'waist',
  'hip',
  'thigh',
  'calf',
  'arm',
] as const;

export type SizeMatch = { brand: string; size: string; fit: string };

export type MeasureResult = {
  measures: Measurement;
  sizes: SizeMatch[];
  usedPhotos: boolean; // 사진을 써서 추정했는지 (안내문 분기용). 서버 응답의 source 로 판단한다.
};

type EstimateStatus = 'idle' | 'loading' | 'success' | 'error';

type MeasureState = {
  input: MeasureInput | null;
  photos: MeasurePhotos;
  status: EstimateStatus;
  result: MeasureResult | null;
  error: string | null;
  /**
   * 실패 원인이 '기본 정보(성별·키·몸무게) 없음'인지. 이 경우 재시도는 같은 실패를
   * 반복하므로 화면이 재시도 대신 STEP1 로 돌려보내야 한다.
   */
  needsBasicInfo: boolean;
};

const EMPTY: MeasureState = {
  input: null,
  photos: { front: null, side: null },
  status: 'idle',
  result: null,
  error: null,
  needsBasicInfo: false,
};

let state: MeasureState = EMPTY;
const listeners = new Set<() => void>();

function setState(next: Partial<MeasureState>): void {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

/**
 * 브랜드 사이즈 매칭 — 아직 백엔드가 없어 가슴둘레 기준 임시 규칙으로 만든다.
 * (치수 자체와 달리 이건 '추정값'이 아니라 표시용 매칭이라 프론트에 남겨둔다.)
 */
function mockSizes(chest: number): SizeMatch[] {
  const tier = chest < 90 ? 'S' : chest < 98 ? 'M' : 'L';
  const up = tier === 'S' ? 'M' : tier === 'M' ? 'L' : 'XL';
  return [
    { brand: '무신사 스탠다드', size: tier, fit: '딱 맞음' },
    { brand: '유니클로', size: up, fit: '여유 있음' },
    { brand: 'COS', size: tier, fit: '딱 맞음' },
  ];
}

// ── 백엔드 응답 형식 ──────────────────────────────────────────
// DRF DecimalField 는 문자열("170.0")로 내려올 수 있어 숫자로 정규화한다. 미입력은 null.
type BodyDto = {
  gender: string | null;
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

/**
 * 무사진 추정(POST /body/estimate/)과 사진 트랜잭션 조회(GET /body/photos/{id}/)가
 * 공유하는 결과 형식 (BodyEstimationResultSerializer).
 */
type BodyEstimationResult = {
  status: 'in_progress' | 'succeeded' | 'failed';
  source: 'basic_info' | 'photo';
  transaction_id: string | null;
  measurement: BodyDto;
  error_message: string | null;
};

function toNum(v: unknown): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * 추정 결과의 상세 7개를 화면용 Measurement 로 바꾼다.
 * 하나라도 비어 있으면 null — 빈 칸을 0 이나 임의값으로 메우면 사용자는 그게
 * 추정 실패인지 진짜 0 인지 구분할 수 없다. (서버는 성공 시 7개를 모두 채워 보낸다)
 */
function toMeasurement(dto: BodyDto | null | undefined): Measurement | null {
  if (!dto) return null;
  const out = {} as Measurement;
  for (const key of MEASURE_KEYS) {
    const value = toNum(dto[key]);
    if (value === null) return null;
    out[key] = value;
  }
  return out;
}

/**
 * 로컬 입력을 서버가 받는 형태로 바꾼다.
 * 성별 미선택('none')은 아예 보내지 않는다 — 서버 ChoiceField 가 male|female 만 받아
 * 빈 값을 보내면 400 이 되고, 생략하면 저장된 값으로 대체된다.
 */
function basicInfoPayload(input: MeasureInput | null): Record<string, string> {
  if (!input) return {};
  const payload: Record<string, string> = {
    height: String(input.height),
    weight: String(input.weight),
  };
  if (input.sex !== 'none') payload.gender = input.sex;
  return payload;
}

/** GET /body/ 조회. 미로그인/오프라인/미입력이면 null. */
async function fetchBody(): Promise<BodyDto | null> {
  try {
    return await api.get<BodyDto>(BodyEndpoints.me);
  } catch {
    return null;
  }
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
type PhotoUploadResponse = { transaction_id: string; status: string };

const POLL_INTERVAL_MS = 2000;
const POLL_ATTEMPTS = 30; // 2초 × 30 = 최대 약 60초

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

/**
 * 정면·측면 사진을 multipart 로 업로드 → 측정 트랜잭션 생성(202).
 *
 * 키·몸무게·성별을 **같이** 보낸다. 생략하면 서버가 저장된 기본 정보를 찾는데,
 * STEP1 에서 저장이 실패했거나(오프라인·인증 만료) 사용자가 입력을 건너뛰었으면
 * 저장된 값이 없어 업로드가 통째로 400 이 된다. 로컬 입력은 이미 손에 있으므로
 * 그걸 실어 보내 STEP1 저장 성공 여부와의 결합을 끊는다.
 */
async function uploadBodyPhotos(
  frontUri: string,
  sideUri: string,
  input: MeasureInput | null,
): Promise<PhotoUploadResponse> {
  const form = new FormData();
  await appendImage(form, 'front_image', frontUri, 'front.jpg');
  await appendImage(form, 'side_image', sideUri, 'side.jpg');
  for (const [key, value] of Object.entries(basicInfoPayload(input))) {
    form.append(key, value);
  }
  return api.post<PhotoUploadResponse>(BodyEndpoints.photos, form);
}

/**
 * 측정 트랜잭션이 끝날 때까지 폴링한다. 끝나면 결과 전체를 그대로 돌려준다 —
 * 이 응답에 추정된 치수와 실패 사유가 이미 들어 있어 GET /body/ 를 다시 부를 필요가 없다.
 * 시간 안에 안 끝나면 null (호출부가 안내 문구를 정한다).
 */
async function pollTransaction(
  transactionId: string,
): Promise<BodyEstimationResult | null> {
  for (let i = 0; i < POLL_ATTEMPTS; i++) {
    const result = await api.get<BodyEstimationResult>(
      BodyEndpoints.photo(transactionId),
    );
    if (result.status !== 'in_progress') return result;
    await delay(POLL_INTERVAL_MS);
  }
  return null;
}

/** 추정 결과 → 화면 상태. 상세 7개를 못 읽으면 null (호출부가 실패로 처리한다). */
function toResult(estimation: BodyEstimationResult): MeasureResult | null {
  const measures = toMeasurement(estimation.measurement);
  if (!measures) return null;
  return {
    measures,
    sizes: mockSizes(measures.chest),
    usedPhotos: estimation.source === 'photo',
  };
}

/** 서버가 성공이라 했는데 치수가 비어 있을 때의 안내 문구. */
const UNREADABLE_RESULT = '추정 결과를 읽지 못했어요. 다시 시도해주세요.';

/**
 * 이 실패가 '기본 정보 없음' 때문인지 판정한다.
 *
 * 두 추정 API 모두 성별·키·몸무게를 생략하면 **저장된 값**으로 대체하고, 그것도
 * 없으면 400 을 준다. 즉 우리가 로컬 입력을 못 보낸 상태에서 400 이 왔다면
 * 서버에도 저장된 값이 없다는 뜻이고, 같은 요청을 재시도해봐야 결과는 같다.
 * 이럴 때 화면은 재시도 버튼 대신 STEP1 입력으로 안내해야 한다.
 */
function isMissingBasicInfo(error: unknown, input: MeasureInput | null): boolean {
  const sentBasicInfo = Boolean(input && input.sex !== 'none');
  return !sentBasicInfo && error instanceof ApiError && error.status === 400;
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
    /* 서버는 gender·height·weight 를 **셋 다** 요구하고, gender 는 male|female 만 받는다.
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
   * 사진 없이 치수 추정 — POST /body/estimate/ (서버 동기 추론, 수십 ms).
   * STEP2 "사진 없이 진행" 과 STEP3 직접 진입 시 호출하고, 결과는 STEP3 가 구독한다.
   * 화면이 언마운트돼도 결과가 이 스토어에 남아 나갔다 돌아와도 유지된다.
   */
  async estimate(): Promise<void> {
    /* 로컬 입력도 사진도 없으면 추정 근거가 없다. 서버에 저장된 기본 정보가 있을 수도
       있지만, 그 경우도 값이 없으면 서버가 400 을 주므로 굳이 왕복하지 않고 먼저 막는다. */
    const hasPhotos = Boolean(state.photos.front || state.photos.side);
    if (!state.input && !hasPhotos) {
      setState({
        status: 'error',
        result: null,
        error: '키·몸무게를 입력하거나 사진을 등록해야 치수를 추정할 수 있어요.',
        needsBasicInfo: true,
      });
      return;
    }

    setState({ status: 'loading', error: null, result: null, needsBasicInfo: false });
    try {
      const estimation = await api.post<BodyEstimationResult>(
        BodyEndpoints.estimate,
        basicInfoPayload(state.input),
      );
      const result = toResult(estimation);
      if (!result) {
        setState({
          status: 'error',
          result: null,
          error: estimation.error_message ?? UNREADABLE_RESULT,
        });
        return;
      }
      setState({ status: 'success', result });
    } catch (e) {
      setState({
        status: 'error',
        result: null,
        // 서버가 준 사유(성별 미입력 등)를 그대로 보여준다. 네트워크 오류는 원문이
        // 'Failed to fetch' 라 사용자에게 의미가 없어 우리 문구로 바꾼다.
        error:
          e instanceof ApiError
            ? e.message
            : '치수 추정에 실패했어요. 잠시 후 다시 시도해주세요.',
        needsBasicInfo: isMissingBasicInfo(e, state.input),
      });
    }
  },

  /**
   * STEP2 "측정 시작하기" — 정면·측면 사진 업로드 → 측정 트랜잭션 폴링.
   * 폴링 응답에 추정된 치수가 함께 오므로 별도 조회 없이 바로 결과를 그린다.
   */
  async startPhotoMeasurement(): Promise<void> {
    const { front, side } = state.photos;
    if (!front || !side) {
      // 사진이 모자란 것이지 기본 정보 문제는 아니다 — 직전 실패의 플래그를 물려받지 않게 끈다.
      setState({
        status: 'error',
        result: null,
        error: '정면·측면 사진이 모두 필요해요.',
        needsBasicInfo: false,
      });
      return;
    }
    setState({ status: 'loading', error: null, result: null, needsBasicInfo: false });
    try {
      const tx = await uploadBodyPhotos(front, side, state.input);
      const estimation = await pollTransaction(tx.transaction_id);

      if (!estimation) {
        setState({
          status: 'error',
          result: null,
          error: '측정이 시간 내에 끝나지 않았어요. 잠시 후 다시 시도해주세요.',
        });
        return;
      }
      if (estimation.status !== 'succeeded') {
        // 서버가 실패 사유를 담아 보낸다 — 뭉뚱그린 문구 대신 그대로 보여준다.
        setState({
          status: 'error',
          result: null,
          error: estimation.error_message ?? '사진 측정에 실패했어요. 다시 시도해주세요.',
        });
        return;
      }
      const result = toResult(estimation);
      if (!result) {
        setState({
          status: 'error',
          result: null,
          error: estimation.error_message ?? UNREADABLE_RESULT,
        });
        return;
      }
      setState({ status: 'success', result });
    } catch (e) {
      setState({
        status: 'error',
        result: null,
        error:
          e instanceof ApiError
            ? e.message
            : '사진 측정에 실패했어요. 다시 시도해주세요.',
        // 업로드 400 도 기본 정보 부족이 원인일 수 있다 (서버가 저장된 값을 못 찾은 경우).
        needsBasicInfo: isMissingBasicInfo(e, state.input),
      });
    }
  },

  /** STEP3 에서 사용자가 직접 수정한 치수를 반영 (로컬만) */
  updateMeasures(measures: Measurement): void {
    if (!state.result) return;
    setState({ result: { ...state.result, measures } });
  },

  /**
   * STEP3 "완료" — 수정한 상세 7개를 서버에 저장(PATCH detail)한다.
   * Measurement 의 키가 백엔드 BODY_DETAIL_FIELDS 와 1:1 이라 그대로 보낸다.
   * 로컬 반영을 먼저 하므로 저장 실패해도 결과는 유지되고, 실패는 throw 로 알린다.
   */
  async saveDetail(measures: Measurement): Promise<void> {
    if (state.result) setState({ result: { ...state.result, measures } });
    await api.patch(BodyEndpoints.detail, measures);
  },
};

export function useMeasure(): MeasureState {
  return useSyncExternalStore(
    measureStore.subscribe,
    measureStore.getState,
    measureStore.getState,
  );
}
