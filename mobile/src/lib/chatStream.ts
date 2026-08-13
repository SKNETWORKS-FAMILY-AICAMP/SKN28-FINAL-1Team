import { getRun, type ApiChatRun, type ApiRunStatus } from '@/lib/chatApi';

/**
 * 답변 run 이 끝날 때까지 기다린다.
 *
 * **왜 SSE 가 아니라 폴링인가.**
 * 백엔드는 /chat/runs/{id}/events/ 로 SSE 를 준다. 그런데 양쪽 플랫폼 모두 그대로는 못 쓴다.
 *   - 웹: 브라우저 `EventSource` 는 **커스텀 헤더를 못 붙인다**. 이 엔드포인트는 JWT 로
 *     소유자를 가리므로 Authorization 없이 열면 남의 run 으로 취급돼 404 가 난다.
 *     (쿠키 신원인 게스트라면 가능하지만 지금은 로그인 사용자만 붙인다.)
 *   - 네이티브: React Native 에 `EventSource` 자체가 없다.
 * 웹만 fetch 스트리밍으로 따로 파싱하는 길도 있지만, 그러면 플랫폼별로 갈라진 두 경로를
 * 각각 검증해야 한다. 답변이 보통 몇 초 안에 끝나는 작업이라 폴링 한 갈래로 통일한다.
 * (SSE 로 올리고 싶어지면 이 파일만 바꾸면 된다 — 부르는 쪽은 run 결과만 본다.)
 */

/** 더 기다려도 소용없는 상태들. NEEDS_CLARIFICATION 도 **정상 답변**이다(되묻는 것). */
const TERMINAL: ApiRunStatus[] = ['SUCCEEDED', 'NEEDS_CLARIFICATION', 'FAILED'];

export function isTerminal(status: ApiRunStatus): boolean {
  return TERMINAL.includes(status);
}

/** 답변이 실제로 생긴 경우. 화면은 이때 메시지를 다시 불러 말풍선을 채운다. */
export function isAnswered(status: ApiRunStatus): boolean {
  return status === 'SUCCEEDED' || status === 'NEEDS_CLARIFICATION';
}

/** 첫 몇 번은 촘촘히, 그 뒤엔 느슨하게. 대부분 5초 안에 끝나서 앞을 촘촘히 둔다. */
function delayFor(attempt: number): number {
  if (attempt < 5) return 700;
  if (attempt < 15) return 1500;
  return 3000;
}

/** 이만큼 지나도 안 끝나면 포기한다. 워커가 죽어 있으면 영영 PENDING 이라 상한이 필요하다. */
const TIMEOUT_MS = 120_000;

export class ChatRunTimeout extends Error {
  constructor() {
    super('답변이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요.');
    this.name = 'ChatRunTimeout';
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    }
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

/**
 * run 이 끝날 때까지 폴링하고 마지막 상태를 돌려준다.
 * 실패 run(FAILED)도 **예외가 아니라 값으로** 준다 — 화면이 오류 문구를 말풍선으로
 * 보여줄지 토스트로 띄울지 고를 수 있어야 해서다. 시간 초과만 예외로 던진다.
 */
export async function waitForRun(
  runId: string,
  options: { signal?: AbortSignal } = {},
): Promise<ApiChatRun> {
  const { signal } = options;
  const startedAt = Date.now();

  for (let attempt = 0; ; attempt += 1) {
    const run = await getRun(runId);
    if (isTerminal(run.status)) return run;

    if (Date.now() - startedAt > TIMEOUT_MS) throw new ChatRunTimeout();
    await sleep(delayFor(attempt), signal);
  }
}
