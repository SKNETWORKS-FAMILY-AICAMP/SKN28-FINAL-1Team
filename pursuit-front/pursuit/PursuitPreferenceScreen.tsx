import React, { useState, useEffect } from 'react';
import {
  View,
  ScrollView,
  TouchableOpacity,
  Text,
  SafeAreaView,
  ActivityIndicator,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
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

import NormalFitIcon from '@/assets/icons/top-fit/normal-fit.svg';
import SlimFitIcon from '@/assets/icons/top-fit/slim-fit.svg';
import LooseFitIcon from '@/assets/icons/top-fit/loose-fit.svg';
import OverFitIcon from '@/assets/icons/top-fit/over-fit.svg';

import CropLengthIcon from '@/assets/icons/top-length/crop.svg';
import ShortLengthIcon from '@/assets/icons/top-length/short-length.svg';
import RegularLengthIcon from '@/assets/icons/top-length/regular-length.svg';
import LongLengthIcon from '@/assets/icons/top-length/long-length.svg';

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

// ============================================================================
// Types & Interfaces
// ============================================================================

type PreferenceMode = 'preferred' | 'avoided';

// icon은 임시 이모지(string) 또는 SVG 아이콘 컴포넌트(FC<SvgProps>)를 받는다.
// SVG 아이콘이 준비된 항목부터 순차적으로 이모지 대신 넣는다.
interface PreferenceOption {
  code: string;
  label: string;
  colorHex?: string;
  icon?: string | React.FC<SvgProps>;
}

interface CategoryOptions {
  seasons: PreferenceOption[];
  styles: PreferenceOption[];
  colors: PreferenceOption[];
  necklines: PreferenceOption[];
  top_fits: PreferenceOption[];
  top_lengths: PreferenceOption[];
  sleeves: PreferenceOption[];
  pants_fits: PreferenceOption[];
  pants_lengths: PreferenceOption[];
  skirt_lengths: PreferenceOption[];
  skirt_types: PreferenceOption[];
}

interface UserPreferences {
  preferred: {
    seasons: string[];
    styles: string[];
    colors: string[];
    necklines: string[];
    top_fits: string[];
    top_lengths: string[];
    sleeves: string[];
    pants_fits: string[];
    pants_lengths: string[];
    skirt_lengths: string[];
    skirt_types: string[];
  };
  avoided: {
    seasons: string[];
    styles: string[];
    colors: string[];
    necklines: string[];
    top_fits: string[];
    top_lengths: string[];
    sleeves: string[];
    pants_fits: string[];
    pants_lengths: string[];
    skirt_lengths: string[];
    skirt_types: string[];
  };
}

// ============================================================================
// Mock Data
// ============================================================================

const MOCK_CATEGORY_OPTIONS: CategoryOptions = {
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
    { code: 'normal', label: '노멀핏'},
    { code: 'slim', label: '슬림핏'},
    { code: 'loose', label: '루즈핏'},
    { code: 'oversized', label: '오버핏'},
  ],
  top_lengths: [
    { code: 'crop', label: '크롭'},
    { code: 'short', label: '숏'},
    { code: 'regular', label: '레귤러'},
    { code: 'long', label: '롱'},
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

// ============================================================================
// Chip Component
// ============================================================================

interface ChipProps {
  label: string;
  code: string;
  isSelected: boolean;
  mode: PreferenceMode;
  colorHex?: string;
  icon?: string | React.FC<SvgProps>;
  onPress: () => void;
}

const Chip: React.FC<ChipProps> = ({
  label,
  code,
  isSelected,
  mode,
  colorHex,
  icon,
  onPress,
}) => {
  const backgroundColor = isSelected
    ? mode === 'preferred'
      ? '#007AFF'
      : '#FF3B30'
    : '#FFFFFF';

  const textColor = isSelected ? '#FFFFFF' : '#000000';
  const borderColor = isSelected ? 'transparent' : '#E0E0E0';

  return (
    <TouchableOpacity
      onPress={onPress}
      style={{
        paddingHorizontal: 12,
        paddingVertical: 8,
        borderRadius: 20,
        backgroundColor,
        borderWidth: 1,
        borderColor,
        flexDirection: 'row',
        alignItems: 'center',
      }}
    >
      {colorHex && (
        <View
          style={{
            width: 12,
            height: 12,
            borderRadius: 2,
            backgroundColor: colorHex,
            marginRight: 6,
            borderWidth: colorHex === '#FFFFFF' ? 1 : 0,
            borderColor: '#CCCCCC',
          }}
        />
      )}
      {icon &&
        (typeof icon === 'string' ? (
          <Text style={{ marginRight: 4, fontSize: 14 }}>{icon}</Text>
        ) : (
          React.createElement(icon, {
            width: 16,
            height: 16,
            style: { marginRight: 4 },
          })
        ))}
      <Text style={{ color: textColor, fontSize: 12, fontWeight: '500' }}>
        {label}
      </Text>
    </TouchableOpacity>
  );
};

// ============================================================================
// Category Section Component
// ============================================================================

interface CategorySectionProps {
  title: string;
  options: PreferenceOption[];
  selectedCodes: {
    preferred: string[];
    avoided: string[];
  };
  currentMode: PreferenceMode;
  onSelectOption: (code: string) => void;
}

const CategorySection: React.FC<CategorySectionProps> = ({
  title,
  options,
  selectedCodes,
  currentMode,
  onSelectOption,
}) => {
  return (
    <View style={{ marginBottom: 24 }}>
      <Text style={{ fontSize: 16, fontWeight: '600', marginBottom: 12 }}>
        {title}
      </Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -4 }}>
        {options.map((option) => {
          const isSelectedPreferred = selectedCodes.preferred.includes(
            option.code
          );
          const isSelectedAvoided = selectedCodes.avoided.includes(option.code);
          const isSelected = isSelectedPreferred || isSelectedAvoided;
          const mode = isSelectedPreferred ? 'preferred' : 'avoided';

          return (
            <View key={option.code} style={{ paddingHorizontal: 4, marginBottom: 8 }}>
              <Chip
                label={option.label}
                code={option.code}
                isSelected={isSelected}
                mode={mode}
                colorHex={option.colorHex}
                icon={option.icon}
                onPress={() => onSelectOption(option.code)}
              />
            </View>
          );
        })}
      </View>
    </View>
  );
};

// ============================================================================
// Main Screen Component
// ============================================================================

export const PursuitPreferenceScreen: React.FC = () => {
  const insets = useSafeAreaInsets();
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const goBack = () => {
    if (returnTo === 'my') router.replace('/(tabs)/my');
    else router.back();
  };
  const [currentMode, setCurrentMode] = useState<PreferenceMode>('preferred');
  const [preferences, setPreferences] = useState<UserPreferences>({
    preferred: {
      seasons: [],
      styles: [],
      colors: [],
      necklines: [],
      top_fits: [],
      top_lengths: [],
      sleeves: [],
      pants_fits: [],
      pants_lengths: [],
      skirt_lengths: [],
      skirt_types: [],
    },
    avoided: {
      seasons: [],
      styles: [],
      colors: [],
      necklines: [],
      top_fits: [],
      top_lengths: [],
      sleeves: [],
      pants_fits: [],
      pants_lengths: [],
      skirt_lengths: [],
      skirt_types: [],
    },
  });
  const [isLoading, setIsLoading] = useState(false);

  const handleSelectOption = (categoryKey: keyof UserPreferences['preferred'], code: string) => {
    setPreferences((prev) => {
      const newPrefs = { ...prev };
      const preferredList = newPrefs.preferred[categoryKey] as string[];
      const avoidedList = newPrefs.avoided[categoryKey] as string[];

      const isInPreferred = preferredList.includes(code);
      const isInAvoided = avoidedList.includes(code);

      if (currentMode === 'preferred') {
        if (isInPreferred) {
          newPrefs.preferred[categoryKey] = preferredList.filter(
            (c) => c !== code
          ) as any;
        } else {
          newPrefs.preferred[categoryKey] = [...preferredList, code] as any;
          newPrefs.avoided[categoryKey] = avoidedList.filter(
            (c) => c !== code
          ) as any;
        }
      } else {
        if (isInAvoided) {
          newPrefs.avoided[categoryKey] = avoidedList.filter(
            (c) => c !== code
          ) as any;
        } else {
          newPrefs.avoided[categoryKey] = [...avoidedList, code] as any;
          newPrefs.preferred[categoryKey] = preferredList.filter(
            (c) => c !== code
          ) as any;
        }
      }

      return newPrefs;
    });
  };

  const handleSave = async () => {
    setIsLoading(true);
    try {
      // TODO: 백엔드 "내 선호도 저장" API 연동 전까지는 저장 없이 이동만 한다.
      goBack();
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    goBack();
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#FFFFFF' }}>
      <View style={{ paddingHorizontal: 16, paddingVertical: 12 }}>
        <Text style={{ fontSize: 18, fontWeight: '600' }}>추구미 선호도</Text>
      </View>

      <View
        style={{
          flexDirection: 'row',
          paddingHorizontal: 16,
          paddingVertical: 12,
          gap: 12,
        }}
      >
        <TouchableOpacity
          onPress={() => setCurrentMode('preferred')}
          style={{
            flex: 1,
            paddingVertical: 12,
            paddingHorizontal: 16,
            borderRadius: 20,
            backgroundColor:
              currentMode === 'preferred' ? '#007AFF' : '#FFFFFF',
            borderWidth: currentMode === 'preferred' ? 0 : 1,
            borderColor: '#007AFF',
            alignItems: 'center',
          }}
        >
          <Text
            style={{
              color: currentMode === 'preferred' ? '#FFFFFF' : '#007AFF',
              fontSize: 14,
              fontWeight: '600',
            }}
          >
            💙 선호해요
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          onPress={() => setCurrentMode('avoided')}
          style={{
            flex: 1,
            paddingVertical: 12,
            paddingHorizontal: 16,
            borderRadius: 20,
            backgroundColor:
              currentMode === 'avoided' ? '#FF3B30' : '#FFFFFF',
            borderWidth: currentMode === 'avoided' ? 0 : 1,
            borderColor: '#FF3B30',
            alignItems: 'center',
          }}
        >
          <Text
            style={{
              color: currentMode === 'avoided' ? '#FFFFFF' : '#FF3B30',
              fontSize: 14,
              fontWeight: '600',
            }}
          >
            🚫 피하고 싶어요
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{
          paddingHorizontal: 16,
          paddingTop: 24,
          paddingBottom: 48,
        }}
        showsVerticalScrollIndicator={false}
      >
        <CategorySection
          title="계절"
          options={MOCK_CATEGORY_OPTIONS.seasons}
          selectedCodes={{
            preferred: preferences.preferred.seasons,
            avoided: preferences.avoided.seasons,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('seasons', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="스타일"
          options={MOCK_CATEGORY_OPTIONS.styles}
          selectedCodes={{
            preferred: preferences.preferred.styles,
            avoided: preferences.avoided.styles,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('styles', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="색상"
          options={MOCK_CATEGORY_OPTIONS.colors}
          selectedCodes={{
            preferred: preferences.preferred.colors,
            avoided: preferences.avoided.colors,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('colors', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="넥라인"
          options={MOCK_CATEGORY_OPTIONS.necklines}
          selectedCodes={{
            preferred: preferences.preferred.necklines,
            avoided: preferences.avoided.necklines,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('necklines', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="상의핏"
          options={MOCK_CATEGORY_OPTIONS.top_fits}
          selectedCodes={{
            preferred: preferences.preferred.top_fits,
            avoided: preferences.avoided.top_fits,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('top_fits', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="상의기장"
          options={MOCK_CATEGORY_OPTIONS.top_lengths}
          selectedCodes={{
            preferred: preferences.preferred.top_lengths,
            avoided: preferences.avoided.top_lengths,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('top_lengths', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="소매길이"
          options={MOCK_CATEGORY_OPTIONS.sleeves}
          selectedCodes={{
            preferred: preferences.preferred.sleeves,
            avoided: preferences.avoided.sleeves,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('sleeves', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="팬츠핏"
          options={MOCK_CATEGORY_OPTIONS.pants_fits}
          selectedCodes={{
            preferred: preferences.preferred.pants_fits,
            avoided: preferences.avoided.pants_fits,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('pants_fits', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="팬츠 기장"
          options={MOCK_CATEGORY_OPTIONS.pants_lengths}
          selectedCodes={{
            preferred: preferences.preferred.pants_lengths,
            avoided: preferences.avoided.pants_lengths,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('pants_lengths', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="스커트 기장"
          options={MOCK_CATEGORY_OPTIONS.skirt_lengths}
          selectedCodes={{
            preferred: preferences.preferred.skirt_lengths,
            avoided: preferences.avoided.skirt_lengths,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('skirt_lengths', code)}
        />

        <View style={{ height: 8 }} />

        <CategorySection
          title="스커트 타입"
          options={MOCK_CATEGORY_OPTIONS.skirt_types}
          selectedCodes={{
            preferred: preferences.preferred.skirt_types,
            avoided: preferences.avoided.skirt_types,
          }}
          currentMode={currentMode}
          onSelectOption={(code) => handleSelectOption('skirt_types', code)}
        />
      </ScrollView>

      <View
        style={{
          flexDirection: 'row',
          paddingHorizontal: 16,
          paddingVertical: 12,
          paddingBottom: insets.bottom + 12,
          gap: 12,
        }}
      >
        <TouchableOpacity
          onPress={handleCancel}
          disabled={isLoading}
          style={{
            flex: 1,
            paddingVertical: 14,
            borderRadius: 8,
            backgroundColor: '#FFFFFF',
            borderWidth: 1,
            borderColor: '#E0E0E0',
            alignItems: 'center',
          }}
        >
          <Text style={{ fontSize: 16, fontWeight: '600', color: '#000000' }}>
            취소
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          onPress={handleSave}
          disabled={isLoading}
          style={{
            flex: 1,
            paddingVertical: 14,
            borderRadius: 8,
            backgroundColor: isLoading ? '#CCCCCC' : '#000000',
            alignItems: 'center',
          }}
        >
          {isLoading ? (
            <ActivityIndicator color='#FFFFFF' />
          ) : (
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#FFFFFF' }}>
              저장하기
            </Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
};

export default PursuitPreferenceScreen;
