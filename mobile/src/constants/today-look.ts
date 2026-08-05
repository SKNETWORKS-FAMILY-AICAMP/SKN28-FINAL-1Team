/**
 * '오늘의 룩' 단일 출처.
 *
 * 룩상세(look-detail)·가상피팅(fitting)이 같은 룩을 가리키므로 제목·서브텍스트·구성 아이템을
 * 여기 한 곳에서 정의해 화면 간 불일치(드리프트)를 막는다. 백엔드가 룩을 내려주면 이 상수를
 * API 응답으로 교체한다(필드명 유지).
 */

import type { MallKey } from '@/lib/mall';

export type LookRelated = {
  name: string;
  brand: string;
  price: string;
  tone: number;
  /**
   * 외부 쇼핑몰 상품 주소. 백엔드 catalog 가 아직 link 를 안 내려줘서 지금은 비어 있고,
   * 비어 있으면 `mall` 에서 브랜드+상품명 검색 주소를 만든다(lib/mall.ts).
   */
  link?: string;
  /** 어느 몰로 보낼지. 생략하면 네이버쇼핑. */
  mall?: MallKey;
};

export type LookPiece = {
  slot: string;
  /**
   * 썸네일 원격 URL (SmartImage uri). 웹에선 프록시로 변환돼 로드된다.
   * **없으면 비워 둔다** — 다른 옷 사진을 빌려 쓰면 이름과 사진이 어긋나(벨트 사진에 '스니커즈')
   * placeholder 보다 나쁜 화면이 된다. 사진이 없으면 SmartImage 가 자리만 잡는다.
   */
  image?: string;
  name: string;
  brand: string;
  /** 관련 상품 썸네일 placeholder 농도 */
  tone: number;
  /** true=내 옷장 / false=추천 구매 */
  mine: boolean;
  related: LookRelated[];
};

export type LookVariant = {
  /** 화면 주소에 실리는 값 — `/look-detail?id=daily` */
  id: string;
  title: string;
  /** 무드·상황. 날씨는 화면에서 실시간 값을 앞에 붙일 수 있다. */
  subtitle: string;
  /** 대표 사진. 없으면 번들 목업(look-images.ts TODAY_LOOK_IMAGE)을 쓴다. */
  image?: string;
  reasons: string[];
  pieces: LookPiece[];
};

export const TODAY_LOOK = {
  id: 'daily',
  title: '산뜻한 미니멀 데일리',
  /** 무드·상황. 날씨는 화면에서 실시간 값을 앞에 붙일 수 있다. */
  subtitle: '미니멀 · 데일리',
  reasons: [
    '연분홍 상의에 검정 하의를 더해 화사함과 차분함의 균형을 잡았어요.',
    '추구하시는 미니멀 무드에 맞게 색을 둘로 절제하고 장식을 덜어냈어요.',
    '벨트로 허리선을 정리해 가벼운 반팔 룩에도 단정한 인상을 더했어요.',
  ],
  pieces: [
    {
      slot: '상의',
      image: 'https://i.pinimg.com/1200x/5b/a0/cc/5ba0cceab9b8340408f76b3149db7da7.jpg',
      name: '연분홍 코튼 티셔츠',
      brand: 'COS',
      tone: 0.05,
      mine: true,
      related: [
        { name: '베이직 코튼 반팔 티', brand: 'Uniqlo U', price: '19,900', tone: 0.05 },
        { name: '피그먼트 하프 티셔츠', brand: 'COS', price: '45,000', tone: 0.08 },
      ],
    },
    {
      slot: '하의',
      image: 'https://i.pinimg.com/736x/c8/5d/37/c85d37ca0dfe97d5fa9fc43e8a3bf7a8.jpg',
      name: '블랙 스트레이트 팬츠',
      brand: 'Uniqlo',
      tone: 0.2,
      mine: true,
      related: [
        { name: '스트레이트 코튼 팬츠', brand: 'Uniqlo', price: '39,900', tone: 0.2 },
        { name: '테이퍼드 슬랙스', brand: 'COS', price: '110,000', tone: 0.22 },
      ],
    },
    {
      slot: '액세서리',
      image: 'https://i.pinimg.com/1200x/0d/7f/72/0d7f72b8174a2bb5b9aae77463fdfaf3.jpg',
      name: '레더 슬림 벨트',
      brand: 'Musinsa Standard',
      tone: 0.15,
      mine: false,
      related: [
        { name: '미니멀 레더 벨트', brand: 'Musinsa Standard', price: '29,000', tone: 0.15, mall: 'musinsa' },
        { name: '스퀘어 버클 벨트', brand: 'COS', price: '55,000', tone: 0.18 },
      ],
    },
    {
      slot: '잡화',
      image: 'https://i.pinimg.com/1200x/c4/e5/98/c4e5989ab29ff09fa325d50b04d21173.jpg',
      name: '슬림 카드 지갑',
      brand: 'Fennec',
      tone: 0.1,
      mine: true,
      related: [
        { name: '레더 카드 홀더', brand: 'Fennec', price: '38,000', tone: 0.1 },
        { name: '슬림 카드 케이스', brand: 'COS', price: '49,000', tone: 0.12 },
      ],
    },
  ] as LookPiece[],
};

/**
 * 추천 룩 변형 — [다른 룩] 으로 돌아가며 보는 대상이자, 룩 상세가 id 로 가리키는 목록.
 *
 * 하나만 두면 어떤 카드를 눌러도 같은 화면이 열리고 [다른 룩] 이 갈 곳이 없다.
 * 백엔드가 룩을 내려주면 이 배열을 API 응답으로 갈아끼운다(필드명 유지).
 */
export const LOOK_VARIANTS: LookVariant[] = [
  TODAY_LOOK,
  {
    id: 'date',
    title: '부드러운 데이트 룩',
    subtitle: '캐주얼 · 데이트',
    image: 'https://i.pinimg.com/736x/55/26/0d/55260de328aec1e50740655fd4b5fdc5.jpg',
    reasons: [
      '밝은 니트에 데님을 맞춰 힘을 뺀 인상을 만들었어요.',
      '겉옷을 어깨에 걸칠 수 있게 얇은 것으로 골라 실내외 온도차에 대비했어요.',
      '장식이 적은 신발로 마무리해 시선이 상의로 모이게 했어요.',
    ],
    pieces: [
      {
        slot: '상의',
        name: '크림 케이블 니트',
        brand: 'COS',
        tone: 0.05,
        mine: true,
        related: [
          { name: '코튼 케이블 니트', brand: 'Uniqlo', price: '39,900', tone: 0.05 },
          { name: '램스울 크루넥', brand: 'COS', price: '89,000', tone: 0.07 },
        ],
      },
      {
        slot: '하의',
        name: '라이트 워시 데님',
        brand: 'Levi’s',
        tone: 0.16,
        mine: false,
        related: [
          { name: '와이드 스트레이트 데님', brand: 'Levi’s', price: '98,000', tone: 0.16, mall: 'musinsa' },
          { name: '루즈 테이퍼드 진', brand: 'Uniqlo', price: '49,900', tone: 0.18 },
        ],
      },
      {
        slot: '신발',
        name: '화이트 레더 스니커즈',
        brand: 'Adidas',
        tone: 0.06,
        mine: true,
        related: [
          { name: '스탠 스미스', brand: 'Adidas', price: '119,000', tone: 0.06, mall: 'musinsa' },
          { name: '미니멀 레더 스니커', brand: 'COS', price: '150,000', tone: 0.08 },
        ],
      },
    ],
  },
  {
    id: 'outdoor',
    title: '가벼운 나들이 레이어드',
    subtitle: '캐주얼 · 나들이',
    image: 'https://i.pinimg.com/736x/b4/cd/22/b4cd22015add333e10cd2ba06067406b.jpg',
    reasons: [
      '일교차가 큰 날이라 얇게 겹쳐 입어 벗고 걸치기 쉽게 했어요.',
      '활동량이 많은 일정에 맞춰 늘어나는 소재를 아래에 뒀어요.',
      '가방을 크로스로 메면 손이 자유로워 이동이 편해요.',
    ],
    pieces: [
      {
        slot: '아우터',
        name: '라이트 셔켓',
        brand: 'Musinsa Standard',
        tone: 0.12,
        mine: false,
        related: [
          { name: '코튼 셔켓', brand: 'Musinsa Standard', price: '59,000', tone: 0.12, mall: 'musinsa' },
          { name: '워크 재킷', brand: 'COS', price: '145,000', tone: 0.14 },
        ],
      },
      {
        slot: '상의',
        name: '화이트 코튼 티',
        brand: 'Uniqlo',
        tone: 0.04,
        mine: true,
        related: [
          { name: '에어리즘 코튼 티', brand: 'Uniqlo', price: '14,900', tone: 0.04 },
          { name: '헤비 코튼 티', brand: 'COS', price: '35,000', tone: 0.06 },
        ],
      },
      {
        slot: '잡화',
        name: '캔버스 크로스백',
        brand: 'Fennec',
        tone: 0.1,
        mine: false,
        related: [
          { name: '코튼 크로스백', brand: 'Fennec', price: '52,000', tone: 0.1 },
          { name: '나일론 숄더백', brand: 'COS', price: '95,000', tone: 0.12 },
        ],
      },
    ],
  },
];

/** id 로 룩을 찾는다. 못 찾으면 오늘의 룩. */
export function resolveLookVariant(id?: string | null): LookVariant {
  return LOOK_VARIANTS.find((l) => l.id === id) ?? LOOK_VARIANTS[0];
}
