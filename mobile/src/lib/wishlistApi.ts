import { WishlistEndpoints } from '@/constants/config';
import { api } from '@/lib/apiClient';

/**
 * 찜(판매 상품) API.
 *
 * 상품을 이름이 아니라 **카탈로그 식별자**(`source_id`)로 구분한다 — 같은 상품이
 * 추천마다 다른 이름으로 오기 때문이다. 그래서 담을 때는 추천 아이템을 가리키고
 * (서버가 그 아이템에서 상품을 찾아 브랜드·판매처를 채운다), 뺄 때는 찜 행 id 를 쓴다.
 */

export type ApiWishItem = {
  wish_id: string;
  /** 담을 때의 추천 구성 아이템. 추천이 지워지면 null 이 된다. */
  item_id: string | null;
  result_id: string | null;
  card_id: string | null;
  source_collection: string;
  /** 카탈로그 원본 상품 식별자. 하트가 켜졌는지 판단하는 기준이다. */
  source_id: string;
  display_name: string;
  /** 카탈로그에 없으면 빈 문자열 (11번가 상품엔 브랜드 열이 없다) */
  brand: string;
  price_snapshot: number | null;
  /** S3 키 또는 URL — recommendApi 의 imageUrlOf() 로 걸러 쓴다. */
  image_ref: string;
  purchase_url: string;
  slot: string;
  added_at: string;
};

export function listWishlist(): Promise<ApiWishItem[]> {
  return api.get<ApiWishItem[]>(WishlistEndpoints.list);
}

/** 이미 담긴 상품이면 서버가 200 으로 같은 행을 돌려준다(중복 생성 없음). */
export function addWish(
  resultId: string,
  cardId: string,
  itemId: string,
): Promise<ApiWishItem> {
  return api.post<ApiWishItem>(WishlistEndpoints.add(resultId, cardId, itemId));
}

export function removeWish(wishId: string): Promise<void> {
  return api.delete<void>(WishlistEndpoints.remove(wishId));
}
