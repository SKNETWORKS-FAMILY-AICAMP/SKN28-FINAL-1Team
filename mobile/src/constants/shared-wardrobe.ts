import type { SharedItemStatus } from '@/lib/wardrobeApi';

export const SHARED_ITEM_STATUS_META: Record<
  SharedItemStatus,
  { label: string; description: string; chatReference: boolean }
> = {
  available: {
    label: '공유 가능',
    description: '친구가 볼 수 있고 채팅 추천에도 참고할 수 있어요.',
    chatReference: true,
  },
  borrowed: {
    label: '대여 중',
    description: '대여 중으로 표시되지만 채팅 추천에는 계속 참고할 수 있어요.',
    chatReference: true,
  },
  private: {
    label: '나만 보기',
    description: '공유방에는 남지만 채팅 추천의 참고 대상에서는 제외돼요.',
    chatReference: false,
  },
};

export const SHARED_ITEM_STATUSES = [
  'available',
  'borrowed',
  'private',
] as const satisfies readonly SharedItemStatus[];
