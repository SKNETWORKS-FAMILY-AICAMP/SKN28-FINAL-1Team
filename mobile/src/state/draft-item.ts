import { useSyncExternalStore } from 'react';

/** 아이템 등록 화면과 가져오기 화면 사이의 사진 1장 임시 저장소. */
let photo: string | null = null;
const listeners = new Set<() => void>();

export const draftItem = {
  getPhoto: () => photo,
  setPhoto(next: string | null) {
    photo = next;
    listeners.forEach((listener) => listener());
  },
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useDraftPhoto() {
  return useSyncExternalStore(draftItem.subscribe, draftItem.getPhoto, draftItem.getPhoto);
}
