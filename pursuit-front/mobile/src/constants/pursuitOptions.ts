/**
 * 추구미 선호도 화면(옵션 목록 + 카테고리 순서) 상수.
 *
 * ⚠️ 현재는 프론트 하드코딩(Mock)이다. final.md 방향대로 스타일/색상 목록은
 * 백엔드가 관리하는 쪽을 우선 검토 중이며, 실제로는
 *   GET /api/v1/pursuit/options/  → { seasons: [...], styles: [...], ... }
 * 형태의 옵션 목록 조회 API로 대체될 예정이다. 이 파일의 키 이름(카테고리)과
 * PursuitOption 필드(code/label/colorHex/icon)는 그 응답 스키마를 그대로 맞춰 뒀으므로,
 * API 연동 시에는 이 상수를 fetch 결과로 교체하기만 하면 된다.
 */

import type { FC } from 'react';
import type { SvgProps } from 'react-native-svg';

import RoundNeckIcon from '@/assets/icons/necklines/round-neck.svg';
import VNeckIcon from '@/assets/icons/necklines/v-neck.svg';
import UNeckIcon from '@/assets/icons/necklines/u-neck.svg';
import HoodIcon from '@/assets/icons/necklines/hood.svg';
import SquareNeckIcon from '@/assets/icons/necklines/square-neck.svg';
import OffShoulderIcon from '@/assets/icons/necklines/off-shoulder.svg';
import HalfHighNeckIcon from '@/assets/icons/necklines/half_high.svg';
import OneShoulderIcon from '@/assets/icons/necklines/one-shoulder.svg';
import HalterNeckIcon from '@/assets/icons/necklines/halter-neck.svg';
import BoatNeckIcon from '@/assets/icons/necklines/boat-neck.svg';
import SweetheartNeckIcon from '@/assets/icons/necklines/sweetheart-neck.svg';
import TurtleneckIcon from '@/assets/icons/necklines/turtleneck.svg';
import HighNeckIcon from '@/assets/icons/necklines/high-neck.svg';
import HalfZipIcon from '@/assets/icons/necklines/half-zip.svg';

import LongSleeveIcon from '@/assets/icons/sleeve-length/long-sleeve.svg';
import ShortSleeveIcon from '@/assets/icons/sleeve-length/short-sleeve.svg';
import ThreeQuarterSleeveIcon from '@/assets/icons/sleeve-length/three-quarter-sleeve.svg';
import SleevelessIcon from '@/assets/icons/sleeve-length/sleeveless.svg';

import WidePantsIcon from '@/assets/icons/pants-fit/wide.svg';
import JoggerPantsIcon from '@/assets/icons/pants-fit/jogger.svg';
import StraightPantsIcon from '@/assets/icons/pants-fit/straight.svg';
import SkinnyPantsIcon from '@/assets/icons/pants-fit/skinny.svg';
import BootcutPantsIcon from '@/assets/icons/pants-fit/bootcut.svg';
import SlacksIcon from '@/assets/icons/pants-fit/slacks.svg';
import SemiWidePantsIcon from '@/assets/icons/pants-fit/semi-wide.svg';

import ShortShortsIcon from '@/assets/icons/pants-length/short-shorts-3.svg';
import ShortsIcon from '@/assets/icons/pants-length/shorts-5.svg';
import SevenPartPantsIcon from '@/assets/icons/pants-length/three-quarter-pants.svg';
import LongPantsIcon from '@/assets/icons/pants-length/long-pants.svg';

import MiniSkirtIcon from '@/assets/icons/skirt-length/mini.svg';
import MidiSkirtIcon from '@/assets/icons/skirt-length/midi.svg';
import LongSkirtIcon from '@/assets/icons/skirt-length/long-skirt.svg';
import MaxiSkirtIcon from '@/assets/icons/skirt-length/maxi.svg';

import ALineSkirtIcon from '@/assets/icons/skirt-type/a-line.svg';
import PleatsSkirtIcon from '@/assets/icons/skirt-type/pleated.svg';
import FlareSkirtIcon from '@/assets/icons/skirt-type/flare.svg';
import HLineSkirtIcon from '@/assets/icons/skirt-type/h-line.svg';
import MermaidSkirtIcon from '@/assets/icons/skirt-type/mermaid.svg';
import BalloonSkirtIcon from '@/assets/icons/skirt-type/balloon.svg';

export type PursuitCategoryKey =
  | 'seasons'
  | 'styles'
  | 'colors'
  | 'necklines'
  | 'top_fits'
  | 'top_lengths'
  | 'sleeves'
  | 'pants_fits'
  | 'pants_lengths'
  | 'skirt_lengths'
  | 'skirt_types';

export interface PursuitOption {
  code: string;
  label: string;
  /** 색상 카테고리 전용 스와치 색상 (선택적 표시 메타데이터) */
  colorHex?: string;
  /** 실루엣 아이콘이 준비된 카테고리(넥라인/소매/팬츠/스커트 등)에서만 사용 */
  icon?: FC<SvgProps>;
}

export type PursuitCategoryOptions = Record<PursuitCategoryKey, PursuitOption[]>;

/** 화면에 그릴 카테고리 순서 + 제목 + 짧은 설명 (final.md "카테고리" 목록 순서 그대로) */
export const PURSUIT_CATEGORIES: { key: PursuitCategoryKey; title: string; desc: string }[] = [
  { key: 'seasons', title: '계절', desc: '즐겨 입는 계절감을 골라주세요' },
  { key: 'styles', title: '스타일', desc: '추구하는 무드를 골라주세요' },
  { key: 'colors', title: '색상', desc: '입고 싶은 톤과 피하고 싶은 톤을 골라주세요' },
  { key: 'necklines', title: '넥라인', desc: '선호하는 넥라인을 골라주세요' },
  { key: 'top_fits', title: '상의핏', desc: '선호하는 상의 핏을 골라주세요' },
  { key: 'top_lengths', title: '상의기장', desc: '선호하는 상의 기장을 골라주세요' },
  { key: 'sleeves', title: '소매길이', desc: '선호하는 소매 길이를 골라주세요' },
  { key: 'pants_fits', title: '팬츠핏', desc: '선호하는 팬츠 핏을 골라주세요' },
  { key: 'pants_lengths', title: '팬츠기장', desc: '선호하는 팬츠 기장을 골라주세요' },
  { key: 'skirt_lengths', title: '스커트기장', desc: '선호하는 스커트 기장을 골라주세요' },
  { key: 'skirt_types', title: '스커트타입', desc: '선호하는 스커트 라인을 골라주세요' },
];

export const PURSUIT_CATEGORY_OPTIONS: PursuitCategoryOptions = {
  seasons: [
    { code: 'spring', label: '봄' },
    { code: 'summer', label: '여름' },
    { code: 'autumn', label: '가을' },
    { code: 'winter', label: '겨울' },
  ],
  styles: [
    { code: 'minimal', label: '미니멀' },
    { code: 'casual', label: '캐주얼' },
    { code: 'street', label: '스트릿' },
    { code: 'classic', label: '클래식' },
    { code: 'lovely', label: '러블리' },
    { code: 'chic', label: '시크' },
    { code: 'sporty', label: '스포티' },
    { code: 'vintage', label: '빈티지' },
    { code: 'romantic', label: '로맨틱' },
    { code: 'elegance', label: '엘레강스' },
    { code: 'retro', label: '레트로' },
    { code: 'modern', label: '모던' },
    { code: 'business', label: '비즈니스' },
    { code: 'business_casual', label: '비즈니스 캐주얼' },
    { code: 'americasual', label: '아메카지' },
    { code: 'boyish', label: '보이시' },
  ],
  colors: [
    { code: 'black', label: '블랙', colorHex: '#000000' },
    { code: 'ivory', label: '아이보리', colorHex: '#FFFFF0' },
    { code: 'white', label: '화이트', colorHex: '#FFFFFF' },
    { code: 'gray', label: '그레이', colorHex: '#808080' },
    { code: 'charcoal', label: '차콜', colorHex: '#413b3bdf' },
    { code: 'navy', label: '네이비', colorHex: '#000080' },
    { code: 'beige', label: '베이지', colorHex: '#F5F5DC' },
    { code: 'brown', label: '브라운', colorHex: '#8B4513' },
    { code: 'olive', label: '올리브', colorHex: '#556B2F' },
    { code: 'khaki', label: '카키', colorHex: '#625F04' },
    { code: 'carmel', label: '카멜', colorHex: '#C19A6B' },
    { code: 'denim_blue', label: '데님블루', colorHex: '#1560BD' },
    { code: 'light_pink', label: '라이트 핑크', colorHex: '#FFB6C1' },
    { code: 'pink', label: '핑크', colorHex: '#FFC0CB' },
    { code: 'rose', label: '로즈', colorHex: '#FF007F' },
    { code: 'mauve', label: '모브', colorHex: '#B784A7' },
    { code: 'peach', label: '피치', colorHex: '#FFDAB9' },
    { code: 'coral', label: '코럴', colorHex: '#FF7F50' },
    { code: 'light_blue', label: '라이트 블루', colorHex: '#ADD8E6' },
    { code: 'blue', label: '블루', colorHex: '#0000FF' },
    { code: 'mint', label: '민트', colorHex: '#3EB489' },
    { code: 'green', label: '그린', colorHex: '#05c905' },
    { code: 'red', label: '레드', colorHex: '#FF0000' },
    { code: 'burgundy', label: '버건디', colorHex: '#800020' },
    { code: 'yellow', label: '옐로우', colorHex: '#FFDB58' },
    { code: 'purple', label: '퍼플', colorHex: '#800080' },
    { code: 'orange', label: '오렌지', colorHex: '#FFA500' },
    { code: 'silver', label: '실버', colorHex: '#C0C0C0' },
    { code: 'gold', label: '골드', colorHex: '#FFD700' },
  ],
  necklines: [
    { code: 'round', label: '라운드넥', icon: RoundNeckIcon },
    { code: 'vneck', label: '브이넥', icon: VNeckIcon },
    { code: 'uneck', label: '유넥', icon: UNeckIcon },
    { code: 'hood', label: '후드', icon: HoodIcon },
    { code: 'square', label: '스퀘어넥', icon: SquareNeckIcon },
    { code: 'off_shoulder', label: '오프숄더', icon: OffShoulderIcon },
    { code: 'half_high', label: '반하이넥', icon: HalfHighNeckIcon },
    { code: 'one_shoulder', label: '원숄더', icon: OneShoulderIcon },
    { code: 'halter', label: '홀터넥', icon: HalterNeckIcon },
    { code: 'boat', label: '보트넥', icon: BoatNeckIcon },
    { code: 'heart', label: '하트넥', icon: SweetheartNeckIcon },
    { code: 'turtle', label: '터틀넥', icon: TurtleneckIcon },
    { code: 'high', label: '하이넥', icon: HighNeckIcon },
    { code: 'half_zip', label: '반집업', icon: HalfZipIcon },
  ],
  top_fits: [
    { code: 'normal', label: '노멀핏' },
    { code: 'slim', label: '슬림핏' },
    { code: 'loose', label: '루즈핏' },
    { code: 'oversized', label: '오버핏' },
  ],
  top_lengths: [
    { code: 'crop', label: '크롭' },
    { code: 'short', label: '숏' },
    { code: 'regular', label: '레귤러' },
    { code: 'long', label: '롱' },
  ],
  sleeves: [
    { code: 'long', label: '긴소매', icon: LongSleeveIcon },
    { code: 'short', label: '반소매', icon: ShortSleeveIcon },
    { code: 'three_quarter', label: '7부소매', icon: ThreeQuarterSleeveIcon },
    { code: 'sleeveless', label: '민소매', icon: SleevelessIcon },
  ],
  pants_fits: [
    { code: 'wide', label: '와이드', icon: WidePantsIcon },
    { code: 'jogger', label: '조거', icon: JoggerPantsIcon },
    { code: 'straight', label: '스트레이트', icon: StraightPantsIcon },
    { code: 'skinny', label: '스키니', icon: SkinnyPantsIcon },
    { code: 'bootcut', label: '부츠컷', icon: BootcutPantsIcon },
    { code: 'slacks', label: '슬랙스', icon: SlacksIcon },
    { code: 'semi_wide', label: '세미와이드', icon: SemiWidePantsIcon },
  ],
  pants_lengths: [
    { code: 'short_shorts', label: '짧은 반바지(3부)', icon: ShortShortsIcon },
    { code: 'shorts', label: '반바지(5부)', icon: ShortsIcon },
    { code: 'seven_part', label: '7부', icon: SevenPartPantsIcon },
    { code: 'long_pants', label: '긴바지', icon: LongPantsIcon },
  ],
  skirt_lengths: [
    { code: 'mini', label: '미니', icon: MiniSkirtIcon },
    { code: 'midi', label: '미디', icon: MidiSkirtIcon },
    { code: 'long', label: '롱', icon: LongSkirtIcon },
    { code: 'maxi', label: '맥시', icon: MaxiSkirtIcon },
  ],
  skirt_types: [
    { code: 'aline', label: 'A라인', icon: ALineSkirtIcon },
    { code: 'pleats', label: '플리츠', icon: PleatsSkirtIcon },
    { code: 'flare', label: '플레어 라인', icon: FlareSkirtIcon },
    { code: 'hline', label: 'H라인', icon: HLineSkirtIcon },
    { code: 'mermaid', label: '머메이드', icon: MermaidSkirtIcon },
    { code: 'balloon', label: '벌룬', icon: BalloonSkirtIcon },
  ],
};
