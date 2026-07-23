import { API_BASE_URL, AuthEndpoints } from '@/constants/config';
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  saveAccessToken,
} from '@/lib/secureStore';

/**
 * 앱 전역 HTTP 클라이언트.
 *  - base URL 자동 prepend
 *  - 로그인 상태면 Authorization: Bearer <access> 자동 부착
 *  - 401 이 오면 refresh 토큰으로 access 재발급 후 원요청 1회 재시도
 *  - 재발급까지 실패하면 토큰을 지우고 onUnauthorized 콜백을 호출(=세션 종료)
 *
 * 참고 프로젝트(SKN28-4th-4team)의 frontend/services/apiClient.js 인터셉터
 * 패턴을 React Native + SecureStore 환경으로 옮긴 것.
 */

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

// 세션 만료(재발급 실패) 시 호출. auth 스토어가 등록한다. (순환 import 회피용 콜백)
let onUnauthorizedCb: (() => void) | null = null;
export function onUnauthorized(cb: () => void): void {
  onUnauthorizedCb = cb;
}

type RequestOptions = Omit<RequestInit, 'body' | 'headers'> & {
  /** 객체면 JSON 으로 직렬화되어 전송된다 */
  body?: unknown;
  headers?: Record<string, string>;
  /** false 면 Authorization 헤더를 붙이지 않는다 (기본 true) */
  auth?: boolean;
  /** 내부용: 401 재시도 여부 (직접 넘기지 말 것) */
  _retried?: boolean;
};

async function parseBody(res: Response): Promise<unknown> {
  const type = res.headers.get('content-type') ?? '';
  if (type.includes('application/json')) {
    return res.json().catch(() => null);
  }
  const text = await res.text().catch(() => '');
  return text || null;
}

// 동시에 여러 요청이 401 을 받아도 refresh 는 한 번만 수행하도록 공유한다.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = await getRefreshToken();
  if (!refresh) return null;

  try {
    const res = await fetch(`${API_BASE_URL}${AuthEndpoints.refresh}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return null;

    const data = (await parseBody(res)) as { access?: string } | null;
    if (!data?.access) return null;

    await saveAccessToken(data.access);
    return data.access;
  } catch {
    return null;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, auth = true, headers, _retried, ...rest } = options;

  const token = auth ? await getAccessToken() : null;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // 401 → refresh 1회 시도 후 원요청 재시도
  if (res.status === 401 && auth && !_retried) {
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }
    const newAccess = await refreshPromise;

    if (newAccess) {
      return apiFetch<T>(path, { ...options, _retried: true });
    }

    // 재발급 실패 → 세션 종료
    await clearTokens();
    onUnauthorizedCb?.();
    throw new ApiError('세션이 만료되었습니다. 다시 로그인해 주세요.', 401, null);
  }

  const data = await parseBody(res);

  if (!res.ok) {
    const detail = (data as { detail?: string; message?: string } | null) ?? null;
    const message = detail?.detail ?? detail?.message ?? `요청 실패 (${res.status})`;
    throw new ApiError(message, res.status, data);
  }

  return data as T;
}

/** 자주 쓰는 메서드 단축 헬퍼 */
export const api = {
  get: <T = unknown>(path: string, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'GET' }),
  post: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'POST', body }),
  put: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'PUT', body }),
  patch: <T = unknown>(path: string, body?: unknown, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'PATCH', body }),
  delete: <T = unknown>(path: string, opts?: RequestOptions) =>
    apiFetch<T>(path, { ...opts, method: 'DELETE' }),
};
