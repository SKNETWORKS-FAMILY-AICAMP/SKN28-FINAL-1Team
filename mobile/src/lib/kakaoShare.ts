/**
 * 공유 옷장 초대 — 카카오톡 공유.
 *
 * 모바일 앱은 카카오톡을 열고, PC 웹은 초대 문구만 복사한다.
 *
 * 플랫폼별로 SDK 가 갈린다 — 쓰는 키가 서로 다르기 때문이다.
 *   네이티브 : @react-native-kakao/share, **네이티브 앱 키**로 초기화(_layout 에서 1회)
 *   웹       : Kakao JS SDK, **JavaScript 키**로 Kakao.init
 * 웹에서 네이티브 앱 키로 init 하면 예외도 없이 조용히 실패한다. 이 파일이 존재하는
 * 이유의 절반이 그 실수를 다시 못 하게 하는 것이다.
 *
 * 어떤 경로로 가든 **먼저 클립보드에 초대 문구를 복사**한다. 카카오 공유가 막히거나
 * (도메인 미등록·카톡 미설치) 사용자가 다른 채팅방에 직접 붙여넣고 싶을 때
 * 손으로 코드를 옮겨 적지 않아도 되게 하기 위해서다.
 */
import type { KakaoFeedTemplate } from '@react-native-kakao/share';
import * as Clipboard from 'expo-clipboard';
import { Platform, Share } from 'react-native';

import { KAKAO_JAVASCRIPT_KEY } from '@/constants/config';

/** 카카오 JS SDK. 버전을 올릴 때 CDN 경로 형식도 함께 확인한다. */
const KAKAO_JS_SDK_SRC = 'https://t1.kakaocdn.net/kakao_js_sdk/2.8.0/kakao.min.js';

/** 공유 카드 대표 이미지. 카카오는 절대 URL 만 받는다(상대경로·data URI 불가). */
const INVITE_THUMBNAIL =
  'https://images.unsplash.com/photo-1540221652346-e5dd6b50f3e7?w=800&auto=format&fit=crop&q=60';

export type KakaoInvite = {
  /** 공유 옷장 이름 */
  roomName: string;
  /** 6자리 참여 코드 */
  code: string;
  /** 초대 수락 링크 (/invite?code=...) */
  link: string;
};

/**
 * 공유가 실제로 어떤 경로로 나갔는지 — 호출부가 토스트 문구를 고르는 데 쓴다.
 * `no-key`는 설정 누락이라 사용자가 아니라 **개발자가 고쳐야 하는** 실패다.
 * 이걸 'clipboard'와 뭉뚱그리면 "왜 카톡이 안 열리지"를 영원히 못 찾는다.
 */
export type KakaoShareResult =
  | 'kakao'
  | 'share-sheet'
  | 'clipboard'
  | 'no-key'
  | 'cancelled';

/** 웹에서 카카오 SDK를 쓸 수 있는 상태인지 (키가 번들에 실렸는지) */
export function isKakaoWebConfigured(): boolean {
  return Boolean(KAKAO_JAVASCRIPT_KEY);
}

/**
 * 카카오톡·다른 앱에 실려 나갈 본문.
 *
 * **URL 은 넣지 않는다.** 참여는 6자리 코드로만 받기로 했다 — 링크를 같이 뿌리면
 * 코드가 눈에 안 들어오고, 링크가 어디까지 퍼졌는지도 통제가 안 된다.
 * (링크 자체는 카카오 카드 버튼 목적지로만 내부에서 쓴다.)
 */
export function inviteMessage({ roomName, code }: KakaoInvite): string {
  return `[cozy] '${roomName}' 공유 옷장에 초대합니다!\n참여 코드: ${code}\n앱에서 '초대 코드로 참여'에 이 코드를 입력해 주세요.`;
}

/**
 * 텍스트 복사. 웹에서 두 번 시도한다.
 *
 * `navigator.clipboard`(expo-clipboard가 쓰는 것)는 **보안 컨텍스트에서만** 동작한다.
 * 실기기 테스트는 보통 `http://<PC-IP>:8081`로 붙는데 이건 보안 컨텍스트가 아니라
 * 그냥 실패한다 — 그래서 구식 execCommand 폴백을 남겨 둔다. 없으면 휴대폰 브라우저에서
 * 복사가 통째로 죽고, 사용자 눈에는 "눌러도 아무 일도 안 일어남"으로 보인다.
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    await Clipboard.setStringAsync(text);
    return true;
  } catch {
    /* 아래 폴백으로 */
  }

  if (Platform.OS !== 'web' || typeof document === 'undefined') return false;

  try {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

export function copyInviteMessage(invite: KakaoInvite): Promise<boolean> {
  return copyText(inviteMessage(invite));
}

/**
 * OS 공유 시트. 웹과 네이티브가 완전히 다른 API다.
 *
 * react-native 의 `Share.share` 는 **웹에서 동작하지 않는다**(react-native-web 미구현).
 * 그래서 웹은 Web Share API 를 직접 쓴다 — 다만 이것도 보안 컨텍스트 + 사용자 제스처가
 * 필요해서, 없으면 조용히 false 를 돌려주고 호출부가 클립보드로 내려가게 한다.
 */
export async function openShareSheet(message: string, title: string): Promise<boolean> {
  if (Platform.OS === 'web') {
    const nav = typeof navigator !== 'undefined' ? (navigator as Navigator & { share?: (d: ShareData) => Promise<void> }) : undefined;
    if (!nav?.share) return false;
    try {
      await nav.share({ title, text: message });
      return true;
    } catch {
      return false; // 사용자가 취소했거나 브라우저가 거부
    }
  }

  try {
    await Share.share({ message, title });
    return true;
  } catch {
    return false;
  }
}

/* ── 웹: Kakao JS SDK ─────────────────────────────────────────────── */

declare global {
  // eslint-disable-next-line no-var
  var Kakao: any;
}

/** 스크립트 로드는 한 번만 — 시트를 여러 번 열어도 <script> 가 쌓이지 않게 캐시한다. */
let webSdkReady: Promise<void> | null = null;

function loadKakaoJsSdk(): Promise<void> {
  if (webSdkReady) return webSdkReady;

  webSdkReady = new Promise<void>((resolve, reject) => {
    if (typeof window === 'undefined' || typeof document === 'undefined') {
      return reject(new Error('브라우저 환경이 아닙니다'));
    }
    if (!KAKAO_JAVASCRIPT_KEY) {
      return reject(new Error('EXPO_PUBLIC_KAKAO_JAVASCRIPT_KEY 가 비어 있습니다'));
    }

    const init = () => {
      try {
        if (!window.Kakao.isInitialized()) window.Kakao.init(KAKAO_JAVASCRIPT_KEY);
        resolve();
      } catch (e) {
        reject(e);
      }
    };

    if (window.Kakao) return init();

    // 같은 스크립트가 이미 붙어 있으면(핫리로드 등) 재사용한다.
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${KAKAO_JS_SDK_SRC}"]`,
    );
    const script = existing ?? document.createElement('script');
    script.addEventListener('load', init, { once: true });
    script.addEventListener('error', () => reject(new Error('Kakao SDK 로드 실패')), {
      once: true,
    });
    if (!existing) {
      script.src = KAKAO_JS_SDK_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
  }).catch((e) => {
    webSdkReady = null; // 실패는 캐시하지 않는다 — 다음 시도에서 다시 받아본다
    throw e;
  });

  return webSdkReady;
}

/* ── 공통 진입점 ──────────────────────────────────────────────────── */

/**
 * 카카오톡 공유 창을 연다. 성공하면 친구·채팅방을 고르는 화면이 뜬다.
 *
 * 실패하면 조용히 죽지 않고 단계적으로 물러난다:
 *   카카오 SDK → OS 공유 시트 → 클립보드 복사
 * 어느 단계든 초대 문구는 이미 클립보드에 있으므로 사용자가 직접 붙여넣을 수 있다.
 */
export async function shareInviteViaKakao(invite: KakaoInvite): Promise<KakaoShareResult> {
  const copied = await copyInviteMessage(invite);
  const message = inviteMessage(invite);

  // PC 웹에서는 카카오 창이나 OS 공유창을 열지 않는다. 사용자가 카카오톡 PC의
  // 원하는 대화방에 직접 붙여넣을 수 있도록 복사만 하는 것이 제품 정책이다.
  if (Platform.OS === 'web') return copied ? 'clipboard' : 'cancelled';

  /**
   * 링크 목적지.
   * - `mobileWebUrl`/`webUrl` : 앱이 없는 사람 → 웹 초대장(/invite?code=)
   * - `*ExecutionParams`      : 앱이 있는 사람 → 카카오톡이 앱을 직접 실행하고
   *   이 파라미터를 스킴 쿼리로 넘긴다. 받는 쪽은 hooks/use-kakao-link.ts.
   * 둘을 같이 넣어야 "설치자는 앱, 미설치자는 웹"이 한 카드로 갈린다.
   */
  const target = {
    mobileWebUrl: invite.link,
    webUrl: invite.link,
    androidExecutionParams: { code: invite.code },
    iosExecutionParams: { code: invite.code },
  };
  /** 피드 템플릿 본문. 웹 SDK 만 여기에 objectType 을 얹어 달라고 요구한다. */
  const template: KakaoFeedTemplate = {
    content: {
      title: `${invite.roomName} 공유 옷장 초대`,
      // 카드에서 제일 크게 읽혀야 하는 건 코드다 — 참여 수단이 코드 하나뿐이다.
      description: `참여 코드 ${invite.code}\n앱에서 이 코드를 입력하면 들어올 수 있어요.`,
      imageUrl: INVITE_THUMBNAIL,
      link: target,
    },
    buttons: [{ title: '초대 수락하기', link: target }],
  };

  try {
    // 동적 import: 카카오 공유는 네이티브 모듈이라 웹 번들에 끌려 들어가면 안 된다.
    const { shareFeedTemplate } = await import('@react-native-kakao/share');
    await shareFeedTemplate({
      template,
      // 카카오톡이 없으면 카카오 웹 공유 페이지로 대신 연다.
      useWebBrowserIfKakaoTalkNotAvailable: true,
    });
    return 'kakao';
  } catch (e) {
    if (__DEV__) console.warn('카카오 공유 실패 — 공유 시트로 대체합니다', e);
  }

  if (await openShareSheet(message, `${invite.roomName} 초대`)) return 'share-sheet';

  return copied ? 'clipboard' : 'cancelled';
}
