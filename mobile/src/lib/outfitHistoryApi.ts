import { OutfitHistoryEndpoints } from '@/constants/config';
import { api } from '@/lib/apiClient';

/**
 * 착장 분석 기록 API — 전송만 담당한다(상태는 화면/스토어).
 * 필드명은 백엔드 OutfitAnalysis* 시리얼라이저를 그대로 따른다(변환하지 않는다 —
 * 이름을 바꿔 두면 백엔드 스키마가 바뀔 때 어디를 고쳐야 하는지 흐려진다).
 */

/** 분석 상태. 목록·단건 모두 같은 값을 쓴다. */
export type OutfitAnalysisStatus = 'QUEUED' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED';

/** 질의에 사용한 날씨 스냅샷. 분석 시점의 값이라 지금 날씨와 다를 수 있다. */
export type AnalysisWeather = {
  region?: string;
  temperature?: number;
  sky_state?: string;
  is_stale?: boolean;
  observed_at?: string;
};

/**
 * 목록 한 줄. 사진은 들어있지 않다 —
 * 백엔드 목록 시리얼라이저에 image 계열 필드가 없고, 단건 조회도 축소 응답이라
 * 어느 경로로도 사진 URL을 받지 못한다. 썸네일이 필요하면 백엔드에 요청해야 한다.
 */
export type OutfitAnalysisListItem = {
  id: string;
  status: OutfitAnalysisStatus;
  /** 미완료 건은 null */
  overall_score: number | null;
  /** 미완료 건은 빈 문자열 */
  summary: string;
  weather: AnalysisWeather;
  personalized: boolean;
  created_at: string;
};

export type OutfitAnalysisListResponse = {
  count: number;
  limit: number;
  offset: number;
  results: OutfitAnalysisListItem[];
};

export type OutfitEvaluation = {
  overall_score: number;
  summary: string;
  strengths: string[];
  weather_comment: string;
  personalization_comment: string;
  styling_tips: string[];
};

/** 단건 조회(축소 응답). 진행 중 폴링과 완료 결과 조회가 같은 모양이다. */
export type OutfitAnalysisDetail = {
  analysis_id: string;
  status: OutfitAnalysisStatus;
  /** 완료 전에는 null */
  evaluation: OutfitEvaluation | null;
  context: {
    weather: AnalysisWeather;
    personalized: boolean;
    used_pursuit: boolean;
    used_body: boolean;
  } | null;
  /** 진행 중일 때만 값이 있다 */
  poll_after_ms: number | null;
  /** FAILED 일 때만 사용자용 문구가 들어온다 */
  detail: string | null;
  created_at: string;
  finished_at: string | null;
};

/** 백엔드 DEFAULT_HISTORY_LIMIT 과 같은 값. 넘기지 않으면 서버도 이 값을 쓴다. */
export const HISTORY_PAGE_SIZE = 20;
/** 백엔드 MAX_HISTORY_LIMIT. 더 크게 보내도 서버가 잘라낸다. */
export const HISTORY_MAX_LIMIT = 100;

export type OutfitHistoryQuery = {
  limit?: number;
  offset?: number;
  status?: OutfitAnalysisStatus;
};

/**
 * 내 분석 기록 목록. **JWT 필수** — 비회원에게는 보여줄 목록이 없다.
 * 최신순(`-created_at`)은 백엔드 모델 Meta.ordering 이 보장한다.
 */
export function listOutfitAnalyses(
  query: OutfitHistoryQuery = {},
): Promise<OutfitAnalysisListResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(Math.min(query.limit ?? HISTORY_PAGE_SIZE, HISTORY_MAX_LIMIT)));
  if (query.offset) params.set('offset', String(query.offset));
  if (query.status) params.set('status', query.status);
  return api.get<OutfitAnalysisListResponse>(`${OutfitHistoryEndpoints.list}?${params}`);
}

/**
 * 단건 조회. 토큰이 없어도 UUID만 맞으면 24시간 안에는 열린다.
 * 없거나·남의 것이거나·기간이 지났으면 전부 404 로 온다(존재 여부를 흘리지 않으려는 백엔드 설계).
 */
export function getOutfitAnalysis(analysisId: string): Promise<OutfitAnalysisDetail> {
  return api.get<OutfitAnalysisDetail>(OutfitHistoryEndpoints.detail(analysisId));
}

export type ClaimSkipReason = 'invalid' | 'expired' | 'not_found' | 'already_owned' | string;

export type OutfitAnalysisClaimResponse = {
  claimed: string[];
  skipped: { analysis_id: string | null; reason: ClaimSkipReason }[];
};

/** 한 번에 넘길 수 있는 토큰 수(백엔드 OUTFIT_CLAIM_MAX_ITEMS). 넘기면 400 이다. */
export const CLAIM_MAX_ITEMS = 20;

/**
 * 비로그인으로 접수했던 분석을 계정으로 가져온다. **로그인 직후 한 번** 부른다.
 * 평가를 다시 하지는 않고 주인만 바꾼다 — 비회원 때 결과라 개인화는 반영돼 있지 않다.
 *
 * ⚠️ claim 토큰은 발급 후 60분만 유효하다(조회 24시간과 다르다). 그 사이에 로그인하지 않으면
 *    기록은 조회는 되어도 계정으로 넘어오지 못한다.
 */
export function claimOutfitAnalyses(claimTokens: string[]): Promise<OutfitAnalysisClaimResponse> {
  return api.post<OutfitAnalysisClaimResponse>(OutfitHistoryEndpoints.claim, {
    claim_tokens: claimTokens.slice(0, CLAIM_MAX_ITEMS),
  });
}
