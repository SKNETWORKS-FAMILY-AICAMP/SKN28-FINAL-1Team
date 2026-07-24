import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { draftItem, useDraftPhoto } from '@/state/draft-item';

// ── 에디토리얼 본(Editorial Bone) 팔레트 ─────────────────
// 디자인은 라이트 모드 고정. 잉크 + 크림 톤.
const INK = '#1c1917';
const BONE = '#eae0d3';
const ink = (a: number) => `rgba(28,25,23,${a})`;

/** 라벨 + (선택)AI 뱃지 + 밑줄 입력 필드 */
function Field({
  label,
  ai,
  value,
  onChangeText,
  placeholder,
}: {
  label: string;
  ai?: boolean;
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
}) {
  return (
    <View style={styles.field}>
      <View style={styles.fieldLabelRow}>
        <Text style={styles.fieldLabel}>{label}</Text>
        {ai ? (
          <View style={styles.aiBadge}>
            <Text style={styles.aiBadgeText}>AI</Text>
          </View>
        ) : null}
      </View>
      <TextInput
        style={styles.fieldValue}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={ink(0.32)}
      />
      <View style={styles.fieldUnderline} />
    </View>
  );
}

export default function ItemAddScreen() {
  const { contentStyle } = useBreakpoint();
  // 무신사 WebView(모달)에서 가져온 사진 URL. 없으면 빈 상태.
  const photo = useDraftPhoto();

  // AI가 자동 분류한 값 (사용자가 수정 가능)
  const [category, setCategory] = useState('상의');
  const [color, setColor] = useState('화이트');
  const [material, setMaterial] = useState('코튼');
  const [size, setSize] = useState('M');
  const [brand, setBrand] = useState('');
  const [memo, setMemo] = useState('');

  // 사진 영역 — item-add-source 에서 가져온 사진 표시
  const openSource = () => router.push('/item-add-source');

  const handleSave = () => {
    // TODO: 백엔드 전송 → 누끼(rembg) → 옷장 저장
    console.log('[옷장 저장]', { photo, category, color, material, size, brand, memo });
    draftItem.setPhoto(null);
  };

  return (
    <View style={styles.container}>
      {/* 헤더 */}
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <View style={styles.headerText}>
            <Text style={styles.title}>아이템 등록</Text>
            <Text style={styles.subtitle}>사진을 올리면 AI가 자동으로 분류해요</Text>
          </View>
          <Pressable hitSlop={12} onPress={() => draftItem.setPhoto(null)}>
            <Text style={styles.close}>✕</Text>
          </Pressable>
        </View>
      </SafeAreaView>
      <View style={styles.divider} />

      {/* 본문 */}
      <ScrollView
        contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}
        keyboardShouldPersistTaps="handled">
        {/* 사진 영역 = 가져오기 버튼 (탭하면 무신사 WebView 열림) */}
        <Pressable style={styles.photo} onPress={openSource}>
          {photo ? (
            <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} contentFit="cover" />
          ) : (
            <View style={styles.photoEmpty}>
              <Text style={styles.photoEmptyIcon}>＋</Text>
              <Text style={styles.photoEmptyText}>사진 추가하기</Text>
            </View>
          )}
          {photo ? (
            <View style={styles.aiDoneBadge}>
              <Text style={styles.aiDoneText}>✓ AI 분석 완료</Text>
            </View>
          ) : null}
        </Pressable>

        {/* 2열 필드: 카테고리 / 색상 */}
        <View style={styles.row}>
          <View style={styles.col}>
            <Field label="카테고리" ai value={category} onChangeText={setCategory} />
          </View>
          <View style={styles.col}>
            <Field label="색상" ai value={color} onChangeText={setColor} />
          </View>
        </View>

        {/* 2열 필드: 소재 / 사이즈 */}
        <View style={styles.row}>
          <View style={styles.col}>
            <Field label="소재" ai value={material} onChangeText={setMaterial} />
          </View>
          <View style={styles.col}>
            <Field label="사이즈" value={size} onChangeText={setSize} />
          </View>
        </View>

        {/* 전체 폭 필드 */}
        <Field
          label="브랜드"
          value={brand}
          onChangeText={setBrand}
          placeholder="브랜드를 입력하세요"
        />
        <Field
          label="메모"
          value={memo}
          onChangeText={setMemo}
          placeholder="스타일링 메모 (선택)"
        />
      </ScrollView>

      {/* 하단 저장 바 */}
      <View style={styles.bottomDivider} />
      <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
        <Pressable style={styles.saveButton} onPress={handleSave}>
          <Text style={styles.saveText}>옷장에 저장</Text>
        </Pressable>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },

  // 헤더
  headerSafe: { backgroundColor: '#ffffff' },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 12,
  },
  headerText: { gap: 3 },
  title: {
    fontFamily: Fonts.serif,
    fontSize: 24,
    color: INK,
    fontWeight: '500',
  },
  subtitle: { fontSize: 11.5, color: ink(0.45) },
  close: { fontSize: 18, color: ink(0.5) },
  divider: { height: 1, backgroundColor: ink(0.1) },

  // 본문
  content: { paddingHorizontal: 20, paddingTop: 24, paddingBottom: 32, gap: 22 },

  // 사진
  photo: {
    height: 180,
    borderRadius: 16,
    backgroundColor: BONE,
    overflow: 'hidden',
    justifyContent: 'flex-end',
  },
  photoEmpty: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  photoEmptyIcon: { fontSize: 30, color: ink(0.35), lineHeight: 34 },
  photoEmptyText: { fontSize: 13, color: ink(0.45) },
  aiDoneBadge: {
    position: 'absolute',
    left: 14,
    bottom: 14,
    flexDirection: 'row',
    backgroundColor: INK,
    paddingLeft: 11,
    paddingRight: 13,
    paddingVertical: 6,
    borderRadius: 999,
  },
  aiDoneText: { fontSize: 10, color: '#ffffff', fontWeight: '500' },

  // 필드
  row: { flexDirection: 'row', gap: 16 },
  col: { flex: 1 },
  field: { gap: 9 },
  fieldLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  fieldLabel: {
    fontSize: 10,
    fontWeight: '500',
    color: ink(0.42),
    letterSpacing: 0.2,
  },
  aiBadge: {
    backgroundColor: INK,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 999,
  },
  aiBadgeText: {
    fontSize: 8,
    fontWeight: '500',
    color: '#ffffff',
    letterSpacing: 0.16,
  },
  fieldValue: {
    fontSize: 14,
    color: ink(0.9),
    padding: 0,
    ...Platform.select({ android: { paddingVertical: 0 } }),
  },
  fieldUnderline: { height: 1, backgroundColor: ink(0.15) },

  // 하단 바
  bottomDivider: { height: 1, backgroundColor: ink(0.1) },
  bottomBar: { backgroundColor: '#ffffff', paddingHorizontal: 20, paddingTop: 16 },
  saveButton: {
    height: 48,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveText: { fontSize: 14, fontWeight: '500', color: '#ffffff' },
});
