import { File, Paths } from 'expo-file-system';

import { getImageSource } from '@/lib/resolveImageUri';

/**
 * 네이티브 멀티파트 업로드에 공통으로 쓰는 파일 준비 유틸.
 * 옷장·캘린더가 같은 방식으로 사진을 올려서 한곳에 둔다.
 */

const MIME_BY_EXT: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  heic: 'image/heic',
};

export function isRemote(uri: string): boolean {
  return /^https?:/i.test(uri);
}

export function guessFileName(uri: string, fallback = 'upload.jpg'): string {
  const last = uri.split('?')[0].split('/').pop() ?? '';
  return /\.[a-zA-Z0-9]+$/.test(last) ? last : fallback;
}

export function guessMimeType(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return MIME_BY_EXT[ext] ?? 'image/jpeg';
}

/**
 * 업로드에 쓸 로컬 파일을 만든다.
 *
 * `File` 은 기기 안의 파일을 가리키는 것이라 `https://...` 주소를 그대로 넣으면 올라가지 않는다.
 * 룩의 구성 아이템이나 쇼핑몰에서 가져온 사진은 전부 원격 주소라, 캐시에 한 번 내려받아
 * 진짜 파일로 만든 뒤 올린다.
 *
 * `downloaded` 가 true 면 호출한 쪽이 업로드 후 지워야 한다.
 */
export async function toLocalFile(
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
