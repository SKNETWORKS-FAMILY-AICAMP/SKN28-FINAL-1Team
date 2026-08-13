import { Platform } from 'react-native';

import { API_BASE_URL, ChatEndpoints } from '@/constants/config';
import { api, apiFetch, ApiError } from '@/lib/apiClient';
import { getAccessToken } from '@/lib/secureStore';
import { guessFileName, guessMimeType, uploadMultipart } from '@/lib/uploadFile';

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

/** 사진 무드 분석의 진행 상태. 승인/거절은 `SUCCEEDED` 가 된 뒤에만 할 수 있다. */
export type ApiAnalysisStatus =
  | 'NOT_REQUESTED'
  | 'QUEUED'
  | 'PROCESSING'
  | 'SUCCEEDED'
  | 'FAILED';

/** 무드를 추천 조건에 반영할지 정한 결과. 한 번 정하면 되돌릴 수 없다(서버가 409). */
export type ApiMoodDecision = 'UNDECIDED' | 'APPROVED' | 'REJECTED';

/** 승인/거절을 보낼 때 쓰는 값. 저장되는 값(APPROVED/REJECTED)과 **철자가 다르다**. */
export type ApiMoodDecisionInput = 'APPROVE' | 'REJECT';

/**
 * 사진에서 읽어낸 무드.
 * `tags` 는 사람에게 보여줄 짧은 한국어 단어이고, `styles`/`colors`/`fits` 는 추천 필터에
 * 그대로 들어가는 서비스 표준값이다. 화면에는 tags 만 쓴다.
 */
export type ApiMoodAnalysis = {
  summary: string;
  tags: string[];
  styles: string[];
  colors: string[];
  fits: string[];
};

export type ApiChatAttachment = {
  id: string;
  mime_type: string;
  size: number;
  analysis_status: ApiAnalysisStatus;
  /** 분석 전에는 빈 객체다 — tags 가 있는지로 판단할 것. */
  analysis_result: Partial<ApiMoodAnalysis>;
  mood_decision: ApiMoodDecision | null;
  /** presigned GET (기본 1시간). 만료되면 메시지를 다시 받아야 새 주소가 온다. */
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

/* ── 사진 ──────────────────────────────────────────────
   업로드 → 무드 분석 → 승인/거절 세 단계다. 업로드만으로는 분석이 시작되지 않는다
   (`analysis_status` 가 `NOT_REQUESTED` 로 남는다). */

/** 업로드 응답. `created:false` 면 같은 client_message_id 로 이미 올린 사진이다. */
export type ApiAttachmentUpload = {
  message: ApiChatMessage;
  attachment: ApiChatAttachment;
  created: boolean;
};

/** 무드 분석 접수의 202 응답. 답변과 마찬가지로 run 을 기다려야 결과가 나온다. */
export type ApiMoodAnalysisSubmit = {
  attachment: ApiChatAttachment;
  run: ApiChatRun;
  events_url: string;
};

export type ApiMoodDecisionResult = {
  attachment: ApiChatAttachment;
  /** 이번 호출로 실제 상태가 바뀌었는지 (같은 결정을 다시 보내면 false) */
  changed: boolean;
  /** 추천 조건에 반영됐는지. REJECT 면 false. */
  applied: boolean;
  context_state: Record<string, unknown>;
};

/** 업로드 상한. 없으면 응답이 안 올 때 화면이 영영 "보내는 중"으로 남는다. */
const UPLOAD_TIMEOUT_MS = 60_000;

function withUploadTimeout<T>(request: Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('사진 전송이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요.'));
    }, UPLOAD_TIMEOUT_MS);
    request.then(resolve, reject).finally(() => clearTimeout(timer));
  });
}

/** XHR 응답을 DTO 로. 실패면 서버가 준 본문을 그대로 ApiError 에 실어 보낸다. */
function parseUploadResponse<T>(response: { status: number; body: string }): T {
  let data: unknown = null;
  try {
    data = response.body ? JSON.parse(response.body) : null;
  } catch {
    data = response.body;
  }
  if (response.status < 200 || response.status >= 300) {
    const detail = (data as { detail?: string } | null)?.detail;
    throw new ApiError(
      detail ?? `사진을 보내지 못했어요. (${response.status})`,
      response.status,
      data,
    );
  }
  return data as T;
}

/**
 * 사진 올리기. 첨부만 달린 사용자 메시지가 하나 생긴다.
 *
 * ⚠️ 글은 같이 보내지 않는다. 서버는 첨부가 있는 메시지를 **무드 분석 전용**으로 처리해서
 *    (orchestrator 가 첨부를 먼저 본다) 같이 보낸 글은 답변에 반영되지 않는다.
 *    말은 사진을 보낸 뒤 따로 하는 편이 사용자에게 정직하다.
 * ⚠️ 네이티브는 apiClient 를 타지 않는다 — 전역 fetch(Expo winter fetch)가 RN 의
 *    `{ uri, name, type }` 파트를 못 받아서 XHR 로 직접 보낸다(lib/uploadFile.ts 참고).
 *    그래서 401 자동 재발급이 없다.
 */
export async function uploadPhoto(
  sessionId: string,
  uri: string,
  clientMessageId: string,
): Promise<ApiAttachmentUpload> {
  const path = ChatEndpoints.attachments(sessionId);
  const name = guessFileName(uri, 'chat.jpg');
  const mimeType = guessMimeType(name);

  if (Platform.OS === 'web') {
    const blob = await fetch(uri).then((response) => {
      if (!response.ok) throw new Error('선택한 사진을 불러오지 못했어요.');
      return response.blob();
    });
    const form = new FormData();
    form.append('image', blob, name);
    form.append('client_message_id', clientMessageId);
    return withUploadTimeout(apiFetch<ApiAttachmentUpload>(path, { method: 'POST', body: form }));
  }

  const form = new FormData();
  // React Native 의 FormData 는 파일을 { uri, name, type } 로 받는다(XHR 전용).
  form.append('image', { uri, name, type: mimeType } as unknown as Blob);
  form.append('client_message_id', clientMessageId);
  const token = await getAccessToken();
  const response = await uploadMultipart(`${API_BASE_URL}${path}`, form, {
    token,
    timeoutMs: UPLOAD_TIMEOUT_MS,
  });
  return parseUploadResponse<ApiAttachmentUpload>(response);
}

/** 무드 분석 접수. 요청 본문은 없고, 결과는 run 이 끝나야 나온다. */
export function requestMoodAnalysis(
  sessionId: string,
  attachmentId: string,
): Promise<ApiMoodAnalysisSubmit> {
  return api.post<ApiMoodAnalysisSubmit>(
    ChatEndpoints.attachmentAnalysis(sessionId, attachmentId),
  );
}

/** 분석된 무드를 추천 조건에 넣을지 확정한다. 서버가 첫 결정만 받는다(번복 시 409). */
export function decideMood(
  sessionId: string,
  attachmentId: string,
  decision: ApiMoodDecisionInput,
): Promise<ApiMoodDecisionResult> {
  return api.post<ApiMoodDecisionResult>(
    ChatEndpoints.attachmentMoodDecision(sessionId, attachmentId),
    { decision },
  );
}
