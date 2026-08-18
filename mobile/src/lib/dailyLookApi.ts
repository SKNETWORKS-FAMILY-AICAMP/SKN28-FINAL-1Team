import { DailyLookEndpoint } from '@/constants/config';
import { api } from '@/lib/apiClient';

/**
 * 오늘의 룩 API 타입 — 백엔드 DailyLookSerializer(api/apps/recommend/serializers.py)와
 * 필드명을 맞춘다. 생성 전에도 200 으로 내려오며 status 로 분기한다.
 */
export type DailyLookStatus = 'QUEUED' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED' | 'EMPTY';

export type DailyLookItem = {
  item_key: string;
  name?: string;
  category?: string;
  sub_category?: string;
  layer_role?: string;
  color?: string;
  note?: string;
  /** 흰 배경 아이템 이미지 presigned URL — 조회마다 새로 서명되므로 캐시하면 만료된다 */
  image_url: string | null;
};

export type DailyLookResult = {
  headline: string;
  golden_id: string;
  rationale_ko: string;
  /**
   * 카드 태그. **룩북 필터와 같은 어휘**다 (백엔드 apps/lookbook/contracts.py 의
   * LOOKBOOK_TAGS 가 단일 정의이고, state/lookbook.ts 의 ALLOWED_HASHTAGS 와 같은 목록).
   * 골든 코디의 occasion·style 에서, 그것이 비면 사용자 추구미에서 뽑는다.
   * 하나도 못 만들면 빈 배열이며 그때는 태그 줄을 숨긴다 — 아이템 이름을 태그처럼
   * 보여주면(예전 방식) 같은 서비스 안에서 '태그'가 두 가지를 뜻하게 된다.
   */
  tags?: string[];
  styling_tips?: string[];
  /** 문장을 누가 썼는지: 'llm' | 'template' (template 이면 담백한 톤) */
  generated_by?: string;
  items?: DailyLookItem[];
  /** 정면 착용 이미지(대표). 생성 전/실패면 null — 그때는 items[].image_url 카드로 화면을 만든다 */
  render_image_url: string | null;
  /** 원본 코디 사진. 사용권이 열린 코디(exposable)에만 값이 있다 */
  outfit_image_url: string | null;
};

export type DailyLookContext = {
  weather: Record<string, unknown>;
  used_body: boolean;
  used_pursuit: boolean;
  body_profile: string;
  /** 판정하지 못한 치수 — "어깨너비를 입력하면 더 정확해져요" 안내에 쓸 수 있다 */
  missing_measurements: string[];
  candidate_count: number;
};

export type DailyLook = {
  look_id: string;
  look_date: string;
  status: DailyLookStatus;
  /** 생성이 끝나기 전(QUEUED/PROCESSING/EMPTY/FAILED)에는 null */
  result: DailyLookResult | null;
  context: DailyLookContext;
  /** QUEUED/PROCESSING 일 때만 값이 있다 — 이 간격(ms) 뒤에 다시 조회한다 */
  poll_after_ms: number | null;
  /** 상태별 사용자 안내 문구 (SUCCEEDED 면 null) */
  detail: string | null;
  created_at: string;
  updated_at: string;
};

/** 아직 결과가 없어 폴링을 계속해야 하는 상태 */
export function isDailyLookPending(look: DailyLook | null): boolean {
  return look?.status === 'QUEUED' || look?.status === 'PROCESSING';
}

/**
 * 화면이 그려야 할 단계. 홈 카드와 룩 상세가 같은 규칙을 쓰도록 여기 한 곳에 둔다.
 *
 * - `pending`: 아직 모르거나 만드는 중 → **스켈레톤**. 목업으로 채우지 않는다.
 *   완성된 추천처럼 보이는 자리채움은 몇 초 뒤 통째로 바뀌어 "가짜를 봤다"는 인상을 준다.
 * - `ready`: 실제 추천이 있다.
 * - `unavailable`: 후보 없음(EMPTY)·실패(FAILED)·폴링 포기(stalled) → 무엇을 하면
 *   되는지 안내한다. EMPTY 와 FAILED 는 안내가 달라야 해서 status 를 함께 본다.
 */
export type DailyLookPhase = 'pending' | 'ready' | 'unavailable';

export function dailyLookPhase(look: DailyLook | null, stalled = false): DailyLookPhase {
  if (look?.status === 'SUCCEEDED') return look.result ? 'ready' : 'unavailable';
  if (look == null || isDailyLookPending(look)) return stalled ? 'unavailable' : 'pending';
  return 'unavailable';
}

/**
 * 오늘의 룩 조회. 그날 첫 호출이면 백엔드가 생성을 걸고 QUEUED 로 응답한다
 * (홈 API 가 진입 시점에 선반영을 걸어 두므로 보통은 이미 만들어져 있다).
 * lat/lon 을 주면 그 위치의 날씨로 만든다 — 단, 생성은 하루 한 번이라
 * 이미 만들어진 뒤에 보낸 좌표는 반영되지 않는다.
 */
export function getTodayLook(coords?: { lat: number; lon: number }): Promise<DailyLook> {
  const qs = coords ? `?lat=${coords.lat}&lon=${coords.lon}` : '';
  return api.get<DailyLook>(`${DailyLookEndpoint}${qs}`);
}
