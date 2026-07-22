/**
 * '오늘의 룩' 단일 출처.
 *
 * 룩상세(look-detail)·가상피팅(fitting)이 같은 룩을 가리키므로 제목·서브텍스트·구성 아이템을
 * 여기 한 곳에서 정의해 화면 간 불일치(드리프트)를 막는다. 백엔드가 룩을 내려주면 이 상수를
 * API 응답으로 교체한다(필드명 유지).
 */

export type LookRelated = { name: string; brand: string; price: string; tone: number };

export type LookPiece = {
  slot: string;
  /** 썸네일 원격 URL (SmartImage uri). 웹에선 프록시로 변환돼 로드된다. */
  image: string;
  name: string;
  brand: string;
  /** 관련 상품 썸네일 placeholder 농도 */
  tone: number;
  /** true=내 옷장 / false=추천 구매 */
  mine: boolean;
  related: LookRelated[];
};

export const TODAY_LOOK = {
  title: '산뜻한 미니멀 데일리',
  /** 무드·상황. 날씨는 화면에서 실시간 값을 앞에 붙일 수 있다. */
  subtitle: '미니멀 · 데일리',
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
        { name: '미니멀 레더 벨트', brand: 'Musinsa Standard', price: '29,000', tone: 0.15 },
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
