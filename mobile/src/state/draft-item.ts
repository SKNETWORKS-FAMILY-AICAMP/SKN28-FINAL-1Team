import { useSyncExternalStore } from 'react';

/**
 * 아이템 등록(D2) 화면과 무신사 WebView(import) 사이에서
 * "가져온 사진 URL 리스트"를 주고받기 위한 초경량 스토어.
 */
let photos: string[] = [];
const listeners = new Set<() => void>();

export const draftItem = {
  getPhotos: () => photos,
  setPhotos(next: string[]) {
    photos = next.slice(0, 3);
    listeners.forEach((l) => l());
  },
  setPhoto(photo: string) {
    photos = [photo];
    listeners.forEach((l) => l());
  },
  addPhoto(photo: string) {
    if (photos.length < 3 && !photos.includes(photo)) {
      photos = [...photos, photo];
      listeners.forEach((l) => l());
    }
  },
  clear() {
    photos = [];
    listeners.forEach((l) => l());
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

/** D2 화면에서 현재 가져온 사진 리스트를 구독 */
export function useDraftPhotos() {
  return useSyncExternalStore(draftItem.subscribe, draftItem.getPhotos, draftItem.getPhotos);
}
