import { RecommendEndpoints } from '@/constants/config';
import { api, ApiError } from '@/lib/apiClient';

/**
 * 추천 결과 조회.
 *
 * 채팅 답변이 추천까지 만들어 내면 그 답변 메시지의 metadata 에 recommendation_result_id 만
 * 들어온다. 실제 코디 구성(카드)은 여기서 따로 받아 온다 — 대화 API 는 대화만 다룬다.
 */

export type ApiRecommendationItem = {
  item_id: string;
  position: number;
  slot: string;
  /** WARDROBE = 내 옷장 옷, PRODUCT = 새로 살 상품 */
  source_type: string;
  display_name: string;
  category: string | null;
  color: string | null;
  /**
   * ⚠️ **바로 쓸 수 있는 주소가 아닐 수 있다.** 백엔드 주석이 "S3 키 또는 검증된 URL" 이라,
   *    옷장 아이템은 키가, 상품은 URL 이 들어오는 식으로 섞인다. imageUrlOf() 로 거른다.
   */
  image_ref: string;
  /** 옷장 아이템이면 null (살 필요가 없으므로 가격이 없다) */
  price_snapshot: number | null;
  purchase_url: string | null;
  reasons: string[];
};

/** 검증기가 남긴 한 줄. severity 는 INFO/WARNING 계열 문자열이다. */
export type ApiValidationReason = {
  severity: string;
  code: string;
  message: string;
  slot: string | null;
};

export type ApiRecommendationCard = {
  card_id: string;
  rank: number;
  /** 새로 사야 하는 상품들의 합. 옷장 옷만으로 짠 코디면 0 이다. */
  total_product_price: number | null;
  warnings: string[];
  items: ApiRecommendationItem[];
  validation_reasons: ApiValidationReason[];
  /** 아직 반응을 남기지 않았으면 null. 카드 목록·상세가 같은 모양으로 준다. */
  feedback: ApiCardFeedback | null;
};

export type ApiRecommendationResult = {
  result_id: string;
  session_id: string;
  run_id: string;
  mode: string;
  created_at: string;
  cards: ApiRecommendationCard[];
};

/**
 * 화면에 걸 수 있는 주소만 통과시킨다.
 * S3 키(예: "wardrobe/2026/ab12.jpg")를 그대로 <Image> 에 넘기면 조용히 깨진 자리만 남는다.
 */
export function imageUrlOf(imageRef: string | null | undefined): string | null {
  if (!imageRef) return null;
  return /^https?:\/\//.test(imageRef) ? imageRef : null;
}

export function getRecommendationResult(resultId: string): Promise<ApiRecommendationResult> {
  return api.get<ApiRecommendationResult>(RecommendEndpoints.result(resultId));
}

/** 카드 한 장. 목록에도 같은 모양이 들어 있지만, 상세는 항상 최신 피드백을 다시 받는다. */
export function getRecommendationCard(
  resultId: string,
  cardId: string,
): Promise<ApiRecommendationCard> {
  return api.get<ApiRecommendationCard>(RecommendEndpoints.card(resultId, cardId));
}

/* ── 피드백 ───────────────────────────────────────── */

export type ApiFeedbackReaction = 'LIKE' | 'DISLIKE';

export type ApiCardFeedback = {
  feedback_id: string;
  reaction: ApiFeedbackReaction;
  reason_codes: string[];
  comment: string;
  created_at: string;
  updated_at: string;
};

/**
 * 왜 별로였는지 고르는 코드. 서버는 대문자 코드면 무엇이든 받지만, 집계가 되려면
 * 값이 흔들리지 않아야 해서 앱이 쓰는 목록을 여기 고정한다.
 */
export const FEEDBACK_REASONS = [
  { code: 'STYLE', label: '스타일이 안 맞아요' },
  { code: 'COLOR', label: '색이 취향이 아니에요' },
  { code: 'FIT', label: '핏이 안 맞아요' },
  { code: 'PRICE', label: '너무 비싸요' },
  { code: 'ALREADY_OWNED', label: '이미 비슷한 옷이 있어요' },
] as const;

/**
 * 카드의 최신 반응을 통째로 교체한다(PUT). 사유를 바꾸려면 reaction 도 함께 보낸다.
 * 서버가 카드당 하나만 두므로 여러 번 보내도 마지막 것만 남는다.
 */
export function putCardFeedback(
  resultId: string,
  cardId: string,
  input: { reaction: ApiFeedbackReaction; reasonCodes?: string[]; comment?: string },
): Promise<ApiCardFeedback> {
  return api.put<ApiCardFeedback>(RecommendEndpoints.cardFeedback(resultId, cardId), {
    reaction: input.reaction,
    reason_codes: input.reasonCodes ?? [],
    comment: input.comment ?? '',
  });
}

/** 반응 취소. 카드 자체는 그대로 남는다. */
export function deleteCardFeedback(resultId: string, cardId: string): Promise<void> {
  return api.delete<void>(RecommendEndpoints.cardFeedback(resultId, cardId));
}

/* ── 코디 이미지 ───────────────────────────────────── */

export type ApiRenderStatus = 'QUEUED' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED';

export type ApiRenderJob = {
  job_id: string;
  card_id: string;
  status: ApiRenderStatus;
  cache_hit: boolean;
  /** 만료되는 presigned URL. SUCCEEDED 일 때만 채워진다. */
  image_url: string | null;
  error: { code: string; message: string } | null;
  created_at: string;
  updated_at: string;
};

export function isRenderTerminal(status: ApiRenderStatus): boolean {
  return status === 'SUCCEEDED' || status === 'FAILED';
}

/**
 * 이미지 생성 상태. **아직 작업이 없으면 null** 이다(서버는 404).
 * 추천이 저장될 때 서버가 미리 작업을 걸어두므로 보통은 여기서 결과가 나온다.
 */
export async function getCardRender(
  resultId: string,
  cardId: string,
): Promise<ApiRenderJob | null> {
  try {
    return await api.get<ApiRenderJob>(RecommendEndpoints.cardRender(resultId, cardId));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** 이미지 생성 접수. 이미 만들어 둔 같은 조합이 있으면 서버가 그대로 돌려준다. */
export function requestCardRender(
  resultId: string,
  cardId: string,
): Promise<ApiRenderJob> {
  return api.post<ApiRenderJob>(RecommendEndpoints.cardRender(resultId, cardId));
}
