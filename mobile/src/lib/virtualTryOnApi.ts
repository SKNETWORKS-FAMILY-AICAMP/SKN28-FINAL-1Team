import { Platform } from 'react-native';

import { API_BASE_URL, DailyLookVirtualTryOnEndpoint } from '@/constants/config';
import { ApiError, apiFetch } from '@/lib/apiClient';
import { getAccessToken } from '@/lib/secureStore';
import { guessFileName, guessMimeType, uploadMultipart } from '@/lib/uploadFile';

export type VirtualTryOnResult = {
  mode: 'person' | 'mannequin';
  image_url: string;
  cache_hit: boolean;
};

/**
 * 오늘의 룩을 내 체형 마네킹에 입힌다.
 *
 * `goldenId` 는 '다른 룩'으로 돌려보던 후보를 입어볼 때 준다. 생략하면 서버가
 * 대표 룩을 쓰므로, 화면이 후보를 보여주고 있다면 **반드시 넘겨야** 한다 —
 * 안 넘기면 화면에서 고른 룩과 마네킹이 입은 룩이 달라진다.
 * 서버는 이 값이 그 사용자의 오늘 후보 안에 있는지 확인한다(아니면 404).
 */
export async function fitDailyLookToMannequin(
  lookId: string,
  personUri: string,
  goldenId?: string,
): Promise<VirtualTryOnResult> {
  const form = new FormData();
  const name = guessFileName(personUri, 'person.jpg');

  if (Platform.OS === 'web') {
    const response = await fetch(personUri);
    if (!response.ok) throw new Error('선택한 사진을 불러오지 못했습니다.');
    form.append('person_image', await response.blob(), name);
    form.append('mode', 'mannequin');
    if (goldenId) form.append('golden_id', goldenId);
    return apiFetch<VirtualTryOnResult>(DailyLookVirtualTryOnEndpoint(lookId), {
      method: 'POST',
      body: form,
    });
  }

  form.append(
    'person_image',
    { uri: personUri, name, type: guessMimeType(name) } as unknown as Blob,
  );
  form.append('mode', 'mannequin');
  if (goldenId) form.append('golden_id', goldenId);
  const response = await uploadMultipart(
    `${API_BASE_URL}${DailyLookVirtualTryOnEndpoint(lookId)}`,
    form,
    { token: await getAccessToken(), timeoutMs: 10 * 60 * 1000 },
  );
  let body: unknown = null;
  try {
    body = response.body ? JSON.parse(response.body) : null;
  } catch {
    body = response.body;
  }
  if (response.status < 200 || response.status >= 300) {
    const detail = (body as { detail?: string } | null)?.detail;
    throw new ApiError(detail ?? `가상 착장 요청 실패 (${response.status})`, response.status, body);
  }
  return body as VirtualTryOnResult;
}
