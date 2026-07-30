/**
 * 아직 백엔드가 없는 옷 목록의 목업.
 *
 * ⚠️ **내 옷장(CLOSET_ITEMS)은 더 이상 화면이 쓰지 않는다** — 옷장 화면과 캘린더 '옷 고르기'는
 * 실 API(hooks/use-wardrobe.ts)를 본다. 남겨 둔 이유는 캘린더 시드 기록이 이 배열을 참조하기
 * 때문이다(state/calendar.ts). 착장 기록이 서버로 옮겨가면 함께 지운다.
 *
 * SHARED_CLOSET_ITEMS(친구 옷장)·LIBRARY_ITEMS(앱 카탈로그)는 백엔드가 아직 없어 계속 목업이다.
 */

/** 옷이 어디서 왔는지 — 캘린더 기록은 소스까지 함께 저장한다 */
export type WardrobeSource = 'closet' | 'library' | 'shared';

export type WardrobeItem = {
  id: string;
  name: string;
  category: string;
  tone: number;
  /** 공유 옷장 아이템의 주인 */
  owner?: string;
  /** 앱 카탈로그 아이템의 브랜드 */
  brand?: string;
  image?: string;
};

/** 내 옷장 */
export const CLOSET_ITEMS: WardrobeItem[] = [
  {
    id: '1',
    name: '연두 나시',
    category: '상의',
    tone: 0.05,
    image: 'https://i.pinimg.com/1200x/3e/04/ea/3e04eaa53146fd9bf93736707fffcb4f.jpg',
  },
  {
    id: '2',
    name: '연노랑 반팔 가디건',
    category: '아우터',
    tone: 0.22,
    image: 'https://i.pinimg.com/736x/a5/22/df/a522dfff1a759163fae0616ec0cab583.jpg',
  },
  {
    id: '3',
    name: '버뮤다 팬츠',
    category: '하의',
    tone: 0.16,
    image: 'https://i.pinimg.com/1200x/14/64/d4/1464d4e315aa8e7df53bb6c74fc31e59.jpg',
  },
  {
    id: '4',
    name: '아디다스 스니커즈',
    category: '신발',
    tone: 0.24,
    image: 'https://i.pinimg.com/736x/6e/ce/fa/6ecefa13347d6487fc30c0fda287d4dd.jpg',
  },
  {
    id: '5',
    name: '모자',
    category: '하의',
    tone: 0.08,
    image: 'https://i.pinimg.com/736x/ef/fa/96/effa960f41d4e20b7a0e31253732d75e.jpg',
  },
  {
    id: '6',
    name: '체크 가방',
    category: '가방',
    tone: 0.3,
    image: 'https://i.pinimg.com/1200x/39/32/c4/3932c44dead7e38ad916ef2e8cc2902f.jpg',
  },
];

/** 함께 쓰는 옷장 — 스페이스 멤버들의 옷 */
export const SHARED_CLOSET_ITEMS: WardrobeItem[] = [
  {
    id: 's1',
    name: '카멜 오버 코트',
    category: '아우터',
    tone: 0.12,
    owner: '지민',
    image: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400&h=500&fit=crop',
  },
  {
    id: 's2',
    name: '플리츠 미디 스커트',
    category: '하의',
    tone: 0.07,
    owner: '서연',
    image: 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=400&h=500&fit=crop',
  },
  {
    id: 's3',
    name: '체크 오버 셔츠',
    category: '상의',
    tone: 0.18,
    owner: '민준',
    image: 'https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=400&h=500&fit=crop',
  },
  {
    id: 's4',
    name: '스웨이드 첼시 부츠',
    category: '신발',
    tone: 0.26,
    owner: '지민',
    image: 'https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&h=500&fit=crop',
  },
  {
    id: 's5',
    name: '베이지 트렌치 코트',
    category: '아우터',
    tone: 0.1,
    owner: '서연',
    image: 'https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=400&h=500&fit=crop',
  },
  {
    id: 's6',
    name: '실버 체인 목걸이',
    category: '액세서리',
    tone: 0.14,
    owner: '민준',
    image: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400&h=500&fit=crop',
  },
];

/** 앱이 가진 옷 (카탈로그) — 아직 안 산 옷도 착장 기록에 올려볼 수 있다 */
export const LIBRARY_ITEMS: WardrobeItem[] = [
  {
    id: 'c1',
    name: '오버사이즈 셔츠',
    category: '상의',
    tone: 0.08,
    brand: '무신사 스탠다드',
    image: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400&h=500&fit=crop',
  },
  {
    id: 'c2',
    name: '울 블렌드 코트',
    category: '아우터',
    tone: 0.2,
    brand: 'COS',
    image: 'https://images.unsplash.com/photo-1544966503-7cc5ac882d5f?w=400&h=500&fit=crop',
  },
  {
    id: 'c3',
    name: '데님 팬츠',
    category: '하의',
    tone: 0.16,
    brand: '유니클로',
    image: 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=400&h=500&fit=crop',
  },
  {
    id: 'c4',
    name: '레더 스니커즈',
    category: '신발',
    tone: 0.24,
    brand: '나이키',
    image: 'https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&h=500&fit=crop',
  },
  {
    id: 'c5',
    name: '리넨 셋업 재킷',
    category: '아우터',
    tone: 0.11,
    brand: '자라',
    image: 'https://images.unsplash.com/photo-1539533018447-63fcce2678e3?w=400&h=500&fit=crop',
  },
  {
    id: 'c6',
    name: '캔버스 토트백',
    category: '가방',
    tone: 0.13,
    brand: '마르디 메크르디',
    image: 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400&h=500&fit=crop',
  },
];
