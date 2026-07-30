import { useSyncExternalStore } from 'react';

import { Editorial } from '@/constants/theme';

/**
 * 채팅 세션 — 목록(C1)·대화(C2)·모드 선택(C3)이 같은 출처를 봐야 하므로 여기로 모았다.
 * (예전엔 chat.tsx 가 정적 GROUPS 배열을, chat-conversation.tsx 가 정적 SEED 를 각자 들고 있어
 *  새 대화를 만들어도 목록이 그대로였고, 어떤 세션을 열든 같은 대화가 나왔다.)
 *
 * 저장은 아직 메모리(룩북·캘린더 스토어와 동일) — 백엔드가 붙으면 이 스토어의 함수만 API 호출로 바꾼다.
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

/**
 * 한 개의 말풍선.
 * 타이핑 표시(···)는 저장하지 않는다 — 답변을 기다리는 '지금'만의 상태라
 * 대화를 다시 열었을 때 남아 있으면 안 된다. 화면 쪽 지역 상태로 둔다.
 */
export type ChatMessage =
  | { id: string; role: 'ai' | 'user'; kind: 'text'; text: string }
  | { id: string; role: 'user'; kind: 'image' }
  | { id: string; role: 'ai'; kind: 'rec'; title: string; tags: string[] };

export type ChatSession = {
  id: string;
  mode: ChatMode;
  title: string;
  messages: ChatMessage[];
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
  if (!last) return '아직 대화가 없어요';
  if (last.kind === 'text') return last.text.replace(/\n/g, ' ');
  if (last.kind === 'rec') return `추천 · ${last.title}`;
  return '사진을 보냈어요';
}

/* ── 시드 ─────────────────────────────────────────────
   데모용 지난 대화. 시각은 모듈이 로드된 시점 기준으로 벌려 둔다. */
const seededAt = Date.now();

const SEED_SESSIONS: ChatSession[] = [
  {
    id: 'seed-1',
    mode: 'taste',
    title: '가을 데일리 미니멀',
    updatedAt: seededAt,
    messages: [
      {
        id: 'seed-1-1',
        role: 'ai',
        kind: 'text',
        text: '안녕하세요 코지님! 오늘 서울은 8도로 쌀쌀해요.\n미니멀한 무드로 따뜻한 코디 골라봤어요.',
      },
      { id: 'seed-1-2', role: 'user', kind: 'text', text: '출근할 때 입을 거예요' },
      {
        id: 'seed-1-3',
        role: 'ai',
        kind: 'rec',
        title: '포근한 니트 오피스룩',
        tags: ['니트', '슬랙스', '로퍼'],
      },
      { id: 'seed-1-4', role: 'ai', kind: 'text', text: '이 니트에 슬랙스 매치 어때요?' },
    ],
  },
  {
    id: 'seed-2',
    mode: 'taste',
    title: '면접룩 추천',
    updatedAt: seededAt - DAY,
    messages: [
      {
        id: 'seed-2-1',
        role: 'ai',
        kind: 'text',
        text: '면접은 언제인가요? 업종도 알려주시면 톤을 맞춰드려요.',
      },
      { id: 'seed-2-2', role: 'user', kind: 'text', text: '다음 주 금요일, 금융권이에요' },
      { id: 'seed-2-3', role: 'ai', kind: 'text', text: '차분한 네이비 코디로 정리했어요' },
    ],
  },
  {
    id: 'seed-3',
    mode: 'closet',
    title: '내 트렌치로 코디',
    updatedAt: seededAt - 2 * DAY,
    messages: [
      { id: 'seed-3-1', role: 'user', kind: 'text', text: '트렌치 코트 어떻게 입으면 좋을까요?' },
      { id: 'seed-3-2', role: 'ai', kind: 'text', text: '보유하신 트렌치 3가지로 제안해요' },
    ],
  },
  {
    id: 'seed-4',
    mode: 'closet',
    title: '주말 브런치룩',
    updatedAt: seededAt - 3 * DAY,
    messages: [
      { id: 'seed-4-1', role: 'user', kind: 'text', text: '주말 브런치 갈 때 편한 룩 있을까요?' },
      { id: 'seed-4-2', role: 'ai', kind: 'text', text: '데님에 로퍼로 캐주얼하게' },
    ],
  },
];

let sessions: ChatSession[] = [...SEED_SESSIONS];
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

/** 최근 대화가 위로. 목록·검색이 모두 이 순서를 쓴다. */
function sortByRecent(list: ChatSession[]): ChatSession[] {
  return [...list].sort((a, b) => b.updatedAt - a.updatedAt);
}

let messageSeq = 0;

/** 말풍선 id — 같은 밀리초에 여러 개가 추가돼도 겹치지 않게 순번을 붙인다. */
export function nextMessageId(): string {
  return `m${Date.now()}-${++messageSeq}`;
}

export const chatStore = {
  getSessions: () => sessions,
  getSession: (id: string | undefined) =>
    id ? sessions.find((s) => s.id === id) : undefined,

  /** 새 대화. 제목은 첫 답변이 오기 전까지의 임시 이름이다. */
  createSession(mode: ChatMode): ChatSession {
    const session: ChatSession = {
      id: String(Date.now()),
      mode,
      title: '새 대화',
      messages: [],
      updatedAt: Date.now(),
    };
    sessions = [session, ...sessions];
    notify();
    return session;
  },

  renameSession(id: string, title: string) {
    const next = title.trim();
    if (!next) return;
    sessions = sessions.map((s) => (s.id === id ? { ...s, title: next } : s));
    notify();
  },

  removeSession(id: string) {
    sessions = sessions.filter((s) => s.id !== id);
    notify();
  },

  /**
   * 대화 내용 교체. 목록의 미리보기·시각이 여기서 갱신된다.
   * 화면이 통째로 넘기는 이유 — 말풍선 추가/타이핑 제거가 한 번의 갱신으로 끝나야
   * 목록이 중간 상태를 보지 않는다.
   */
  setMessages(id: string, messages: ChatMessage[]) {
    sessions = sessions.map((s) =>
      s.id === id ? { ...s, messages, updatedAt: Date.now() } : s,
    );
    notify();
  },

  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

export function useChatSessions(): ChatSession[] {
  return useSyncExternalStore(chatStore.subscribe, chatStore.getSessions, chatStore.getSessions);
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
