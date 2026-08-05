import { useLocalSearchParams } from 'expo-router';

import { ChatRoomView } from '@/components/chat/chat-room-view';

/**
 * C2 채팅 대화 화면.
 * 본문은 ChatRoomView 가 담당한다 — /chat 도 같은 것을 그리므로 컴포넌트를 공유한다.
 */
export default function ChatRoom() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  // 다른 화면(옷 상세·저장한 룩 등)에서 밀고 들어온 경우가 있어 뒤로가기를 둔다.
  return <ChatRoomView sessionId={id} showBack />;
}
