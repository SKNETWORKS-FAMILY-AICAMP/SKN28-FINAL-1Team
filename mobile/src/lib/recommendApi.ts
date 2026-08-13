import { RecommendEndpoints } from '@/constants/config';
import { api } from '@/lib/apiClient';

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

export type ApiRecommendationCard = {
  card_id: string;
  rank: number;
  /** 새로 사야 하는 상품들의 합. 옷장 옷만으로 짠 코디면 0 이다. */
  total_product_price: number | null;
  warnings: string[];
  items: ApiRecommendationItem[];
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
