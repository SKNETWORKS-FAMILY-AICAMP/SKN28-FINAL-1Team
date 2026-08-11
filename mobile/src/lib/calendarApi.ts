import { UploadType } from 'expo-file-system';
import { Platform } from 'react-native';

import { API_BASE_URL, CalendarEndpoints } from '@/constants/config';
import { api, apiFetch, ApiError } from '@/lib/apiClient';
import { getAccessToken } from '@/lib/secureStore';
import { toLocalFile, guessFileName, guessMimeType } from '@/lib/uploadFile';

/** 사진 등록은 옷 추출이 끝나야 COMPLETED 가 된다. 옷만 고른 기록은 처음부터 COMPLETED. */
export type CalendarStatus = 'REGISTERED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export type CalendarSourceType = 'PHOTO_UPLOAD' | 'WARDROBE_SELECTED';

export type CalendarProcessingErrorCode =
  | 'QUEUE_ENQUEUE_FAILED'
  | 'NO_ITEM_EXTRACTED'
  | 'IMAGE_PROCESSING_FAILED'
  | (string & {});

/** 기록에 딸린 옷 한 벌. `snapshot` 은 등록 시점의 옷장 아이템을 그대로 굳혀둔 것이다. */
export type CalendarWardrobeItem = {
  link_id: string;
  wardrobe_item_id: string;
  image_url: string;
  sort_order: number;
  snapshot: {
    s3_key?: string;
    item_name?: string;
    category_large?: string;
    category_small?: string;
    color?: string;
    [key: string]: unknown;
  };
};

export type CalendarEntryDto = {
  id: string;
  /** 'YYYY-MM-DD' */
  date: string;
  source_type: CalendarSourceType;
  image_s3_key: string;
  /** presigned URL. 사진 없이 옷만 고른 기록이면 빈 문자열이다. */
  image_url: string;
  /** 그날의 일정 메모. 프론트의 `note` 에 해당한다. */
  schedule: string;
  tpo: string[];
  weather_snapshot: Record<string, unknown> | null;
  hashtags: string[];
  status: CalendarStatus;
  wardrobe_items: CalendarWardrobeItem[];
  created_at: string;
  updated_at: string;
};

export type CalendarProcessingStatus = {
  calendar_id: string;
  status: CalendarStatus;
  /** 사진 등록이 아니면 false — 폴링할 필요가 없다. */
  processing_required: boolean;
  is_terminal: boolean;
  result_available: boolean;
  item_counts: { total: number; extracted: number; failed: number };
  failure: { code: CalendarProcessingErrorCode; message: string } | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  updated_at: string;
};

/** 등록·수정에 함께 보내는 메타데이터. 서버가 받는 건 이 셋뿐이다. */
export type CalendarMetadata = {
  schedule?: string;
  tpo?: string[];
  hashtags?: string[];
};

/** 기간 조회 — 월 그리드가 쓴다. 응답은 배열 그대로다(페이지네이션 없음). */
export function listCalendarEntries(startDate: string, endDate: string): Promise<CalendarEntryDto[]> {
  const query = new URLSearchParams({ start_date: startDate, end_date: endDate });
  return api.get<CalendarEntryDto[]>(`${CalendarEndpoints.list}?${query}`);
}

/**
 * 특정 날짜의 기록. **기록이 없으면 서버가 404 를 준다** — 그건 오류가 아니라
 * "그날은 비어 있다"는 뜻이라 null 로 바꿔 돌려준다.
 */
export async function getCalendarEntryByDate(date: string): Promise<CalendarEntryDto | null> {
  try {
    const query = new URLSearchParams({ date });
    return await api.get<CalendarEntryDto>(`${CalendarEndpoints.byDate}?${query}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function getCalendarEntry(calendarId: string): Promise<CalendarEntryDto> {
  return api.get<CalendarEntryDto>(CalendarEndpoints.detail(calendarId));
}

export function getCalendarProcessingStatus(calendarId: string): Promise<CalendarProcessingStatus> {
  return api.get<CalendarProcessingStatus>(CalendarEndpoints.processingStatus(calendarId));
}

/**
 * 옷장 아이템만 골라 등록 — 사진이 없는 기록. 즉시 완료되므로 폴링이 필요 없다.
 * `wardrobeItemIds` 는 비울 수 없다(서버가 400).
 */
export function createCalendarFromWardrobe(input: {
  date: string;
  wardrobeItemIds: string[];
} & CalendarMetadata): Promise<CalendarEntryDto> {
  return api.post<CalendarEntryDto>(CalendarEndpoints.wardrobe, {
    date: input.date,
    wardrobe_item_ids: input.wardrobeItemIds,
    schedule: input.schedule ?? '',
    tpo: input.tpo ?? [],
    hashtags: input.hashtags ?? [],
  });
}

/**
 * 사진으로 등록. 옷장 아이템을 함께 걸 수 있다(사진에서 못 뽑는 옷을 직접 지정하는 용도).
 *
 * 응답은 202 이고 `status` 가 REGISTERED/PROCESSING 이다 — 옷 추출이 끝나야 목록이 채워지므로
 * `getCalendarProcessingStatus` 로 지켜봐야 한다.
 */
export async function createCalendarFromPhoto(input: {
  date: string;
  photoUri: string;
  wardrobeItemIds?: string[];
  name?: string;
  mimeType?: string;
} & CalendarMetadata): Promise<CalendarEntryDto> {
  const name = input.name ?? guessFileName(input.photoUri);
  const mimeType = input.mimeType ?? guessMimeType(name);
  const fields = photoFields(input);

  if (Platform.OS === 'web') {
    const blob = await fetch(input.photoUri).then((response) => {
      if (!response.ok) throw new Error('선택한 사진을 불러오지 못했어요.');
      return response.blob();
    });
    const form = new FormData();
    form.append('image', blob, name);
    for (const [key, value] of Object.entries(fields)) form.append(key, value);
    return apiFetch<CalendarEntryDto>(CalendarEndpoints.photo, { method: 'POST', body: form });
  }

  /* 네이티브 업로드는 apiClient 를 타지 않으므로 인증 헤더를 직접 붙인다.
     (옷장 업로드와 같은 경로 — iOS 는 foreground 세션이어야 실패하지 않는다) */
  const token = await getAccessToken();
  const { file, downloaded } = await toLocalFile(input.photoUri, name);
  try {
    const response = await withUploadTimeout(
      file.upload(`${API_BASE_URL}${CalendarEndpoints.photo}`, {
        httpMethod: 'POST',
        uploadType: UploadType.MULTIPART,
        fieldName: 'image',
        mimeType,
        parameters: fields,
        headers: {
          Accept: 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        /* iOS 기본값은 백그라운드 URLSession 이라 앱이 응답을 못 받고 조용히 멈춘다 —
           오류도 안 나서 화면에서는 "아무 일도 안 일어남"으로 보인다. */
        sessionType: 'foreground',
      }),
    );
    return parseUploadResponse<CalendarEntryDto>(response);
  } finally {
    // 내려받은 임시 파일만 지운다. 사용자가 고른 사진은 우리 것이 아니다.
    if (downloaded) {
      try {
        file.delete();
      } catch {
        // 캐시 파일이라 못 지워도 그냥 둔다.
      }
    }
  }
}

/** 일정·TPO·해시태그만 고친다. 사진과 옷 구성은 PATCH 로 못 바꾼다(삭제 후 재등록). */
export function patchCalendarEntry(
  calendarId: string,
  patch: CalendarMetadata,
): Promise<CalendarEntryDto> {
  return api.patch<CalendarEntryDto>(CalendarEndpoints.detail(calendarId), patch);
}

/** 처리 중인 기록은 서버가 409 로 막는다. */
export function deleteCalendarEntry(calendarId: string): Promise<unknown> {
  return api.delete(CalendarEndpoints.detail(calendarId));
}

/**
 * multipart 는 값이 전부 문자열이라 배열을 그대로 못 싣는다.
 * `expo-file-system` 의 parameters 도 Record<string, string> 이라 같은 키를 반복할 수 없어,
 * DRF 가 HTML 폼 입력에서 인식하는 `필드[인덱스]` 표기로 편다.
 */
function photoFields(input: {
  date: string;
  wardrobeItemIds?: string[];
} & CalendarMetadata): Record<string, string> {
  const fields: Record<string, string> = {
    date: input.date,
    schedule: input.schedule ?? '',
  };
  appendList(fields, 'wardrobe_item_ids', input.wardrobeItemIds);
  appendList(fields, 'tpo', input.tpo);
  appendList(fields, 'hashtags', input.hashtags);
  return fields;
}

function appendList(fields: Record<string, string>, key: string, values?: string[]) {
  values?.forEach((value, index) => {
    fields[`${key}[${index}]`] = value;
  });
}

/** 업로드 상한. 없으면 응답이 안 올 때 화면이 영영 "저장 중"으로 남는다. */
const UPLOAD_TIMEOUT_MS = 60_000;

function withUploadTimeout<T>(request: Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('사진 저장이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요.'));
    }, UPLOAD_TIMEOUT_MS);
    request.then(resolve, reject).finally(() => clearTimeout(timer));
  });
}

function parseUploadResponse<T>(response: { status: number; body?: string }): T {
  let data: unknown = null;
  try {
    data = response.body ? JSON.parse(response.body) : null;
  } catch {
    data = response.body;
  }

  if (response.status < 200 || response.status >= 300) {
    throw new ApiError(uploadErrorMessage(data, response.status), response.status, data);
  }

  return data as T;
}

/**
 * DRF 검증 오류는 `{ "필드": ["설명"] }` 로 온다 — `detail` 만 보면 원인이 통째로 사라진다.
 * 어느 필드가 왜 거절됐는지가 고칠 단서라 그대로 꺼내 보여준다.
 */
function uploadErrorMessage(data: unknown, status: number): string {
  const fallback = `캘린더 기록 저장에 실패했어요. (${status})`;
  if (!data || typeof data !== 'object') return fallback;

  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;

  const messages = Object.entries(data as Record<string, unknown>)
    .map(([field, value]) => {
      const text = Array.isArray(value) ? value.join(' ') : String(value);
      return `${field}: ${text}`;
    })
    .filter(Boolean);

  return messages.length > 0 ? messages.join('\n') : fallback;
}
