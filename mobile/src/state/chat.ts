import { useSyncExternalStore } from 'react';

import { Editorial } from '@/constants/theme';
import {
  createSession as apiCreateSession,
  decideMood as apiDecideMood,
  deleteSession as apiDeleteSession,
  listMessages as apiListMessages,
  listSessions as apiListSessions,
  newClientMessageId,
  renameSession as apiRenameSession,
  sendMessage as apiSendMessage,
  startMoodAnalysis as apiStartMoodAnalysis,
  uploadAttachment as apiUploadAttachment,
  type ApiChatMessage,
  type ApiChatMode,
  type ApiChatRun,
  type ApiChatSession,
  type ApiMoodAnalysis,
  type ApiMoodDecision,
} from '@/lib/chatApi';
import { isAnswered, waitForRun, waitForStylistRun } from '@/lib/chatStream';
import {
  getRecommendationResult,
  imageUrlOf,
  type ApiRecommendationCard,
} from '@/lib/recommendApi';
import {
  requestAlternative as apiRequestAlternative,
  retryPersona as apiRetryPersona,
  saveCard as apiSaveCard,
  updateResponseMode as apiUpdateResponseMode,
  type ApiPersonaResult,
  type ApiResponseMode,
  type ApiStylistRun,
  type StylistId,
} from '@/lib/stylistApi';
import { stylistStore } from '@/state/stylist';

/**
 * 채팅 세션 — 목록(C1)·대화(C2)·모드 선택(C3)이 같은 출처를 봐야 하므로 여기로 모았다.
 *
 * 서버(/api/v1/chat/*)가 원본이고 이 스토어는 그 사본이다. 화면은 서버 모양을 몰라도 되게
 * 여기서 앱 모양(말풍선·모드 이름)으로 옮긴다.
 *
 * ⚠️ **답변은 동기로 오지 않는다.** 질문을 보내면 서버는 202 로 접수만 하고 run 을 만든다.
 *    답변이 생길 때까지 기다리는 일은 lib/chatStream.ts 가 맡는다.
 * ⚠️ 로그인 사용자 전용이다. 게스트 채팅은 쿠키 신원 방식이라 아직 붙이지 않았다.
 */

/** 추천 방식. chat-mode 화면의 두 카드와 1:1 대응한다. */
export type ChatMode = 'taste' | 'closet';

/** 모드의 이름·색. 목록의 그룹 머리와 대화 헤더 배지가 같은 값을 쓴다. */
export const CHAT_MODE_META: Record<ChatMode, { label: string; tint: string }> = {
  taste: { label: '추구미 반영', tint: Editorial.wine },
  closet: { label: '옷장 기반', tint: Editorial.ink },
};

/** 목록에 그릴 순서 — Object.keys 는 순서를 보장하는 것처럼 읽히지 않으므로 명시한다. */
export const CHAT_MODE_ORDER: ChatMode[] = ['taste', 'closet'];

/* ── 서버 ↔ 앱 모드 이름 옮기기 ──
   'closet'(옷장 기반)은 내 옷만 쓰고, 'taste'(추구미 반영)는 새 상품까지 포함한다. */
export function toApiMode(mode: ChatMode): ApiChatMode {
  return mode === 'closet' ? 'WARDROBE_BASED' : 'NEW_ITEM';
}

function fromApiMode(mode: ApiChatMode): ChatMode {
  return mode === 'WARDROBE_BASED' ? 'closet' : 'taste';
}

/**
 * 한 개의 말풍선.
 * 타이핑 표시(···)는 저장하지 않는다 — 답변을 기다리는 '지금'만의 상태라
 * 대화를 다시 열었을 때 남아 있으면 안 된다. 화면 쪽 지역 상태로 둔다.
 */
/** 추천 코디 한 벌을 이루는 아이템. */
export type RecItem = {
  id: string;
  name: string;
  category: string | null;
  /** 걸 수 있는 주소일 때만 채운다 (S3 키는 걸러진다 — lib/recommendApi 의 imageUrlOf). */
  imageUrl: string | null;
  /** 새로 사야 하는 상품만 가격이 있다. 옷장에 있는 옷은 null. */
  price: number | null;
  fromWardrobe: boolean;
};

export type ChatMessage =
  | { id: string; role: 'ai' | 'user'; kind: 'text'; text: string }
  /** 사용자가 올린 사진. uri 가 없던 시절(목업)에도 말풍선은 떠서 optional 로 둔다. */
  | { id: string; role: 'user'; kind: 'image'; uri?: string }
  /** 첨부한 사진에서 읽어낸 무드 — 추구미로 삼을지 묻는 카드 */
  | {
      id: string;
      role: 'ai';
      kind: 'mood';
      /** 결정을 보낼 때 필요하다. 카드가 어느 사진에서 나왔는지도 이 값으로 안다. */
      attachmentId: string;
      tags: string[];
      summary: string;
      /** null 이면 아직 안 고른 상태 — 그때만 버튼을 보여준다. */
      decision: 'APPROVED' | 'REJECTED' | null;
    }
  /**
   * 답변을 못 받은 질문 아래에 남기는 줄.
   * 토스트는 사라지므로, 대화를 다시 열었을 때 "질문만 있고 답이 없는" 상태로 보이지 않게 한다.
   */
  | { id: string; role: 'ai'; kind: 'error'; text: string }
  /** 추천 코디 카드. 답변 말풍선 뒤에 붙는다. */
  | {
      id: string;
      role: 'ai';
      kind: 'rec';
      title: string;
      tags: string[];
      items: RecItem[];
      /** 새로 사야 하는 상품 합계. 옷장 옷만으로 짠 코디면 0 이라 표시하지 않는다. */
      totalPrice: number | null;
      warnings: string[];
    }
  /**
   * 응답 모드가 바뀐 자리에 남기는 줄. **말풍선이 아니다** — 오간 말이 아니라 상태 표시라,
   * 실패 줄과 같은 결로 그린다. 여기부터 답하는 방식이 달라졌음을 되돌아봤을 때 알 수 있게 한다.
   */
  | {
      id: string;
      role: 'ai';
      kind: 'mode';
      mode: ApiResponseMode;
      /** STYLIST 일 때 답할 사람들의 이름 */
      names: string[];
    }
  /** 스타일리스트별 카드 묶음. 인원수만큼 자리가 먼저 생기고 끝난 것부터 채워진다. */
  | {
      id: string;
      role: 'ai';
      kind: 'stylist';
      runId: string;
      cards: StylistCard[];
    };

/**
 * 스타일리스트 한 명이 내놓은 카드의 화면용 모양.
 * 아직 안 끝났으면 status 가 PENDING/RUNNING 이고 items 는 비어 있다 — 그 상태로도 자리는 있다.
 */
export type StylistCard = {
  personaId: StylistId;
  name: string;
  /** 카드 순서를 고정하는 값. 끝난 순서로 자리가 바뀌면 볼 때마다 위치가 달라진다. */
  order: number;
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
  /** 페르소나 관점의 핵심 문장 하나 */
  message: string;
  /** 접힌 영역에 보여줄 근거 코드 (state/stylist.ts 의 reasonLabel 로 옮겨 그린다) */
  reasonCodes: string[];
  items: RecItem[];
  totalPrice: number | null;
  warnings: string[];
  /** '이 코디로 할래요'·'다른 추천'에 필요하다. 아직 결과가 없으면 null. */
  resultId: string | null;
  cardId: string | null;
  errorText: string | null;
  /** 다른 추천을 받는 중. 지금 카드는 남겨 두고 표시만 바꾼다. */
  alternating: boolean;
  alternativeCount: number;
  saved: boolean;
};

export type ChatSession = {
  id: string;
  mode: ChatMode;
  title: string;
  /** 서버가 가진 대화의 사본. 새로고침하면 이 배열은 통째로 다시 만들어진다. */
  messages: ChatMessage[];
  /**
   * 화면에 그릴 순서 — messages 에 스타일리스트 카드·모드 구분선을 끼워 넣은 것.
   *
   * 왜 따로 두는가 — 그 둘은 **서버 대화에 없다**. 카드는 run 에 딸린 것이고 구분선은 앱이
   * 남기는 표시라, 대화를 새로 받아오면(loadMessages) 사라진다. 그래서 messages 는 서버
   * 사본으로 두고, 끼워 넣은 결과를 여기에 따로 만든다. 화면은 이쪽만 그린다.
   */
  timeline: ChatMessage[];
  /** 대화를 한 번이라도 열어 메시지를 받아왔는지. 목록만 받은 세션은 false 다. */
  messagesLoaded: boolean;
  /** 다음 질문을 어떻게 답할지. 대화방을 옮기지 않고 이 값만 바뀐다. */
  responseMode: ApiResponseMode;
  /** STYLIST 일 때 답할 스타일리스트들 (1~3명). 끄더라도 지우지 않는다 — 다시 켜면 복원한다. */
  selectedPersonaIds: StylistId[];
  updatedAt: number;
};

const MINUTE = 60 * 1000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** 목록의 시각 표시. '방금 / n분 전 / n시간 전 / 어제 / n일 전 / M월 D일' */
export function formatRelativeTime(ts: number, now: number = Date.now()): string {
  const diff = Math.max(0, now - ts);
  if (diff < MINUTE) return '방금';
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)}분 전`;
  if (diff < DAY) return `${Math.floor(diff / HOUR)}시간 전`;
  const days = Math.floor(diff / DAY);
  if (days === 1) return '어제';
  if (days < 7) return `${days}일 전`;
  const d = new Date(ts);
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}

/** 목록에 한 줄로 보여줄 마지막 대화. 추천 카드·사진은 문구가 없으니 대신할 말을 준다. */
export function sessionPreview(session: ChatSession): string {
  const last = session.messages[session.messages.length - 1];
  if (!last) return session.messagesLoaded ? '아직 대화가 없어요' : '';
  if (last.kind === 'text') return last.text.replace(/\n/g, ' ');
  if (last.kind === 'rec') return `추천 · ${last.title}`;
  if (last.kind === 'mood') return `추구미 · ${last.tags.join(' ')}`;
  if (last.kind === 'error') return '답변을 받지 못했어요';
  return '사진을 보냈어요';
}

/** 검색이 훑을 글자. 사진 말풍선은 글자가 없어 검색되지 않는다. */
function searchableText(m: ChatMessage): string {
  if (m.kind === 'text') return m.text;
  if (m.kind === 'rec') return `${m.title} ${m.tags.join(' ')}`;
  if (m.kind === 'mood') return m.tags.join(' ');
  /* 오류 줄은 검색 대상이 아니다 — 대화 내용이 아니라 상태 표시라, 검색어에 걸리면
     엉뚱한 대화가 결과로 올라온다. */
  return '';
}

/**
 * 제목과 대화 내용으로 찾는다. 대소문자 구분 없는 부분 일치.
 *
 * ⚠️ 아직 연 적 없는 세션은 메시지가 비어 있어 **제목으로만** 걸린다.
 *    서버에 /chat/sessions/search/ 가 있으니 그걸로 옮기면 본문까지 찾을 수 있다.
 */
export function sessionMatches(session: ChatSession, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (session.title.toLowerCase().includes(q)) return true;
  return session.messages.some((m) => searchableText(m).toLowerCase().includes(q));
}

/**
 * 검색 결과의 미리보기 — 검색어가 걸린 말풍선을 보여준다.
 * 마지막 대화를 그대로 두면 '왜 이게 결과인지' 알 수 없다.
 */
export function searchPreview(session: ChatSession, query: string): string {
  const q = query.trim().toLowerCase();
  if (!q) return sessionPreview(session);
  const hit = session.messages.find((m) => searchableText(m).toLowerCase().includes(q));
  if (!hit) return sessionPreview(session);
  if (hit.kind === 'rec') return `추천 · ${hit.title}`;
  if (hit.kind === 'mood') return `추구미 · ${hit.tags.join(' ')}`;
  return searchableText(hit).replace(/\n/g, ' ');
}

/* ── 서버 응답 옮기기 ───────────────────────────────── */

function toRecMessage(messageId: string, card: ApiRecommendationCard): ChatMessage {
  return {
    id: `${messageId}-r${card.card_id}`,
    role: 'ai',
    kind: 'rec',
    /* 서버가 코디에 이름을 붙이지 않는다. 없는 이름을 지어내면 추천마다 다른 작명 규칙이
       생기므로 순위를 그대로 쓴다. */
    title: `추천 코디 ${card.rank}`,
    tags: card.items.map((i) => i.category || i.slot).filter(Boolean),
    items: card.items.map((i) => ({
      id: i.item_id,
      name: i.display_name,
      category: i.category,
      imageUrl: imageUrlOf(i.image_ref),
      price: i.price_snapshot,
      fromWardrobe: i.source_type !== 'PRODUCT',
    })),
    totalPrice: card.total_product_price,
    warnings: card.warnings ?? [],
  };
}

/**
 * 무드 분석이 끝나면 서버가 **답변 메시지**를 하나 남긴다
 * (metadata.message_kind === 'mood', "사진에서 … 무드가 보여요. 반영할까요?").
 *
 * 그 메시지를 글 말풍선으로 그리는 대신 카드로 바꾼다. 카드가 같은 내용에 태그와
 * 선택 버튼까지 담고 있어서, 둘 다 그리면 같은 말이 연달아 두 번 나온다.
 *
 * 결정 상태(APPROVED/REJECTED)는 메시지가 아니라 **첨부**에 남으므로 밖에서 찾아 넣는다.
 */
function toMoodMessage(
  api: ApiChatMessage,
  decisions: Map<string, ApiMoodDecision | null>,
): ChatMessage | null {
  const meta = api.metadata ?? {};
  if (meta.message_kind !== 'mood') return null;
  const analysis = (meta.mood_analysis ?? {}) as Partial<ApiMoodAnalysis>;
  const tags = analysis.tags ?? [];
  const attachmentId = typeof meta.attachment_id === 'string' ? meta.attachment_id : '';
  if (tags.length === 0 || !attachmentId) return null;

  const decided = decisions.get(attachmentId);
  return {
    id: api.id,
    role: 'ai',
    kind: 'mood',
    attachmentId,
    tags,
    summary: analysis.summary ?? '',
    // UNDECIDED 와 null 은 같은 뜻으로 다룬다 — 아직 안 고른 것.
    decision: decided === 'APPROVED' || decided === 'REJECTED' ? decided : null,
  };
}

/** 첨부에만 있는 결정 상태를 attachment_id 로 찾을 수 있게 모은다. */
function collectDecisions(list: ApiChatMessage[]): Map<string, ApiMoodDecision | null> {
  const map = new Map<string, ApiMoodDecision | null>();
  for (const m of list) {
    for (const a of m.attachments) map.set(a.id, a.mood_decision);
  }
  return map;
}

/**
 * 서버 메시지 → 말풍선.
 * SYSTEM·TOOL 은 사람에게 보여줄 말이 아니라 버린다. 사진 첨부는 사진 말풍선을 따로 만들어
 * 글보다 앞에 놓는다 — 올릴 때 사진이 먼저였으니 다시 열어도 그 순서여야 한다.
 * 추천 카드는 말풍선 **뒤에** 붙는다 (먼저 말로 설명하고 그다음 코디를 보여주는 순서).
 */
function toMessages(
  api: ApiChatMessage,
  cards: ApiRecommendationCard[] = [],
  decisions: Map<string, ApiMoodDecision | null> = new Map(),
): ChatMessage[] {
  if (api.role !== 'USER' && api.role !== 'ASSISTANT') return [];
  const role = api.role === 'USER' ? 'user' : 'ai';
  const out: ChatMessage[] = [];

  if (role === 'user') {
    for (const a of api.attachments) {
      out.push({ id: `${api.id}-a${a.id}`, role: 'user', kind: 'image', uri: a.image_url ?? undefined });
    }
  }

  // 무드 답변은 글 대신 카드로 그린다 (toMoodMessage 주석 참고).
  const mood = role === 'ai' ? toMoodMessage(api, decisions) : null;
  if (mood) {
    out.push(mood);
    return out;
  }

  const text = api.content.trim();
  if (text) out.push({ id: api.id, role, kind: 'text', text });
  for (const card of cards) out.push(toRecMessage(api.id, card));

  /* 답변 생성이 실패하면 서버가 **질문 메시지**를 FAILED 로 표시한다(답변 메시지는 아예 없다).
     그 표시를 읽어 오류 줄을 만들면 대화를 다시 열어도 남는다.
     사유까지는 run 에만 있어 여기서는 알 수 없다 — 보낸 직후에는 sendText 가 채워 넣는다. */
  if (role === 'user' && api.status === 'FAILED') {
    out.push({ id: failureLineId(api.id), role: 'ai', kind: 'error', text: GENERIC_FAILURE });
  }
  return out;
}

const GENERIC_FAILURE = '답변을 만들지 못했어요.';

function failureLineId(messageId: string): string {
  return `${messageId}-err`;
}

/** 답변에 붙은 추천 id. 없으면 그냥 대화만 오간 것이다. */
function recommendationIdOf(api: ApiChatMessage): string | null {
  const id = api.metadata?.recommendation_result_id;
  return typeof id === 'string' && id ? id : null;
}

/**
 * 추천이 붙은 답변들의 코디 카드를 한꺼번에 받아 메시지 id 별로 묶는다.
 *
 * 실패해도 대화 자체는 보여줘야 하므로 카드만 조용히 빠뜨린다 — 추천 조회 한 번이 실패했다고
 * 주고받은 말까지 사라지면 무엇이 잘못됐는지 알 수 없다.
 */
async function fetchCards(list: ApiChatMessage[]): Promise<Map<string, ApiRecommendationCard[]>> {
  const targets = list
    .map((m) => ({ messageId: m.id, resultId: recommendationIdOf(m) }))
    .filter((t): t is { messageId: string; resultId: string } => t.resultId !== null);

  const byMessage = new Map<string, ApiRecommendationCard[]>();
  if (targets.length === 0) return byMessage;

  // 같은 추천을 두 메시지가 가리킬 수 있어 결과별로 한 번만 부른다.
  const unique = [...new Set(targets.map((t) => t.resultId))];
  const results = await Promise.all(
    unique.map((id) =>
      getRecommendationResult(id)
        .then((r) => [id, r.cards] as const)
        .catch(() => [id, [] as ApiRecommendationCard[]] as const),
    ),
  );
  const cardsByResult = new Map(results);
  for (const t of targets) byMessage.set(t.messageId, cardsByResult.get(t.resultId) ?? []);
  return byMessage;
}

function toSession(api: ApiChatSession, previous?: ChatSession): ChatSession {
  return {
    id: api.id,
    mode: fromApiMode(api.mode),
    title: api.title,
    // 목록 갱신이 이미 받아둔 대화를 지우면 안 된다.
    messages: previous?.messages ?? [],
    timeline: previous?.timeline ?? [],
    messagesLoaded: previous?.messagesLoaded ?? false,
    /* ⚠️ 서버가 이 필드를 **안 줄 수도 있다**(배포 서버가 아직 스타일리스트 이전 버전).
       없을 때 DEFAULT 로 덮으면 방금 켠 모드가 목록 새로고침 한 번에 꺼진다. */
    responseMode: api.response_mode ?? previous?.responseMode ?? 'DEFAULT',
    selectedPersonaIds: api.selected_persona_ids ?? previous?.selectedPersonaIds ?? [],
    updatedAt: new Date(api.last_message_at || api.updated_at).getTime(),
  };
}

/* ── 타임라인에 끼워 넣는 것들 ───────────────────────
   서버 대화에 없는 두 가지(모드 구분선·스타일리스트 카드)를 세션별로 따로 들고 있다가
   messages 사이에 끼워 넣는다. 붙는 자리는 **바로 앞 말풍선의 id** 로 기억한다 —
   대화를 다시 받아와도 그 말풍선은 같은 id 로 돌아오므로 자리를 잃지 않는다.
   (앱을 껐다 켜면 사라진다. 서버에 남는 값이 아니라 이번 실행에서만 유효한 표시다.) */

type Overlay = { id: string; after: string | null; message: ChatMessage };

const overlays = new Map<string, Overlay[]>();

function overlaysOf(sessionId: string): Overlay[] {
  return overlays.get(sessionId) ?? [];
}

/** messages 에 끼워 넣어 화면에 그릴 순서를 만든다. */
function buildTimeline(sessionId: string, messages: ChatMessage[]): ChatMessage[] {
  const list = overlaysOf(sessionId);
  if (list.length === 0) return messages;

  const byAnchor = new Map<string, ChatMessage[]>();
  const head: ChatMessage[] = [];
  const anchors = new Set(messages.map((m) => m.id));
  /* 앵커를 못 찾은 것 = 방금 만들어져 아직 서버 대화에 없는 말풍선에 붙은 경우.
     맨 뒤로 보낸다 — 실제로도 지금 대화의 끝이다. */
  const orphans: ChatMessage[] = [];

  for (const o of list) {
    if (o.after === null) head.push(o.message);
    else if (anchors.has(o.after)) {
      const bucket = byAnchor.get(o.after) ?? [];
      bucket.push(o.message);
      byAnchor.set(o.after, bucket);
    } else orphans.push(o.message);
  }

  const out: ChatMessage[] = [...head];
  for (const m of messages) {
    out.push(m);
    const attached = byAnchor.get(m.id);
    if (attached) out.push(...attached);
  }
  return [...out, ...orphans];
}

/** 끼워 넣은 것이 바뀌었을 때 화면용 순서를 다시 만든다 (replaceSession 이 알아서 계산한다). */
function rebuildTimeline(sessionId: string) {
  replaceSession(sessionId, (s) => s);
}

function addOverlay(sessionId: string, overlay: Overlay) {
  overlays.set(sessionId, [...overlaysOf(sessionId), overlay]);
  rebuildTimeline(sessionId);
}

function updateOverlay(sessionId: string, overlayId: string, message: ChatMessage) {
  overlays.set(
    sessionId,
    overlaysOf(sessionId).map((o) => (o.id === overlayId ? { ...o, message } : o)),
  );
  rebuildTimeline(sessionId);
}

/** 붙는 자리를 옮긴다 — 답변까지 받고 나면 카드는 그 답변 **뒤**에 있어야 한다. */
function reanchorOverlay(sessionId: string, overlayId: string, after: string | null) {
  overlays.set(
    sessionId,
    overlaysOf(sessionId).map((o) => (o.id === overlayId ? { ...o, after } : o)),
  );
  rebuildTimeline(sessionId);
}

function lastMessageId(sessionId: string): string | null {
  const session = sessions.find((s) => s.id === sessionId);
  const list = session?.messages ?? [];
  return list.length > 0 ? list[list.length - 1].id : null;
}

/** 스타일리스트 묶음 안의 카드 하나만 손본다. */
function patchCard(
  message: ChatMessage,
  personaId: StylistId,
  patch: (card: StylistCard) => StylistCard,
): ChatMessage {
  if (message.kind !== 'stylist') return message;
  return {
    ...message,
    cards: message.cards.map((c) => (c.personaId === personaId ? patch(c) : c)),
  };
}

/* ── 스타일리스트 결과 옮기기 ───────────────────────── */

function toStylistCard(r: ApiPersonaResult): StylistCard {
  const card = r.card;
  return {
    personaId: r.persona_id,
    name: r.display_name || stylistStore.displayName(r.persona_id),
    order: r.display_order,
    status: r.status,
    message: r.message,
    reasonCodes: r.validated_reason_codes ?? [],
    items:
      card?.items.map((i) => ({
        id: i.item_id,
        name: i.display_name,
        category: i.category,
        imageUrl: imageUrlOf(i.image_ref),
        price: i.price_snapshot,
        fromWardrobe: i.source_type !== 'PRODUCT',
      })) ?? [],
    totalPrice: card?.total_product_price ?? null,
    warnings: card?.warnings ?? [],
    resultId: r.result_id,
    cardId: card?.card_id ?? null,
    errorText: r.error?.message || null,
    alternating: r.alternative_status === 'PENDING' || r.alternative_status === 'RUNNING',
    alternativeCount: r.alternative_count,
    saved: card?.is_saved ?? false,
  };
}

/** 아직 아무것도 안 받은 자리 — 인원수만큼 먼저 깔아 두는 로딩 카드. */
function pendingCard(personaId: StylistId): StylistCard {
  return {
    personaId,
    name: stylistStore.displayName(personaId),
    order: stylistStore.displayOrder(personaId),
    status: 'PENDING',
    message: '',
    reasonCodes: [],
    items: [],
    totalPrice: null,
    warnings: [],
    resultId: null,
    cardId: null,
    errorText: null,
    alternating: false,
    alternativeCount: 0,
    saved: false,
  };
}

function toStylistMessage(id: string, runId: string, run: ApiStylistRun): ChatMessage {
  return {
    id,
    role: 'ai',
    kind: 'stylist',
    runId,
    cards: [...run.results].sort((a, b) => a.display_order - b.display_order).map(toStylistCard),
  };
}

/** 한 run 의 카드 묶음은 하나뿐이라 id 를 run 에서 바로 만든다 (재시도·다른추천이 다시 찾는다). */
function stylistOverlayId(runId: string): string {
  return `sty-${runId}`;
}

/**
 * 스타일리스트 답변 한 턴.
 *
 * **인원수만큼 빈 카드를 먼저 깔고** 시작한다 — 다 끝난 뒤 한 번에 그리면 먼저 끝난 카드가
 * 남을 기다리는 동안 화면이 비고, 몇 장이 올지도 알 수 없다. 서버도 run 을 만들 때 자리를
 * 먼저 만들어 두므로 화면이 그 모양을 그대로 따른다.
 */
async function runStylistTurn(
  sessionId: string,
  runId: string,
  personaIds: StylistId[],
  question: string,
): Promise<{ run: ApiStylistRun; overlayId: string }> {
  const overlayId = stylistOverlayId(runId);
  const ordered = stylistStore.sortIds(personaIds);

  addOverlay(sessionId, {
    id: overlayId,
    // 방금 띄운 내 말풍선 뒤. 답변이 들어오면 sendText 가 그 뒤로 옮긴다.
    after: lastMessageId(sessionId),
    message: {
      id: overlayId,
      role: 'ai',
      kind: 'stylist',
      runId,
      cards: ordered.map(pendingCard),
    },
  });

  try {
    const run = await waitForStylistRun(runId, {
      hint: { personaIds: ordered, question },
      onProgress: (r) => {
        if (r.results.length === 0) return; // 아직 자리가 안 생겼다 — 깔아 둔 카드를 지우지 않는다
        updateOverlay(sessionId, overlayId, toStylistMessage(overlayId, runId, r));
      },
    });
    if (run.results.length > 0) {
      updateOverlay(sessionId, overlayId, toStylistMessage(overlayId, runId, run));
    } else {
      // 자리조차 안 생기고 run 이 끝났다 = 스타일리스트 실행 자체가 실패
      failPendingCards(sessionId, overlayId, run.error_message || GENERIC_FAILURE);
    }
    return { run, overlayId };
  } catch (e) {
    /* 시간 초과 등으로 기다리기를 포기했다. 깔아 둔 카드를 그대로 두면 영영 도는 것처럼
       보이므로 실패로 바꿔 놓고 예외는 그대로 올린다(화면이 토스트로 알린다). */
    failPendingCards(sessionId, overlayId, messageOf(e, GENERIC_FAILURE));
    throw e;
  }
}

/** 아직 안 끝난 카드들을 실패로 바꾼다. 이미 받은 카드는 건드리지 않는다. */
function failPendingCards(sessionId: string, overlayId: string, text: string) {
  const current = overlaysOf(sessionId).find((o) => o.id === overlayId)?.message;
  if (!current || current.kind !== 'stylist') return;
  updateOverlay(sessionId, overlayId, {
    ...current,
    cards: current.cards.map((c) =>
      c.status === 'PENDING' || c.status === 'RUNNING'
        ? { ...c, status: 'FAILED', errorText: text }
        : c,
    ),
  });
}

/** 폴링 중간 상태를 카드에 반영한다. 재시도·다른추천이 공유한다. */
function applyRunProgress(sessionId: string, runId: string, run: ApiStylistRun) {
  if (run.results.length === 0) return;
  const overlayId = stylistOverlayId(runId);
  updateOverlay(sessionId, overlayId, toStylistMessage(overlayId, runId, run));
}

function sameIds(a: StylistId[], b: StylistId[]): boolean {
  return a.length === b.length && a.every((id, i) => id === b[i]);
}

/* ── 스토어 ─────────────────────────────────────────── */

let sessions: ChatSession[] = [];
let loading = false;
/**
 * 목록을 **한 번이라도** 받아왔는지. 빈 배열만으로는 "아직 안 불러옴"과 "정말 없음"을
 * 구분할 수 없어서, 첫 렌더에 "대화가 없어요" 화면이 한 프레임 번쩍이는 문제가 있었다.
 */
let loadedOnce = false;
let error: string | null = null;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

/** 최근 대화가 위로. 목록·검색이 모두 이 순서를 쓴다. */
function sortByRecent(list: ChatSession[]): ChatSession[] {
  return [...list].sort((a, b) => b.updatedAt - a.updatedAt);
}

/**
 * 세션 하나를 바꾼다.
 *
 * 화면용 순서(timeline)는 여기서 **항상** 다시 만든다. 말풍선을 건드리는 자리마다 따로
 * 챙기게 두면 한 곳만 빠뜨려도 "방금 보낸 말이 안 보이는" 상태가 된다 — 한 곳으로 모은다.
 */
function replaceSession(id: string, patch: (s: ChatSession) => ChatSession) {
  sessions = sessions.map((s) => {
    if (s.id !== id) return s;
    const next = patch(s);
    return { ...next, timeline: buildTimeline(id, next.messages) };
  });
  notify();
}

let messageSeq = 0;

/** 말풍선 id — 같은 밀리초에 여러 개가 추가돼도 겹치지 않게 순번을 붙인다. */
export function nextMessageId(): string {
  return `m${Date.now()}-${++messageSeq}`;
}

function messageOf(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

export const chatStore = {
  getSessions: () => sessions,
  getSession: (id: string | undefined) =>
    id ? sessions.find((s) => s.id === id) : undefined,
  getStatus: () => status,

  /** 목록 새로고침. 화면 진입·당겨서 새로고침에서 부른다. */
  async loadSessions(): Promise<void> {
    loading = true;
    error = null;
    setStatus();
    try {
      const list = await apiListSessions();
      const before = new Map(sessions.map((s) => [s.id, s]));
      sessions = sortByRecent(list.map((s) => toSession(s, before.get(s.id))));
    } catch (e) {
      error = messageOf(e, '대화 목록을 불러오지 못했어요');
    } finally {
      loading = false;
      loadedOnce = true;
      setStatus();
      notify();
    }
  },

  /** 대화 내용 받아오기. 이미 받아둔 세션은 다시 부르지 않는다(force 로 강제). */
  async loadMessages(id: string, options: { force?: boolean } = {}): Promise<void> {
    const current = sessions.find((s) => s.id === id);
    if (!options.force && current?.messagesLoaded) return;
    const list = await apiListMessages(id);
    const cards = await fetchCards(list);
    const decisions = collectDecisions(list);
    replaceSession(id, (s) => ({
      ...s,
      messages: list.flatMap((m) => toMessages(m, cards.get(m.id), decisions)),
      messagesLoaded: true,
    }));
  },

  /**
   * 새 대화. 서버가 인사 메시지를 sequence 1 로 미리 넣어 주므로 여기서 만들지 않는다.
   * 제목도 서버가 첫 질문을 보고 정한다 — 그래서 만들 때는 비워 둔다.
   */
  async createSession(mode: ChatMode): Promise<ChatSession> {
    const created = await apiCreateSession(toApiMode(mode));
    const session = toSession(created);
    sessions = [session, ...sessions];
    notify();
    // 인사 메시지를 바로 띄우기 위해 이어서 받아온다(실패해도 대화 진입은 막지 않는다).
    this.loadMessages(session.id).catch(() => {});
    return session;
  },

  /** 이름 바꾸기 — 화면을 먼저 바꾸고 서버에 반영한다. 실패하면 되돌린다. */
  async renameSession(id: string, title: string): Promise<void> {
    const next = title.trim();
    if (!next) return;
    const previous = sessions.find((s) => s.id === id)?.title;
    replaceSession(id, (s) => ({ ...s, title: next }));
    try {
      await apiRenameSession(id, next);
    } catch (e) {
      if (previous !== undefined) replaceSession(id, (s) => ({ ...s, title: previous }));
      throw e;
    }
  },

  /** 지우기 — 목록에서 먼저 걷어내고, 실패하면 되돌린다. */
  async removeSession(id: string): Promise<void> {
    const previous = sessions;
    sessions = sessions.filter((s) => s.id !== id);
    notify();
    try {
      await apiDeleteSession(id);
    } catch (e) {
      sessions = previous;
      notify();
      throw e;
    }
  },

  /**
   * 질문 보내기. 말풍선을 먼저 띄우고(기다리는 동안 빈 화면이 되지 않게) 답변을 기다린다.
   *
   * 끝난 뒤 목록을 다시 받아오는 이유 — 답변 말풍선뿐 아니라 **서버가 정한 제목**도
   * 이때 확정된다(첫 질문으로 자동 저장). 화면이 따로 챙기지 않아도 되게 여기서 맞춘다.
   *
   * 되묻는 답변(NEEDS_CLARIFICATION)도 정상 답변이라 실패로 취급하지 않는다.
   */
  async sendText(id: string, text: string): Promise<ApiChatRun> {
    const body = text.trim();
    if (!body) throw new Error('보낼 내용이 없어요');

    const session = sessions.find((s) => s.id === id);
    const stylistMode =
      session?.responseMode === 'STYLIST' && session.selectedPersonaIds.length > 0;

    const draftId = nextMessageId();
    replaceSession(id, (s) => ({
      ...s,
      messages: [...s.messages, { id: draftId, role: 'user', kind: 'text', text: body }],
      updatedAt: Date.now(),
    }));

    const submitted = await apiSendMessage(id, body, newClientMessageId());

    /* 스타일리스트 모드면 답변을 기다리는 방식이 다르다 — 결과가 여러 개고 끝나는 시각이
       제각각이라, 다 끝날 때까지 묶어 두지 않고 끝난 카드부터 채운다. */
    const turn = stylistMode
      ? await runStylistTurn(id, submitted.run.id, session.selectedPersonaIds, body)
      : null;
    const run = turn ? turn.run : await waitForRun(submitted.run.id);

    // 답변이 생겼든 실패했든 서버가 가진 대화가 정답이다 — 통째로 다시 맞춘다.
    await this.loadMessages(id, { force: true }).catch(() => {});

    /* 카드는 답변 **뒤**에 와야 한다. 보낼 때는 그 답변 말풍선이 아직 없어서 임시로 끝에
       놓아 뒀고, 이제 서버 대화가 들어왔으니 마지막 말풍선 뒤로 옮긴다. */
    if (turn) reanchorOverlay(id, turn.overlayId, lastMessageId(id));

    /* 실패 사유는 run 에만 있고 대화에는 남지 않는다. 방금 보낸 질문의 오류 줄에만
       구체적인 사유를 채워 넣는다 — 다시 열면 일반 문구로 돌아간다(서버가 사유를 모르므로). */
    if (run.status === 'FAILED' && run.error_message) {
      const lineId = failureLineId(submitted.message.id);
      replaceSession(id, (s) => ({
        ...s,
        messages: s.messages.map((m) =>
          m.id === lineId && m.kind === 'error' ? { ...m, text: run.error_message } : m,
        ),
      }));
    }

    if (isAnswered(run.status)) {
      const fresh = await apiListSessions().catch(() => null);
      if (fresh) {
        const before = new Map(sessions.map((s) => [s.id, s]));
        sessions = sortByRecent(fresh.map((s) => toSession(s, before.get(s.id))));
        notify();
      }
    }
    return run;
  },

  /**
   * 사진 올리고 무드까지 읽어낸다. 올리기 → 분석 시작 → 분석 끝날 때까지 대기, 세 걸음이다.
   *
   * 중간에 한 번씩 대화를 다시 받아오는 이유 — 사진 말풍선은 올리자마자 보여야 하고,
   * 무드 카드는 분석이 끝나야 생긴다. 마지막에 한 번만 받아오면 사진이 늦게 뜬다.
   *
   * 분석이 실패해도 사진은 이미 대화에 남는다. 그래서 실패를 예외로 올려 화면이
   * 알리게 하되, 올린 사진까지 되돌리지는 않는다.
   */
  async attachPhoto(id: string, uri: string): Promise<void> {
    const uploaded = await apiUploadAttachment(id, { uri }, newClientMessageId());
    await this.loadMessages(id, { force: true }).catch(() => {});

    const started = await apiStartMoodAnalysis(id, uploaded.attachment.id);
    const run = await waitForRun(started.run.id);
    await this.loadMessages(id, { force: true }).catch(() => {});

    if (run.status === 'FAILED') {
      throw new Error(run.error_message || '사진에서 무드를 읽지 못했어요');
    }
  },

  /**
   * 읽어낸 무드를 추천 조건에 반영할지 정한다.
   *
   * ⚠️ 승인해도 **추천이 바로 만들어지지 않는다.** 세션 조건에만 반영되고, 다음 질문부터
   *    그 무드가 쓰인다. 그래서 화면은 승인 뒤에 무엇을 하면 되는지 알려줘야 한다.
   */
  async decideMood(id: string, attachmentId: string, decision: 'APPROVE' | 'REJECT'): Promise<void> {
    await apiDecideMood(id, attachmentId, decision);
    await this.loadMessages(id, { force: true });
  },

  /* ── 스타일리스트 모드 ───────────────────────────── */

  /**
   * 응답 모드 전환. 대화방을 옮기지도, 새로 만들지도 않는다 — **다음 질문부터** 달라진다.
   *
   * ⚠️ personaIds 를 **생략하면 서버가 복원한다**(세션 이전값 → 회원 마지막값 → minimal).
   *    빈 배열을 보내는 것과 다르니 "고른 게 없다"는 뜻으로 [] 를 넘기지 말 것.
   *
   * 바뀐 자리에는 구분선을 남긴다. 되돌아봤을 때 어디서부터 답하는 방식이 달라졌는지
   * 알 수 있어야 하기 때문이다. 아무것도 안 바뀌었으면 남기지 않는다.
   */
  async setResponseMode(
    id: string,
    mode: ApiResponseMode,
    personaIds?: StylistId[],
  ): Promise<void> {
    const before = sessions.find((s) => s.id === id);
    const updated = await apiUpdateResponseMode(id, mode, personaIds);
    const nextIds = updated.selected_persona_ids ?? [];

    const changed =
      before?.responseMode !== updated.response_mode ||
      (updated.response_mode === 'STYLIST' && !sameIds(before?.selectedPersonaIds ?? [], nextIds));

    replaceSession(id, (s) => ({
      ...s,
      responseMode: updated.response_mode,
      // 꺼도 선택값은 지우지 않는다 — 다시 켤 때 복원해야 한다.
      selectedPersonaIds: nextIds.length > 0 ? nextIds : s.selectedPersonaIds,
    }));

    if (!changed) return;
    const markId = nextMessageId();
    addOverlay(id, {
      id: markId,
      after: lastMessageId(id),
      message: {
        id: markId,
        role: 'ai',
        kind: 'mode',
        mode: updated.response_mode,
        names: updated.response_mode === 'STYLIST' ? stylistStore.displayNames(nextIds) : [],
      },
    });
  },

  /**
   * 실패한 스타일리스트 한 명만 다시 실행한다. 성공한 다른 카드는 그대로 남는다.
   * 같은 run 을 다시 폴링하되 **그 한 명만** 보고 기다린다 — 나머지는 이미 끝나 있어서
   * '전원 종료' 조건으로는 첫 폴링에 바로 빠져나온다.
   */
  async retryStylist(sessionId: string, runId: string, personaId: StylistId): Promise<void> {
    const overlayId = stylistOverlayId(runId);
    const current = overlaysOf(sessionId).find((o) => o.id === overlayId)?.message;
    if (current) {
      // 누른 것이 바로 보이게 먼저 대기 상태로 돌린다.
      updateOverlay(
        sessionId,
        overlayId,
        patchCard(current, personaId, (c) => ({ ...c, status: 'PENDING', errorText: null })),
      );
    }

    const accepted = await apiRetryPersona(runId, personaId);
    applyRunProgress(sessionId, runId, accepted.run);
    /* 몇 번째 재실행인지를 기준으로 삼는다. 상태만 보면 접수 직후 아직 안 바뀐 옛 FAILED 를
       보고 "벌써 끝났다"고 오해할 수 있다. */
    const target = accepted.run.results.find((r) => r.persona_id === personaId);
    const expected = target?.retry_count ?? 0;

    await waitForStylistRun(runId, {
      onProgress: (run) => applyRunProgress(sessionId, runId, run),
      until: (run) => {
        const r = run.results.find((x) => x.persona_id === personaId);
        if (!r) return true;
        return r.retry_count >= expected && (r.status === 'SUCCEEDED' || r.status === 'FAILED');
      },
    });
  },

  /**
   * 같은 스타일리스트에게 다른 코디를 받는다.
   * 기다리는 동안 **지금 카드는 그대로 둔다** — 없애 버리면 마음에 들던 코디를 놓치고,
   * 새 추천이 실패하면 남는 게 없다.
   */
  async alternativeStylist(
    sessionId: string,
    runId: string,
    personaId: StylistId,
  ): Promise<void> {
    const overlayId = stylistOverlayId(runId);
    const current = overlaysOf(sessionId).find((o) => o.id === overlayId)?.message;
    if (current) {
      updateOverlay(
        sessionId,
        overlayId,
        patchCard(current, personaId, (c) => ({ ...c, alternating: true })),
      );
    }

    const accepted = await apiRequestAlternative(runId, personaId);
    applyRunProgress(sessionId, runId, accepted.run);
    const target = accepted.run.results.find((r) => r.persona_id === personaId);
    const expected = target?.alternative_count ?? 0;

    await waitForStylistRun(runId, {
      onProgress: (run) => applyRunProgress(sessionId, runId, run),
      until: (run) => {
        const r = run.results.find((x) => x.persona_id === personaId);
        if (!r) return true;
        return (
          r.alternative_count >= expected &&
          r.alternative_status !== 'PENDING' &&
          r.alternative_status !== 'RUNNING'
        );
      },
    });
  },

  /** 고른 코디를 내 룩으로 저장한다. 화면을 먼저 바꾸고, 실패하면 되돌린다. */
  async saveStylistCard(sessionId: string, runId: string, personaId: StylistId): Promise<void> {
    const overlayId = stylistOverlayId(runId);
    const current = overlaysOf(sessionId).find((o) => o.id === overlayId)?.message;
    if (!current || current.kind !== 'stylist') return;
    const card = current.cards.find((c) => c.personaId === personaId);
    if (!card?.resultId || !card.cardId) throw new Error('아직 저장할 코디가 없어요');

    updateOverlay(sessionId, overlayId, patchCard(current, personaId, (c) => ({ ...c, saved: true })));
    try {
      await apiSaveCard(card.resultId, card.cardId);
    } catch (e) {
      const reverted = overlaysOf(sessionId).find((o) => o.id === overlayId)?.message;
      if (reverted) {
        updateOverlay(
          sessionId,
          overlayId,
          patchCard(reverted, personaId, (c) => ({ ...c, saved: false })),
        );
      }
      throw e;
    }
  },

  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

/* useSyncExternalStore 는 getSnapshot 이 매번 같은 참조를 주길 요구한다.
   loading·error 를 객체로 만들어 돌려주면 렌더마다 새 객체라 무한 루프가 된다.
   그래서 바뀔 때만 새로 만들어 둔다. */
let status: { loading: boolean; loadedOnce: boolean; error: string | null } = {
  loading: false,
  loadedOnce: false,
  error: null,
};
function setStatus() {
  if (status.loading !== loading || status.error !== error || status.loadedOnce !== loadedOnce) {
    status = { loading, loadedOnce, error };
  }
}

export function useChatSessions(): ChatSession[] {
  return useSyncExternalStore(chatStore.subscribe, chatStore.getSessions, chatStore.getSessions);
}

/** 목록 로딩·오류 상태. 빈 화면과 '못 불러옴'을 구분해 보여주기 위한 것. */
export function useChatStatus(): { loading: boolean; loadedOnce: boolean; error: string | null } {
  return useSyncExternalStore(chatStore.subscribe, chatStore.getStatus, chatStore.getStatus);
}

/** 세션 하나를 구독. 없는 id(삭제된 대화 등)면 undefined. */
export function useChatSession(id: string | undefined): ChatSession | undefined {
  const all = useChatSessions();
  return id ? all.find((s) => s.id === id) : undefined;
}

/** 가장 최근 대화 — id 없이 대화 화면으로 들어온 경우의 기본값. */
export function useLatestSession(): ChatSession | undefined {
  const all = useChatSessions();
  return sortByRecent(all)[0];
}

/**
 * 검색 결과 — 모드로 묶지 않고 최근 순 한 줄로 준다.
 * 찾는 사람은 '어느 모드였는지'가 아니라 '어느 대화였는지'를 좇는다.
 */
export function useSearchedSessions(query: string): ChatSession[] {
  const all = useChatSessions();
  return sortByRecent(all.filter((s) => sessionMatches(s, query)));
}

/** 모드별로 묶은 목록 — 각 모드 안에서는 최근 대화가 위로 온다. */
export function useChatGroups(): { mode: ChatMode; label: string; tint: string; sessions: ChatSession[] }[] {
  const all = useChatSessions();
  return CHAT_MODE_ORDER.map((mode) => ({
    mode,
    ...CHAT_MODE_META[mode],
    sessions: sortByRecent(all.filter((s) => s.mode === mode)),
  }));
}
