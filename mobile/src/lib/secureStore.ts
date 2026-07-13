import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

/**
 * 토큰 저장소.
 * - 네이티브(iOS/Android): expo-secure-store (Keychain/Keystore, 암호화 저장)
 * - 웹(EAS Hosting 체험용 빌드): SecureStore 미지원 → localStorage 로 폴백
 *
 * SecureStore 키는 [A-Za-z0-9._-] 만 허용하므로 밑줄 표기를 쓴다.
 */
const ACCESS_KEY = 'auth_access_token';
const REFRESH_KEY = 'auth_refresh_token';

const isWeb = Platform.OS === 'web';

async function setItem(key: string, value: string): Promise<void> {
  if (isWeb) {
    localStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function getItem(key: string): Promise<string | null> {
  if (isWeb) {
    return localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

async function deleteItem(key: string): Promise<void> {
  if (isWeb) {
    localStorage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
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
