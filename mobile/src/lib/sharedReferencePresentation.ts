/** 공유 옷 레퍼런스의 선택 상태와 결과 표시를 화면용 값으로 변환한다. */

export type SharedReferenceUnavailableReason =
  | 'PRIVATE'
  | 'NOT_CONFIRMED'
  | 'VECTOR_NOT_READY';

export type ReferenceMatchLike = {
  match_type?: string;
  source_type?: string;
  reasons?: string[];
};

export type ReferenceSummaryLike = {
  shared_item_id: string;
  item_name: string;
  category_large: string;
  owner_name: string;
  room_name: string;
  image_url: string | null;
};

export type ReferenceBadgePresentation = {
  label: string;
  isStyleFallback: boolean;
  reasons: string[];
};

const UNAVAILABLE_LABELS: Record<SharedReferenceUnavailableReason, string> = {
  PRIVATE: '나만 보기 상태',
  VECTOR_NOT_READY: '이미지 분석 중',
  NOT_CONFIRMED: '옷 정보 확인 필요',
};

const REFERENCE_LABELS: Record<string, string> = {
  'WARDROBE:VISUAL_SIMILAR': '친구 옷과 비슷한 내 옷',
  'WARDROBE:STYLE_SIMILAR': '친구 옷과 스타일이 비슷한 내 옷',
  'PRODUCT:VISUAL_SIMILAR': '친구 옷과 비슷한 새 상품',
  'PRODUCT:STYLE_SIMILAR': '친구 옷과 스타일이 비슷한 새 상품',
};

export function sharedReferenceUnavailableLabel(input: {
  referenceEligible: boolean;
  referenceUnavailableReason: SharedReferenceUnavailableReason | null;
}): string | null {
  if (input.referenceEligible) return null;
  return input.referenceUnavailableReason
    ? UNAVAILABLE_LABELS[input.referenceUnavailableReason]
    : '지금은 참고할 수 없어요';
}

export function buildReferenceBadge(
  match: ReferenceMatchLike | undefined,
): ReferenceBadgePresentation | null {
  const label = REFERENCE_LABELS[`${match?.source_type}:${match?.match_type}`];
  if (!label) return null;
  return {
    label,
    isStyleFallback: match?.match_type === 'STYLE_SIMILAR',
    reasons: match?.reasons ?? [],
  };
}

export function buildReferenceBubble(summary: ReferenceSummaryLike, text: string) {
  return {
    kind: 'reference' as const,
    text,
    sharedItemId: summary.shared_item_id,
    imageUrl: summary.image_url,
    itemName: summary.item_name || summary.category_large || '옷',
    ownerName: summary.owner_name,
    roomName: summary.room_name || undefined,
  };
}
