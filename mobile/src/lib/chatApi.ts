import { ChatEndpoints } from '@/constants/config';
import { api } from '@/lib/apiClient';

/**
 * 채팅 API 의 원형(DTO)과 호출 함수.
 *
 * 여기서는 백엔드가 주는 모양을 **그대로** 둔다. 앱 화면이 쓰는 모양(말풍선 등)으로
 * 바꾸는 일은 state/chat.ts 가 맡는다 — 계약이 바뀌었을 때 고칠 자리를 한 곳으로 모으려는 것.
 */

/** 추천 방식. 앱의 'closet'/'taste' 와 1:1 대응한다 (state/chat.ts 의 toApiMode). */
export type ApiChatMode = 'WARDROBE_BASED' | 'NEW_ITEM';

export type ApiMessageRole = 'USER' | 'ASSISTANT' | 'SYSTEM' | 'TOOL';
export type ApiMessageStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

/**
 * run 의 상태. **SSE 이벤트 이름과 철자가 다르다** —
 * 이벤트 `completed` 가 여기서는 `SUCCEEDED` 다. 둘을 섞어 비교하지 말 것.
 */
export type ApiRunStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'NEEDS_CLARIFICATION'
  | 'SUCCEEDED'
  | 'FAILED';

export type ApiChatAttachment = {
  id: string;
  mime_type: string;
  size: number;
  analysis_status: string;
  analysis_result: unknown;
  mood_decision: string | null;
  image_url: string | null;
  created_at: string;
};

export type ApiChatMessage = {
  id: string;
  sequence: number;
  role: ApiMessageRole;
  content: string;
  status: ApiMessageStatus;
  client_message_id: string;
  /** 추천이 붙은 답변이면 recommendation_result_id 가 여기 들어온다. */
  metadata: Record<string, unknown>;
  attachments: ApiChatAttachment[];
  created_at: string;
  updated_at: string;
};

export type ApiChatSession = {
  id: string;
  mode: ApiChatMode;
  title: string;
  conversation_summary: string;
  last_message_at: string;
  created_at: string;
  updated_at: string;
};

export type ApiChatRun = {
  id: string;
  session_id: string;
  request_message_id: string;
  response_message_id: string | null;
  status: ApiRunStatus;
  error_code: string;
  error_message: string;
  created_at: string;
  updated_at: string;
};

/** 메시지 전송의 202 응답. events_url 은 신뢰하지 않는다(config.ts 주석 참고). */
export type ApiMessageSubmit = {
  message: ApiChatMessage;
  run: ApiChatRun;
  events_url: string;
};

/**
 * 재전송을 서버가 같은 메시지로 알아보게 하는 값.
 * 같은 요청을 재시도할 때는 **같은 값**을 그대로 다시 보내야 중복 말풍선이 생기지 않는다.
 * (그래서 전송 함수가 내부에서 만들지 않고 호출자가 들고 있게 한다.)
 *
 * ⚠️ `run:` 으로 시작하면 서버가 400 을 낸다 — 서버가 답변 메시지에 쓰는 예약 접두사다.
 */
export function newClientMessageId(): string {
  return `c${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function listSessions(): Promise<ApiChatSession[]> {
  return api.get<ApiChatSession[]>(ChatEndpoints.sessions);
}

export function createSession(mode: ApiChatMode, title?: string): Promise<ApiChatSession> {
  return api.post<ApiChatSession>(ChatEndpoints.sessions, { mode, ...(title ? { title } : {}) });
}

export function renameSession(sessionId: string, title: string): Promise<ApiChatSession> {
  return api.patch<ApiChatSession>(ChatEndpoints.session(sessionId), { title });
}

export function deleteSession(sessionId: string): Promise<void> {
  return api.delete<void>(ChatEndpoints.session(sessionId));
}

/** 시간순 전체 메시지. 대화가 길어지면 messages/page/ 로 나눠 받는 길도 있다. */
export function listMessages(sessionId: string): Promise<ApiChatMessage[]> {
  return api.get<ApiChatMessage[]>(ChatEndpoints.messages(sessionId));
}

/**
 * 질문 전송. **답변은 이 응답에 들어있지 않다** — 202 로 접수만 되고,
 * 실제 답변은 run 을 구독해야 온다(lib/chatStream.ts).
 */
export function sendMessage(
  sessionId: string,
  content: string,
  clientMessageId: string,
): Promise<ApiMessageSubmit> {
  return api.post<ApiMessageSubmit>(ChatEndpoints.messages(sessionId), {
    content,
    client_message_id: clientMessageId,
  });
}

/** run 단건 조회 — 네이티브 폴링과 SSE 실패 시 복구에 쓴다. */
export function getRun(runId: string): Promise<ApiChatRun> {
  return api.get<ApiChatRun>(ChatEndpoints.run(runId));
}
