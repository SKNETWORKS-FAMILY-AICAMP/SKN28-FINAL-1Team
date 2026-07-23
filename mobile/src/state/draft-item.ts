import { useSyncExternalStore } from 'react';

/**
 * 아이템 등록(D2) 화면과 무신사 WebView(import) 사이에서
 * "가져온 사진 URL"을 주고받기 위한 초경량 스토어.
 * (모달에서 뒤로 돌아올 때 값을 전달할 방법으로 사용)
 */
let photo: string | null = null;
const listeners = new Set<() => void>();

export const draftItem = {
  getPhoto: () => photo,
  setPhoto(next: string | null) {
    photo = next;
    listeners.forEach((l) => l());
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

/** D2 화면에서 현재 가져온 사진을 구독 */
export function useDraftPhoto() {
  return useSyncExternalStore(draftItem.subscribe, draftItem.getPhoto, draftItem.getPhoto);
}
