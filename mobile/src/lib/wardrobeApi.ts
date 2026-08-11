import { UploadType } from 'expo-file-system';
import { Platform } from 'react-native';

import { API_BASE_URL, WardrobeEndpoints } from '@/constants/config';
import { api, apiFetch, ApiError } from '@/lib/apiClient';
import { getImageSource } from '@/lib/resolveImageUri';
import { guessFileName, guessMimeType, isRemote, toLocalFile } from '@/lib/uploadFile';
import { getAccessToken } from '@/lib/secureStore';

/**
 * 옷장 API 호출 — 전송만 담당한다(상태·폴링은 hooks/use-wardrobe.ts).
 * 필드명은 백엔드 WardrobeItemSerializer 를 그대로 따른다(변환하지 않는다 —
 * 이름을 바꿔 두면 백엔드 스키마가 바뀔 때 어디를 고쳐야 하는지 흐려진다).
 */

/** 서버가 주는 옷장 아이템 1벌. */
export type WardrobeApiItem = {
  id: string;
  job: string | null;
  s3_key: string;
  /** presigned GET URL — 만료가 있으므로 오래 캐시하지 말 것 */
  image_url: string;
  item_name: string;
  category_large: string;
  category_small: string;
  season: string[];
  style: string[];
  color: string;
  pattern: string;
  fit: string;
  material: string;
  sleeve: string;
  length: string;
  usage: string[];
  layer_role: string;
  layer_order: number | null;
  /** 세그멘테이션 메타(raw_label·score·bbox 등) — 화면에 쓰지 않지만 디버깅에 도움 */
  seg_meta: Record<string, unknown>;
  /** false = 사용자 확인 대기. 추천 검색에서 제외된다. */
  confirmed: boolean;
  created_at: string;
};

export type UploadJobStatus = 'PENDING' | 'PROCESSING' | 'DONE' | 'FAILED';

export type UploadJob = {
  id: string;
  status: UploadJobStatus;
  error_message: string;
  created_at: string;
  finished_at: string | null;
  /** DONE 이면 이 사진에서 나온 아이템들. 1장에서 여러 벌이 나올 수 있다. */
  items: WardrobeApiItem[];
};

/** PATCH 로 보낼 수 있는 필드 (WardrobeItemUpdateSerializer 와 일치) */
export type WardrobeItemPatch = Partial<{
  item_name: string;
  category_large: string;
  category_small: string;
  season: string[];
  style: string[];
  color: string;
  pattern: string;
  fit: string;
  material: string;
  sleeve: string;
  length: string;
  usage: string[];
  layer_role: string;
  layer_order: number | null;
  confirmed: boolean;
}>;

export type WardrobeItemQuery = {
  category_large?: string;
  /** 확인 대기(false)만, 또는 확정(true)만 */
  confirmed?: boolean;
};

/**
 * 사진 1장 업로드 → 처리 job 접수(202). 아이템은 아직 없다.
 *
 * ⚠️ 네이티브에서 `FormData.append('image', { uri, name, type })`(예전 RN 관용구)를 쓰면
 * `Unsupported FormDataPart implementation` 으로 실패한다 — Expo SDK 54+ 의 전역 fetch 가
 * 표준(WinterCG) 구현이라 uri 객체 파트를 받지 않고 Blob/File 만 받기 때문이다.
 * 그래서 네이티브는 expo-file-system 의 네이티브 멀티파트 업로드를 쓴다.
 */
export async function uploadWardrobePhoto(
  uri: string,
  opts: { name?: string; mimeType?: string } = {},
): Promise<{ job_id: string; status: UploadJobStatus }> {
  const name = opts.name ?? guessFileName(uri, 'wardrobe.jpg');
  const type = opts.mimeType ?? guessMimeType(name);

  if (Platform.OS === 'web') {
    /* 남의 도메인 이미지는 CORS 때문에 그대로 fetch 하면 막힌다 —
       화면에서 쓰는 것과 같은 프록시를 태워 받아온다. */
    const source = isRemote(uri) ? (getImageSource(uri)?.uri ?? uri) : uri;
    const blob = await fetch(source).then((r) => r.blob());
    const form = new FormData();
    form.append('image', blob, name);
    return apiFetch<{ job_id: string; status: UploadJobStatus }>(WardrobeEndpoints.uploads, {
      method: 'POST',
      body: form,
    });
  }

  /* 네이티브 경로는 apiClient 를 타지 않으므로 인증 헤더를 직접 붙인다. */
  const token = await getAccessToken();
  const { file, downloaded } = await toLocalFile(uri, name);
  try {
    const res = await file.upload(`${API_BASE_URL}${WardrobeEndpoints.uploads}`, {
      httpMethod: 'POST',
      uploadType: UploadType.MULTIPART,
      fieldName: 'image',
      mimeType: type,
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    return parseUploadResponse(res);
  } finally {
    // 내려받은 임시 파일만 지운다. 사용자가 고른 사진은 우리 것이 아니다.
    if (downloaded) {
      try {
        file.delete();
      } catch {
        // 캐시 정리 실패는 업로드 성패와 무관하다 — 조용히 넘어간다.
      }
    }
  }
}

function parseUploadResponse(res: {
  status: number;
  body?: string;
}): { job_id: string; status: UploadJobStatus } {
  let data: unknown = null;
  try {
    data = res.body ? JSON.parse(res.body) : null;
  } catch {
    data = res.body;
  }

  if (res.status < 200 || res.status >= 300) {
    const detail = (data as { detail?: string } | null)?.detail;
    throw new ApiError(detail ?? `업로드 실패 (${res.status})`, res.status, data);
  }

  return data as { job_id: string; status: UploadJobStatus };
}

/** 처리 상태 조회 — DONE 이 되면 items 가 채워진다. */
export function getUploadJob(jobId: string): Promise<UploadJob> {
  return api.get<UploadJob>(WardrobeEndpoints.uploadJob(jobId));
}

/* ── 일괄 등록(batch) — 인앱 브라우저에서 긁어온 외부 상품 ────────────────
   사진을 올리는 대신 **이미지 주소**를 넘긴다. 이미지는 서버가 받아 S3 에 저장하고
   Qwen VL 태깅 워커를 태운다. 자세한 계약은 constants/config.ts 의 WardrobeEndpoints 주석. */

/** 백엔드 WARDROBE_BATCH_MAX_ITEMS 기본값. 넘겨 보내면 요청 전체가 400 이다. */
export const WARDROBE_BATCH_MAX_ITEMS = 30;

/** URLField(max_length=2048) — 더 긴 주소는 400 을 부른다. */
export const WARDROBE_BATCH_MAX_LINK_LENGTH = 2048;

/** CharField(max_length=120) */
export const WARDROBE_BATCH_MAX_NAME_LENGTH = 120;

/**
 * 일괄 등록에 넣는 상품 1건.
 * image_link 만 필수고, 나머지는 **아는 것만** 넣는다 — 비워 둔 자리는 서버 모델이 채운다.
 * 값이 taxonomy 와 어긋나면 배치 전체가 400 이므로 추측으로 채우지 말 것.
 */
export type WardrobeBatchItemInput = {
  image_link: string;
  item_name?: string;
  category_large?: string;
  category_small?: string;
  season?: string[];
  style?: string[];
  color?: string;
  pattern?: string;
  fit?: string;
  material?: string;
  sleeve?: string;
  length?: string;
  usage?: string[];
  layer_role?: string;
  layer_order?: number | null;
  confirmed?: boolean;
};

/** PARTIAL = 일부만 성공. DONE/PARTIAL/FAILED 가 종료 상태다. */
export type WardrobeBatchStatus = 'PENDING' | 'PROCESSING' | 'DONE' | 'PARTIAL' | 'FAILED';

/** 배치 안의 job 1개 = 이미지 1장. 단건 업로드 job 에 원본 파일명이 붙은 형태. */
export type WardrobeBatchJob = UploadJob & {
  job_id: string;
  /** 이미지 주소에서 뽑은 원본 파일명 — 처리 중에는 이것 말고 보여줄 게 없다 */
  file_name: string;
};

/** POST 응답(202). 접수 결과일 뿐 아직 아이템은 없다. */
export type WardrobeBatchCreated = {
  batch_id: string;
  status: WardrobeBatchStatus;
  total_count: number;
  accepted: { job_id: string; image_link: string }[];
  /** 이미지를 못 받았거나 큐 적재에 실패한 건. reason: image_fetch_failed | upload_failed | enqueue_failed */
  rejected: { image_link: string; reason: string }[];
  poll_url: string;
  poll_after_ms: number;
  estimated_seconds: number;
};

export type WardrobeBatch = {
  batch_id: string;
  status: WardrobeBatchStatus;
  source: string;
  counts: { total: number; pending: number; done: number; failed: number };
  /** 0~1 */
  progress: number;
  /** null 이면 더 물어볼 필요 없다(종료) */
  poll_after_ms: number | null;
  created_at: string;
  finished_at: string | null;
  jobs: WardrobeBatchJob[];
};

/**
 * 상품 여러 건을 한 번에 접수(202).
 *
 * source 는 등록 경로 꼬리표다(백엔드 정규식 `^[a-z][a-z0-9_-]{0,19}$`).
 * 나중에 "어디서 들어온 옷인지"를 세는 데 쓰이므로 화면마다 다른 값을 넣지 말 것.
 */
export function createWardrobeBatch(
  items: WardrobeBatchItemInput[],
  source = 'in_app_browser',
): Promise<WardrobeBatchCreated> {
  return api.post<WardrobeBatchCreated>(WardrobeEndpoints.batches, { source, items });
}

/** 배치 진행 상태. 종료되면 poll_after_ms 가 null 로 온다. */
export function getWardrobeBatch(batchId: string): Promise<WardrobeBatch> {
  return api.get<WardrobeBatch>(WardrobeEndpoints.batch(batchId));
}

export function listWardrobeItems(query: WardrobeItemQuery = {}): Promise<WardrobeApiItem[]> {
  const params = new URLSearchParams();
  if (query.category_large) params.set('category_large', query.category_large);
  if (query.confirmed !== undefined) params.set('confirmed', String(query.confirmed));
  const qs = params.toString();
  return api.get<WardrobeApiItem[]>(
    qs ? `${WardrobeEndpoints.items}?${qs}` : WardrobeEndpoints.items,
  );
}

/* 백엔드가 단건 조회(GET items/{id}/)를 아직 구현하지 않았다 — allow 는 PATCH·DELETE 뿐이라
   405 가 온다. 한 번 405 를 보면 그 뒤로는 바로 목록에서 찾는다(불필요한 왕복 제거).
   백엔드에 GET 이 생기면 이 플래그가 계속 false 로 남아 원래 경로를 쓴다. */
let detailGetUnsupported = false;

async function findItemInList(itemId: string): Promise<WardrobeApiItem> {
  const found = (await listWardrobeItems()).find((i) => i.id === itemId);
  if (!found) throw new ApiError('아이템을 찾을 수 없어요', 404, null);
  return found;
}

export async function getWardrobeItem(itemId: string): Promise<WardrobeApiItem> {
  if (detailGetUnsupported) return findItemInList(itemId);
  try {
    return await api.get<WardrobeApiItem>(WardrobeEndpoints.item(itemId));
  } catch (e) {
    if (e instanceof ApiError && e.status === 405) {
      detailGetUnsupported = true;
      return findItemInList(itemId);
    }
    throw e;
  }
}

/** 태그 수정. confirmed:true 를 함께 보내면 확정까지 한 번에 된다. */
export function patchWardrobeItem(
  itemId: string,
  patch: WardrobeItemPatch,
): Promise<WardrobeApiItem> {
  return api.patch<WardrobeApiItem>(WardrobeEndpoints.item(itemId), patch);
}

export function deleteWardrobeItem(itemId: string): Promise<unknown> {
  return api.delete(WardrobeEndpoints.item(itemId));
}

/** 아이템을 화면에 보여줄 이름 — 서버가 이름을 비워 보낼 수 있다(캡셔닝 실패 등). */
export function itemDisplayName(item: WardrobeApiItem): string {
  return item.item_name || item.category_small || item.category_large;
}

/* ── 파일 이름·형식 추정 ─────────────────────────────────
   백엔드가 확장자·content-type 으로 형식을 거르므로(jpeg/png/webp/heic) 최소한은 맞춰 보낸다. */

