import { File, Paths, UploadType } from 'expo-file-system';
import { Platform } from 'react-native';

import { API_BASE_URL, WardrobeEndpoints } from '@/constants/config';
import { api, apiFetch, ApiError } from '@/lib/apiClient';
import { getImageSource } from '@/lib/resolveImageUri';
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
  const name = opts.name ?? guessFileName(uri);
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

function isRemote(uri: string): boolean {
  return /^https?:/i.test(uri);
}

/**
 * 업로드에 쓸 로컬 파일을 만든다.
 *
 * `File` 은 기기 안의 파일을 가리키는 것이라 `https://...` 주소를 그대로 넣으면 올라가지 않는다.
 * 룩의 구성 아이템이나 쇼핑몰에서 가져온 사진은 전부 원격 주소라, 캐시에 한 번 내려받아
 * 진짜 파일로 만든 뒤 올린다.
 */
async function toLocalFile(
  uri: string,
  name: string,
): Promise<{ file: File; downloaded: boolean }> {
  if (!isRemote(uri)) return { file: new File(uri), downloaded: false };

  /* 이름이 겹치면 내려받기가 실패하므로 매번 다른 이름을 쓴다.
     (핀터레스트처럼 핫링크를 막는 곳은 화면에서 쓰는 것과 같은 헤더를 붙여야 받아진다) */
  const dest = new File(Paths.cache, `upload-${Date.now()}-${name}`);
  const source = getImageSource(uri);
  const file = await File.downloadFileAsync(uri, dest, {
    headers: (source && 'headers' in source ? source.headers : undefined) as
      | Record<string, string>
      | undefined,
  });
  return { file, downloaded: true };
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

export function guessMimeType(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return MIME_BY_EXT[ext] ?? 'image/jpeg';
}

// ── 공유 옷장 (Shared Wardrobe) API ──
export type SharedRoom = {
  id: string;
  title: string;
  invite_code: string | null;
  code_expires_at: string | null;
  created_at: string;
  role?: 'owner' | 'member';
};

export type SharedRoomMember = {
  id: number;
  user: {
    id: number;
    username: string;
    email: string;
  };
  role: 'owner' | 'member';
  joined_at: string;
};

export type SharedRoomItem = {
  id: string;
  registered_by: {
    id: number;
    username: string;
    email: string;
  } | null;
  wardrobe_item: WardrobeApiItem;
  status: 'available' | 'borrowed' | 'private';
  created_at: string;
};

export function createSharedRoom(title: string): Promise<SharedRoom> {
  return api.post<SharedRoom>('/api/v1/shared-wardrobes/', { title });
}

export function renameSharedRoom(roomId: string, title: string): Promise<SharedRoom> {
  return api.patch<SharedRoom>(`/api/v1/shared-wardrobes/${roomId}/`, { title });
}

export function joinSharedRoom(inviteCode: string): Promise<{ room_id: string; title: string; status: string }> {
  return api.post<{ room_id: string; title: string; status: string }>('/api/v1/shared-wardrobes/join/', { invite_code: inviteCode });
}

export function refreshInviteCode(roomId: string): Promise<{ room_id: string; invite_code: string; code_expires_at: string }> {
  return api.post<{ room_id: string; invite_code: string; code_expires_at: string }>(`/api/v1/shared-wardrobes/${roomId}/refresh-code/`);
}

export function leaveSharedRoom(roomId: string, deleteMyItems: boolean = true): Promise<unknown> {
  return api.post(`/api/v1/shared-wardrobes/${roomId}/leave/`, { delete_my_items: deleteMyItems });
}

export function listSharedRoomItems(roomId: string): Promise<SharedRoomItem[]> {
  return api.get<SharedRoomItem[]>(`/api/v1/shared-wardrobes/${roomId}/items/`);
}

export function registerItemToSharedRoom(roomId: string, wardrobeItemId: string, status: 'available' | 'borrowed' | 'private' = 'available'): Promise<SharedRoomItem> {
  return api.post<SharedRoomItem>(`/api/v1/shared-wardrobes/${roomId}/items/`, {
    wardrobe_item_id: wardrobeItemId,
    status
  });
}

export function unregisterItemFromSharedRoom(roomId: string, wardrobeItemId: string): Promise<unknown> {
  return api.delete(`/api/v1/shared-wardrobes/${roomId}/items/`, {
    params: { wardrobe_item_id: wardrobeItemId },
  });
}

export function listSharedRoomMembers(roomId: string): Promise<SharedRoomMember[]> {
  return api.get<SharedRoomMember[]>(`/api/v1/shared-wardrobes/${roomId}/members/`);
}

export function getMySharedRooms(): Promise<SharedRoom[]> {
  return api.get<SharedRoom[]>('/api/v1/shared-wardrobes/');
}
