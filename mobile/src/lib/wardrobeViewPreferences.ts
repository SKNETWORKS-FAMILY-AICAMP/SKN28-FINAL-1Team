import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import type { WardrobeGroupMode, WardrobeItemSort } from '@/lib/wardrobeSections';

const WEB_KEY = 'wardrobe:view-preferences:v1';
// SecureStore 키에는 콜론을 쓸 수 없어 네이티브에서만 같은 버전의 안전한 별칭을 사용한다.
const NATIVE_KEY = 'wardrobe.view-preferences.v1';

export type WardrobeViewPreferences = {
  group_mode: WardrobeGroupMode;
  item_sort: WardrobeItemSort;
};

export const DEFAULT_WARDROBE_VIEW_PREFERENCES: WardrobeViewPreferences = {
  group_mode: 'SYSTEM_CATEGORY',
  item_sort: 'ADDED_DESC',
};

function isPreferences(value: unknown): value is WardrobeViewPreferences {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<WardrobeViewPreferences>;
  return (
    (candidate.group_mode === 'SYSTEM_CATEGORY' || candidate.group_mode === 'CUSTOM_CATEGORY') &&
    (candidate.item_sort === 'ADDED_DESC' || candidate.item_sort === 'COLOR_NAME_ASC')
  );
}

export async function loadWardrobeViewPreferences(): Promise<WardrobeViewPreferences> {
  try {
    const raw =
      Platform.OS === 'web'
        ? localStorage.getItem(WEB_KEY)
        : await SecureStore.getItemAsync(NATIVE_KEY);
    if (!raw) return DEFAULT_WARDROBE_VIEW_PREFERENCES;
    const parsed: unknown = JSON.parse(raw);
    return isPreferences(parsed) ? parsed : DEFAULT_WARDROBE_VIEW_PREFERENCES;
  } catch {
    return DEFAULT_WARDROBE_VIEW_PREFERENCES;
  }
}

export async function saveWardrobeViewPreferences(
  preferences: WardrobeViewPreferences,
): Promise<void> {
  const value = JSON.stringify(preferences);
  try {
    if (Platform.OS === 'web') {
      localStorage.setItem(WEB_KEY, value);
    } else {
      await SecureStore.setItemAsync(NATIVE_KEY, value);
    }
  } catch {
    // 보기 설정 저장 실패가 옷장 탐색을 막아서는 안 된다.
  }
}
