import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

/**
 * 토큰 저장소.
 * - 네이티브(iOS/Android): expo-secure-store (Keychain/Keystore, 암호화 저장)
 * - 웹(EAS Hosting 체험용 빌드): SecureStore 미지원 → localStorage 로 폴백
 * - 키체인 접근 불가 시(예: 코드서명 없는 시뮬레이터 빌드): 메모리 폴백
 *   → 세션은 유지되지만 앱 재시작 시 사라진다. 서명된 실기기/개발빌드에선 키체인 정상 동작.
 *
 * SecureStore 키는 [A-Za-z0-9._-] 만 허용하므로 밑줄 표기를 쓴다.
 */
const ACCESS_KEY = 'auth_access_token';
const REFRESH_KEY = 'auth_refresh_token';

const isWeb = Platform.OS === 'web';

// 키체인 접근 실패 시 폴백용 (서명 정상 빌드에선 쓰이지 않음)
const memoryStore = new Map<string, string>();

async function setItem(key: string, value: string): Promise<void> {
  if (isWeb) {
    localStorage.setItem(key, value);
    return;
  }
  try {
    await SecureStore.setItemAsync(key, value);
  } catch (e) {
    console.warn('[secureStore] 키체인 저장 실패 → 메모리 폴백:', e);
    memoryStore.set(key, value);
  }
}

async function getItem(key: string): Promise<string | null> {
  if (isWeb) {
    return localStorage.getItem(key);
  }
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return memoryStore.get(key) ?? null;
  }
}

async function deleteItem(key: string): Promise<void> {
  if (isWeb) {
    localStorage.removeItem(key);
    return;
  }
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    // 키체인 접근 불가 시 무시 (메모리만 정리)
  }
  memoryStore.delete(key);
}

/** 로그인 성공 시: access + refresh 동시 저장 */
export async function saveTokens(access: string, refresh: string): Promise<void> {
  await Promise.all([setItem(ACCESS_KEY, access), setItem(REFRESH_KEY, refresh)]);
}

/** access 재발급 시: access 만 갱신 */
export async function saveAccessToken(access: string): Promise<void> {
  await setItem(ACCESS_KEY, access);
}

export function getAccessToken(): Promise<string | null> {
  return getItem(ACCESS_KEY);
}

export function getRefreshToken(): Promise<string | null> {
  return getItem(REFRESH_KEY);
}

/** 로그아웃/세션만료 시: 전부 삭제 */
export async function clearTokens(): Promise<void> {
  await Promise.all([deleteItem(ACCESS_KEY), deleteItem(REFRESH_KEY)]);
}
