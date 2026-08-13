import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';

import { Editorial } from '@/constants/theme';
import {
  createSession as apiCreateSession,
  decideMood as apiDecideMood,
  deleteSession as apiDeleteSession,
  listSessions as apiListSessions,
  newClientMessageId,
  pageMessages as apiPageMessages,
  renameSession as apiRenameSession,
  requestMoodAnalysis as apiRequestMoodAnalysis,
  searchSessions as apiSearchSessions,
  sendMessage as apiSendMessage,
  uploadPhoto as apiUploadPhoto,
  type ApiChatMessage,
  type ApiChatMode,
  type ApiChatRun,
  type ApiChatSession,
  type ApiChatSessionSearchItem,
  type ApiMoodDecision,
  type ApiMoodDecisionInput,
} from '@/lib/chatApi';
import { isAnswered, waitForRun } from '@/lib/chatStream';
import {
  getRecommendationResult,
  imageUrlOf,
  type ApiRecommendationCard,
} from '@/lib/recommendApi';

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
  /**
   * 첨부한 사진에서 읽어낸 무드 — 추구미로 삼을지 묻는 카드.
   * `decision` 이 UNDECIDED 일 때만 고를 수 있다. 서버가 첫 결정만 받으므로 번복은 없다.
   */
  | {
      id: string;
      role: 'ai';
      kind: 'mood';
      /** 승인·거절을 보낼 대상. 카드를 만든 첨부 사진이다. */
      attachmentId: string;
      tags: string[];
      decision: ApiMoodDecision;
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
      /** 카드 상세·피드백·이미지 API 를 부를 때 쓰는 두 값 (/rec-card 로 넘긴다). */
      resultId: string;
      cardId: string;
      title: string;
      tags: string[];
      items: RecItem[];
      /** 새로 사야 하는 상품 합계. 옷장 옷만으로 짠 코디면 0 이라 표시하지 않는다. */
      totalPrice: number | null;
      warnings: string[];
    };

export type ChatSession = {
  id: string;
  mode: ChatMode;
  title: string;
  messages: ChatMessage[];
  /** 대화를 한 번이라도 열어 메시지를 받아왔는지. 목록만 받은 세션은 false 다. */
  messagesLoaded: boolean;
  /**
   * 더 오래된 메시지를 받아올 커서. null 이면 처음까지 다 받았다는 뜻이다.
   * 화면은 이 값으로 '이전 대화 더 보기'를 그릴지 정한다.
   */
  olderCursor: string | null;
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

/* 검색은 서버가 한다 (useSessionSearch). 앱이 받아둔 대화만 훑으면 한 번도 열지 않은
   대화가 제목으로만 걸려, 사용자에게는 "분명 그 말을 했는데 안 찾아진다"로 보인다. */

/* ── 서버 응답 옮기기 ───────────────────────────────── */

function toRecMessage(
  messageId: string,
  resultId: string,
  card: ApiRecommendationCard,
): ChatMessage {
  return {
    id: `${messageId}-r${card.card_id}`,
    role: 'ai',
    kind: 'rec',
    resultId,
    cardId: card.card_id,
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

function metaString(api: ApiChatMessage, key: string): string {
  const value = api.metadata?.[key];
  return typeof value === 'string' ? value : '';
}

/** 사진 무드 결정 상태는 **첨부**에 붙어 있다(무드 카드를 만든 AI 메시지가 아니라). */
function decisionsOf(list: ApiChatMessage[]): Map<string, ApiMoodDecision> {
  const map = new Map<string, ApiMoodDecision>();
  for (const message of list) {
    for (const attachment of message.attachments) {
      map.set(attachment.id, attachment.mood_decision ?? 'UNDECIDED');
    }
  }
  return map;
}

/**
 * 사진 분석 답변 → 무드 카드.
 * 서버가 붙인 message_kind='mood' 로 알아본다. 태그가 비어 있으면 물어볼 것이 없으니
 * 카드를 만들지 않고 서버가 쓴 문장을 그대로 말풍선으로 보여준다.
 */
function toMoodMessage(
  api: ApiChatMessage,
  decisions: Map<string, ApiMoodDecision>,
): ChatMessage | null {
  if (metaString(api, 'message_kind') !== 'mood') return null;
  const attachmentId = metaString(api, 'attachment_id');
  const rawTags = (api.metadata?.mood_analysis as { tags?: unknown } | undefined)?.tags;
  const tags = Array.isArray(rawTags)
    ? rawTags.filter((tag): tag is string => typeof tag === 'string' && tag.length > 0)
    : [];
  if (!attachmentId || tags.length === 0) return null;
  return {
    id: api.id,
    role: 'ai',
    kind: 'mood',
    attachmentId,
    tags,
    decision: decisions.get(attachmentId) ?? 'UNDECIDED',
  };
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
  decisions: Map<string, ApiMoodDecision> = new Map(),
): ChatMessage[] {
  if (api.role !== 'USER' && api.role !== 'ASSISTANT') return [];
  const role = api.role === 'USER' ? 'user' : 'ai';
  const out: ChatMessage[] = [];

  /* 무드 카드는 말풍선을 대신한다 — 서버 문장("…무드가 보여요. 반영할까요?")과 카드가
     같은 말을 하므로 둘 다 그리면 같은 질문이 두 번 나온다. */
  if (role === 'ai') {
    const mood = toMoodMessage(api, decisions);
    if (mood) return [mood];
  }

  if (role === 'user') {
    for (const a of api.attachments) {
      out.push({ id: `${api.id}-a${a.id}`, role: 'user', kind: 'image', uri: a.image_url ?? undefined });
    }
  }
  const text = api.content.trim();
  if (text) out.push({ id: api.id, role, kind: 'text', text });
  /* 카드가 있다는 건 이 답변에 추천 id 가 붙어 있다는 뜻이다(카드를 그걸로 받아왔다).
     상세·피드백 API 가 result 와 card 둘 다 요구해서 카드에 함께 실어 둔다. */
  const resultId = recommendationIdOf(api);
  if (resultId) {
    for (const card of cards) out.push(toRecMessage(api.id, resultId, card));
  }

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
    messagesLoaded: previous?.messagesLoaded ?? false,
    olderCursor: previous?.olderCursor ?? null,
    updatedAt: new Date(api.last_message_at || api.updated_at).getTime(),
  };
}

/* ── 받아둔 원본 ─────────────────────────────────────
   말풍선(ChatMessage)만 들고 있으면 페이지를 이어 붙일 수 없다 — 말풍선에는 sequence 가
   없어서 "어디까지 이미 갖고 있는지"를 알 수 없고, 서버 메시지 하나가 말풍선 여러 개로
   갈라지기도 한다. 그래서 서버가 준 모양 그대로 세션별로 보관하고, 화면용 말풍선은
   여기서 매번 다시 만든다(rebuild). */
const rawMessages = new Map<string, ApiChatMessage[]>();
const rawCards = new Map<string, Map<string, ApiRecommendationCard[]>>();

/** 한 번에 받아올 메시지 수. 서버 상한은 100이다. */
const MESSAGE_PAGE_SIZE = 50;
/** 검색 한 페이지. 서버 상한은 50이다. */
const SEARCH_PAGE_SIZE = 20;

/** 한 세션의 원본을 지운다. 대화를 지웠을 때 남겨두면 같은 id 가 다시 생겨도 옛 내용이 붙는다. */
function forgetRaw(id: string): void {
  rawMessages.delete(id);
  rawCards.delete(id);
}

/** 받아둔 원본 → 말풍선. 페이지를 더 받거나 결정이 바뀔 때마다 다시 만든다. */
function rebuild(id: string): void {
  const list = rawMessages.get(id) ?? [];
  const cards = rawCards.get(id) ?? new Map<string, ApiRecommendationCard[]>();
  const decisions = decisionsOf(list);
  replaceSession(id, (s) => ({
    ...s,
    messages: list.flatMap((m) => toMessages(m, cards.get(m.id), decisions)),
    messagesLoaded: true,
  }));
}

/**
 * 새로 받은 페이지를 이미 갖고 있던 원본에 합친다.
 *
 * sequence 로 겹치는 구간을 걷어내고 순서대로 다시 세운다. 재전송·재조회로 같은 메시지가
 * 두 번 오는 일이 있고(질문을 보낸 뒤 최신 페이지를 다시 받는다), 그때 말풍선이 두 벌
 * 생기면 대화가 반복된 것처럼 보인다.
 */
function mergeRaw(id: string, incoming: ApiChatMessage[]): void {
  const arrived = new Set(incoming.map((m) => m.sequence));
  const merged = [
    ...(rawMessages.get(id) ?? []).filter((m) => !arrived.has(m.sequence)),
    ...incoming,
  ].sort((a, b) => a.sequence - b.sequence);
  rawMessages.set(id, merged);
}

function mergeCards(id: string, incoming: Map<string, ApiRecommendationCard[]>): void {
  const current = rawCards.get(id) ?? new Map<string, ApiRecommendationCard[]>();
  for (const [messageId, cards] of incoming) current.set(messageId, cards);
  rawCards.set(id, current);
}

/**
 * 새로 받은 최근 묶음이 이미 갖고 있는 구간과 이어지는지.
 *
 * 대화를 열어 최근 50개를 받아둔 뒤 다른 기기에서 50개 넘게 오갔다면, 다시 받은 최근
 * 50개는 갖고 있던 것보다 **한참 뒤**라 사이에 못 받은 메시지가 생긴다. 그걸 그냥 이어
 * 붙이면 대화 중간이 조용히 비어버린다 — 사용자에게는 안 한 말을 한 것처럼 보인다.
 */
function canStitch(id: string, incoming: ApiChatMessage[]): boolean {
  const held = rawMessages.get(id) ?? [];
  if (held.length === 0 || incoming.length === 0) return false;
  return incoming[0].sequence <= held[held.length - 1].sequence + 1;
}

/* ── 스토어 ─────────────────────────────────────────── */

let sessions: ChatSession[] = [];
let loading = false;
let error: string | null = null;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

/** 최근 대화가 위로. 목록·검색이 모두 이 순서를 쓴다. */
function sortByRecent(list: ChatSession[]): ChatSession[] {
  return [...list].sort((a, b) => b.updatedAt - a.updatedAt);
}

function replaceSession(id: string, patch: (s: ChatSession) => ChatSession) {
  sessions = sessions.map((s) => (s.id === id ? patch(s) : s));
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

/**
 * 목록을 다시 받아 서버가 정한 제목·순서에 맞춘다.
 * 실패해도 대화는 이미 화면에 있으니 조용히 넘어간다.
 */
async function syncSessionList(): Promise<void> {
  const fresh = await apiListSessions().catch(() => null);
  if (!fresh) return;
  const before = new Map(sessions.map((s) => [s.id, s]));
  sessions = sortByRecent(fresh.map((s) => toSession(s, before.get(s.id))));
  notify();
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
      setStatus();
      notify();
    }
  },

  /**
   * 대화 내용 받아오기 — **최근 한 묶음**만 받는다. 이미 받아둔 세션은 건너뛴다(force 로 강제).
   *
   * 전체를 한 번에 받던 때는 대화가 길어질수록 열 때마다 느려졌고, 첨부·추천이 붙은
   * 메시지는 카드 조회까지 그만큼 늘어났다. 더 예전 대화는 화면에서 눌러 받아온다
   * (loadOlderMessages).
   *
   * force 로 다시 받아도 이미 받아둔 예전 페이지는 지우지 않는다 — 질문 하나 보낼 때마다
   * 스크롤이 최근 묶음으로 잘려나가면 방금 읽던 자리를 잃는다.
   */
  async loadMessages(id: string, options: { force?: boolean } = {}): Promise<void> {
    const current = sessions.find((s) => s.id === id);
    if (!options.force && current?.messagesLoaded) return;

    const page = await apiPageMessages(id, { limit: MESSAGE_PAGE_SIZE });
    const cards = await fetchCards(page.items);

    if (canStitch(id, page.items)) {
      /* 이미 갖고 있던 구간과 이어진다. 그때의 커서가 여전히 '그보다 더 오래된' 자리를
         가리키므로 그대로 둔다 — 이번 응답의 커서는 최근 묶음 기준이라 덮어쓰면 중간이 빈다. */
      mergeCards(id, cards);
      mergeRaw(id, page.items);
    } else {
      /* 이어지지 않는다 = 갖고 있던 구간과 이번 묶음 사이에 못 받은 메시지가 있다
         (다른 기기에서 한참 대화했을 때). 중간이 빈 대화를 보여주느니 최근 묶음만
         남기고 '이전 대화 더 보기'로 되돌린다. */
      rawMessages.set(id, page.items);
      rawCards.set(id, cards);
      replaceSession(id, (s) => ({ ...s, olderCursor: page.next_cursor ?? null }));
    }
    rebuild(id);
  },

  /** '이전 대화 더 보기'. 커서가 없으면(처음까지 다 받았으면) 아무 일도 하지 않는다. */
  async loadOlderMessages(id: string): Promise<void> {
    const cursor = sessions.find((s) => s.id === id)?.olderCursor;
    if (!cursor) return;
    const page = await apiPageMessages(id, {
      limit: MESSAGE_PAGE_SIZE,
      cursor,
    });
    mergeCards(id, await fetchCards(page.items));
    mergeRaw(id, page.items);
    replaceSession(id, (s) => ({ ...s, olderCursor: page.next_cursor ?? null }));
    rebuild(id);
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
      forgetRaw(id);
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

    const draftId = nextMessageId();
    replaceSession(id, (s) => ({
      ...s,
      messages: [...s.messages, { id: draftId, role: 'user', kind: 'text', text: body }],
      updatedAt: Date.now(),
    }));

    const submitted = await apiSendMessage(id, body, newClientMessageId());
    const run = await waitForRun(submitted.run.id);

    // 답변이 생겼든 실패했든 서버가 가진 대화가 정답이다 — 통째로 다시 맞춘다.
    await this.loadMessages(id, { force: true }).catch(() => {});

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

    if (isAnswered(run.status)) await syncSessionList();
    return run;
  },

  /**
   * 사진 보내기. **업로드 → 무드 분석 접수 → 결과 대기** 세 단계다.
   * 올리기만 하면 서버는 아무것도 하지 않는다(analysis_status 가 NOT_REQUESTED 로 남는다).
   *
   * 답변은 무드 카드로 온다 — 사진에서 읽은 태그를 추천 조건으로 쓸지 되묻는 것이라,
   * 사용자가 카드에서 고르기 전까지는 추천 조건이 바뀌지 않는다.
   */
  async sendPhoto(id: string, uri: string): Promise<ApiChatRun> {
    const draftId = nextMessageId();
    replaceSession(id, (s) => ({
      ...s,
      messages: [...s.messages, { id: draftId, role: 'user', kind: 'image', uri }],
      updatedAt: Date.now(),
    }));

    try {
      const uploaded = await apiUploadPhoto(id, uri, newClientMessageId());
      const submitted = await apiRequestMoodAnalysis(id, uploaded.attachment.id);
      const run = await waitForRun(submitted.run.id);

      // 사진 말풍선의 진짜 주소(presigned)와 무드 카드는 서버가 가진 대화에서 온다.
      await this.loadMessages(id, { force: true }).catch(() => {});

      if (run.status === 'FAILED' && run.error_message) {
        const lineId = failureLineId(uploaded.message.id);
        replaceSession(id, (s) => ({
          ...s,
          messages: s.messages.map((m) =>
            m.id === lineId && m.kind === 'error' ? { ...m, text: run.error_message } : m,
          ),
        }));
      }
      if (isAnswered(run.status)) await syncSessionList();
      return run;
    } catch (e) {
      /* 사진이 이미 올라갔을 수 있으니 서버 상태로 맞춘다. 그것도 안 되면 방금 띄운 사진
         말풍선만 걷어낸다 — 올라가지 않은 사진이 보낸 것처럼 남아 있으면 안 된다. */
      const synced = await this.loadMessages(id, { force: true }).then(
        () => true,
        () => false,
      );
      if (!synced) {
        replaceSession(id, (s) => ({
          ...s,
          messages: s.messages.filter((m) => m.id !== draftId),
        }));
      }
      throw e;
    }
  },

  /**
   * 무드 카드의 두 버튼.
   * APPROVE 면 사진에서 읽은 표준 태그가 세션 추천 조건에 들어가고, REJECT 면 분석 기록만
   * 남는다. 서버가 **첫 결정만** 받으므로(번복하면 409) 카드도 한 번만 바뀐다.
   */
  async decideMood(
    sessionId: string,
    attachmentId: string,
    decision: ApiMoodDecisionInput,
  ): Promise<void> {
    const result = await apiDecideMood(sessionId, attachmentId, decision);
    const decided: ApiMoodDecision =
      result.attachment.mood_decision ?? (decision === 'APPROVE' ? 'APPROVED' : 'REJECTED');
    /* 결정은 첨부에 달려 있다. 말풍선만 고치면 페이지를 더 받아 다시 그릴 때(rebuild)
       서버에서 온 옛 값으로 되돌아가 버튼이 되살아난다. */
    const list = rawMessages.get(sessionId);
    if (list) {
      rawMessages.set(
        sessionId,
        list.map((message) => ({
          ...message,
          attachments: message.attachments.map((attachment) =>
            attachment.id === attachmentId
              ? { ...attachment, mood_decision: decided }
              : attachment,
          ),
        })),
      );
    }
    rebuild(sessionId);
  },

  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

/* useSyncExternalStore 는 getSnapshot 이 매번 같은 참조를 주길 요구한다.
   loading·error 를 객체로 만들어 돌려주면 렌더마다 새 객체라 무한 루프가 된다.
   그래서 바뀔 때만 새로 만들어 둔다. */
let status: { loading: boolean; error: string | null } = { loading: false, error: null };
function setStatus() {
  if (status.loading !== loading || status.error !== error) status = { loading, error };
}

export function useChatSessions(): ChatSession[] {
  return useSyncExternalStore(chatStore.subscribe, chatStore.getSessions, chatStore.getSessions);
}

/** 목록 로딩·오류 상태. 빈 화면과 '못 불러옴'을 구분해 보여주기 위한 것. */
export function useChatStatus(): { loading: boolean; error: string | null } {
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

/** 검색 결과 한 줄. preview 는 검색어가 걸린 메시지이고, 제목만 걸렸으면 비어 있다. */
export type SearchedSession = {
  session: ChatSession;
  preview: string;
};

export type SessionSearchState = {
  items: SearchedSession[];
  /** 서버가 센 전체 건수. 지금 받아온 items 보다 클 수 있다. */
  totalCount: number;
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  loadMore: () => void;
};

/** 사용자가 글자를 칠 때마다 서버를 부르지 않도록 잠깐 기다린다. */
const SEARCH_DEBOUNCE_MS = 300;

function toSearched(item: ApiChatSessionSearchItem): SearchedSession {
  return {
    // 이미 받아둔 세션이 있으면 그 대화 내용을 유지한 채 제목·시각만 새로 맞춘다.
    session: toSession(item, sessions.find((s) => s.id === item.id)),
    preview: item.search_match?.preview ?? '',
  };
}

/**
 * 서버에서 대화를 찾는다 — 제목뿐 아니라 **저장된 메시지 본문**까지 걸린다.
 *
 * 검색어가 바뀌면 첫 페이지부터 다시 받는다. 서버가 커서에 검색어를 함께 서명해 두기
 * 때문이기도 하고, 이전 검색 결과가 남아 있으면 새 검색어의 결과처럼 읽히기 때문이다.
 *
 * 응답이 늦게 도착해 순서가 뒤집히는 일이 있어(짧은 검색어일수록 결과가 많아 느리다)
 * 요청마다 번호를 매기고 **마지막 요청의 응답만** 반영한다.
 */
export function useSessionSearch(query: string): SessionSearchState {
  const trimmed = query.trim();
  const [items, setItems] = useState<SearchedSession[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    if (!trimmed) {
      requestId.current += 1; // 진행 중인 검색의 응답을 버린다
      setItems([]);
      setTotalCount(0);
      setCursor(null);
      setLoading(false);
      setError(null);
      return;
    }

    const current = ++requestId.current;
    setLoading(true);
    setError(null);
    const timer = setTimeout(() => {
      apiSearchSessions(trimmed, { limit: SEARCH_PAGE_SIZE })
        .then((page) => {
          if (requestId.current !== current) return;
          setItems(page.items.map(toSearched));
          setTotalCount(page.total_count);
          setCursor(page.next_cursor ?? null);
        })
        .catch((e) => {
          if (requestId.current !== current) return;
          setError(messageOf(e, '검색하지 못했어요'));
          setItems([]);
          setTotalCount(0);
          setCursor(null);
        })
        .finally(() => {
          if (requestId.current === current) setLoading(false);
        });
    }, SEARCH_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [trimmed]);

  const loadMore = useCallback(() => {
    if (!cursor || loading || !trimmed) return;
    const current = ++requestId.current;
    setLoading(true);
    apiSearchSessions(trimmed, { limit: SEARCH_PAGE_SIZE, cursor })
      .then((page) => {
        if (requestId.current !== current) return;
        setItems((previous) => [...previous, ...page.items.map(toSearched)]);
        setTotalCount(page.total_count);
        setCursor(page.next_cursor ?? null);
      })
      .catch((e) => {
        // 이미 보여준 결과는 남긴다 — 다음 페이지를 못 받았다고 앞 페이지까지 지우지 않는다.
        if (requestId.current === current) setError(messageOf(e, '더 불러오지 못했어요'));
      })
      .finally(() => {
        if (requestId.current === current) setLoading(false);
      });
  }, [cursor, loading, trimmed]);

  return { items, totalCount, loading, error, hasMore: cursor !== null, loadMore };
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
