import { WardrobeEndpoints } from '@/constants/config';
import { api, apiFetch } from '@/lib/apiClient';

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

/** 사진 1장 업로드 → 처리 job 접수(202). 아이템은 아직 없다. */
export async function uploadWardrobePhoto(
  uri: string,
  opts: { name?: string; mimeType?: string } = {},
): Promise<{ job_id: string; status: UploadJobStatus }> {
  const name = opts.name ?? guessFileName(uri);
  const type = opts.mimeType ?? guessMimeType(name);

  const form = new FormData();
  /* React Native 의 FormData 는 { uri, name, type } 객체를 파일로 취급한다.
     웹에서는 Blob 이어야 하므로 uri 를 먼저 Blob 으로 읽는다. */
  if (uri.startsWith('data:') || uri.startsWith('blob:') || uri.startsWith('http')) {
    const blob = await fetch(uri).then((r) => r.blob());
    form.append('image', blob, name);
  } else {
    // @ts-expect-error RN 전용 파일 형태 — 웹 FormData 타입에는 없다
    form.append('image', { uri, name, type });
  }

  return apiFetch<{ job_id: string; status: UploadJobStatus }>(WardrobeEndpoints.uploads, {
    method: 'POST',
    body: form,
  });
}

/** 처리 상태 조회 — DONE 이 되면 items 가 채워진다. */
export function getUploadJob(jobId: string): Promise<UploadJob> {
  return api.get<UploadJob>(WardrobeEndpoints.uploadJob(jobId));
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

export function getWardrobeItem(itemId: string): Promise<WardrobeApiItem> {
  return api.get<WardrobeApiItem>(WardrobeEndpoints.item(itemId));
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

const MIME_BY_EXT: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  heic: 'image/heic',
};

function guessFileName(uri: string): string {
  const last = uri.split('?')[0].split('/').pop() ?? '';
  return /\.[a-zA-Z0-9]+$/.test(last) ? last : 'wardrobe.jpg';
}

function guessMimeType(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return MIME_BY_EXT[ext] ?? 'image/jpeg';
}
