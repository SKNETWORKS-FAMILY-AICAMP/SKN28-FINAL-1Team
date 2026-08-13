import { useSyncExternalStore } from 'react';

import { Editorial } from '@/constants/theme';
import {
  createSession as apiCreateSession,
  deleteSession as apiDeleteSession,
  listMessages as apiListMessages,
  listSessions as apiListSessions,
  newClientMessageId,
  renameSession as apiRenameSession,
  sendMessage as apiSendMessage,
  type ApiChatMessage,
  type ApiChatMode,
  type ApiChatRun,
  type ApiChatSession,
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
  /** 첨부한 사진에서 읽어낸 무드 — 추구미로 삼을지 묻는 카드 */
  | { id: string; role: 'ai'; kind: 'mood'; tags: string[] }
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
    };

export type ChatSession = {
  id: string;
  mode: ChatMode;
  title: string;
  messages: ChatMessage[];
  /** 대화를 한 번이라도 열어 메시지를 받아왔는지. 목록만 받은 세션은 false 다. */
  messagesLoaded: boolean;
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
 * 서버 메시지 → 말풍선.
 * SYSTEM·TOOL 은 사람에게 보여줄 말이 아니라 버린다. 사진 첨부는 사진 말풍선을 따로 만들어
 * 글보다 앞에 놓는다 — 올릴 때 사진이 먼저였으니 다시 열어도 그 순서여야 한다.
 * 추천 카드는 말풍선 **뒤에** 붙는다 (먼저 말로 설명하고 그다음 코디를 보여주는 순서).
 */
function toMessages(api: ApiChatMessage, cards: ApiRecommendationCard[] = []): ChatMessage[] {
  if (api.role !== 'USER' && api.role !== 'ASSISTANT') return [];
  const role = api.role === 'USER' ? 'user' : 'ai';
  const out: ChatMessage[] = [];

  if (role === 'user') {
    for (const a of api.attachments) {
      out.push({ id: `${api.id}-a${a.id}`, role: 'user', kind: 'image', uri: a.image_url ?? undefined });
    }
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
    messagesLoaded: previous?.messagesLoaded ?? false,
    updatedAt: new Date(api.last_message_at || api.updated_at).getTime(),
  };
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

  /** 대화 내용 받아오기. 이미 받아둔 세션은 다시 부르지 않는다(force 로 강제). */
  async loadMessages(id: string, options: { force?: boolean } = {}): Promise<void> {
    const current = sessions.find((s) => s.id === id);
    if (!options.force && current?.messagesLoaded) return;
    const list = await apiListMessages(id);
    const cards = await fetchCards(list);
    replaceSession(id, (s) => ({
      ...s,
      messages: list.flatMap((m) => toMessages(m, cards.get(m.id))),
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
