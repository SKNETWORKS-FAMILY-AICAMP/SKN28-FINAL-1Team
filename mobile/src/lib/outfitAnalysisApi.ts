import { File, UploadType } from 'expo-file-system';
import { Platform } from 'react-native';

import { API_BASE_URL, OutfitAnalysisEndpoint } from '@/constants/config';
import { apiFetch, ApiError } from '@/lib/apiClient';
import { getAccessToken } from '@/lib/secureStore';

const ANALYSIS_TIMEOUT_MS = 60_000;

export type OutfitEvaluation = {
  overall_score: number;
  summary: string;
  strengths: string[];
  weather_comment: string;
  personalization_comment: string;
  styling_tips: string[];
};

export type OutfitAnalysisResponse = {
  status: 'completed';
  evaluation: OutfitEvaluation;
  context: {
    weather: unknown;
    personalized: boolean;
    used_pursuit: boolean;
    used_body: boolean;
  };
};

type AnalyzeOptions = {
  name?: string;
  mimeType?: string;
  lat?: number;
  lon?: number;
};

export async function analyzeOutfitPhoto(
  uri: string,
  options: AnalyzeOptions = {},
): Promise<OutfitAnalysisResponse> {
  if ((options.lat === undefined) !== (options.lon === undefined)) {
    throw new Error('위도와 경도는 함께 입력해야 합니다.');
  }

  const name = options.name ?? guessFileName(uri);
  const mimeType = options.mimeType ?? guessMimeType(name);

  if (Platform.OS === 'web') {
    const blob = await fetch(uri).then((response) => {
      if (!response.ok) throw new Error('선택한 사진을 불러오지 못했어요.');
      return response.blob();
    });
    const form = new FormData();
    form.append('image', blob, name);
    if (options.lat !== undefined && options.lon !== undefined) {
      form.append('lat', String(options.lat));
      form.append('lon', String(options.lon));
    }
    return withAnalysisTimeout(
      apiFetch<OutfitAnalysisResponse>(OutfitAnalysisEndpoint, {
        method: 'POST',
        body: form,
      }),
    );
  }

  const token = await getAccessToken();
  const file = new File(uri);
  const parameters =
    options.lat !== undefined && options.lon !== undefined
      ? { lat: String(options.lat), lon: String(options.lon) }
      : undefined;
  const response = await withAnalysisTimeout(
    file.upload(`${API_BASE_URL}${OutfitAnalysisEndpoint}`, {
      httpMethod: 'POST',
      uploadType: UploadType.MULTIPART,
      fieldName: 'image',
      mimeType,
      parameters,
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }),
  );

  return parseAnalysisResponse(response);
}

function withAnalysisTimeout<T>(request: Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('착장 분석 시간이 길어지고 있어요. 잠시 후 다시 시도해 주세요.'));
    }, ANALYSIS_TIMEOUT_MS);

    request.then(resolve, reject).finally(() => clearTimeout(timer));
  });
}

function parseAnalysisResponse(response: {
  status: number;
  body?: string;
}): OutfitAnalysisResponse {
  let data: unknown = null;
  try {
    data = response.body ? JSON.parse(response.body) : null;
  } catch {
    data = response.body;
  }

  if (response.status < 200 || response.status >= 300) {
    const detail = (data as { detail?: string } | null)?.detail;
    throw new ApiError(detail ?? `착장 분석에 실패했어요. (${response.status})`, response.status, data);
  }

  return data as OutfitAnalysisResponse;
}

const MIME_BY_EXTENSION: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
};

function guessFileName(uri: string): string {
  const lastSegment = uri.split('?')[0].split('/').pop() ?? '';
  return /\.[a-zA-Z0-9]+$/.test(lastSegment) ? lastSegment : 'outfit.jpg';
}

function guessMimeType(name: string): string {
  const extension = name.split('.').pop()?.toLowerCase() ?? '';
  return MIME_BY_EXTENSION[extension] ?? 'image/jpeg';
}
