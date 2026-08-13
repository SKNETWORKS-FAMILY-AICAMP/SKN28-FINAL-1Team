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

export async function fitDailyLookToMannequin(
  lookId: string,
  personUri: string,
): Promise<VirtualTryOnResult> {
  const form = new FormData();
  const name = guessFileName(personUri, 'person.jpg');

  if (Platform.OS === 'web') {
    const response = await fetch(personUri);
    if (!response.ok) throw new Error('선택한 사진을 불러오지 못했습니다.');
    form.append('person_image', await response.blob(), name);
    form.append('mode', 'mannequin');
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
