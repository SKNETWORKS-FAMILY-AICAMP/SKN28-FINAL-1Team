import { Icon } from '@/components/icon';
import { useConfirm, useToast } from '@/components/ui';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const BONE = '#eae0d3';
const WINE = '#5E2B2F';
const ink = (a: number) => `rgba(28,25,23,${a})`;

const SPECS = [
  { label: '색상', value: '아이보리' },
  { label: '소재', value: '울 80%' },
  { label: '사이즈', value: 'M' },
  { label: '계절', value: '가을·겨울' },
];

const TAGS = ['#미니멀', '#데일리', '#오피스', '#포근함'];

// D3 아이템 상세 — 정보·착용 기록·저활용 경고
export default function ItemDetail() {
  const { contentStyle } = useBreakpoint();
  const wearCount = 3;
  const underused = wearCount < 5;
  const toast = useToast();
  const confirm = useConfirm();

  const onDelete = async () => {
    const ok = await confirm({
      title: '이 아이템을 삭제할까요?',
      message: '삭제하면 되돌릴 수 없어요.',
      confirmLabel: '삭제',
      destructive: true,
    });
    if (!ok) return;
    // TODO: 실제 삭제 연동 (지금은 프로토타입 — 목록에서 빠진 척 뒤로 이동)
    toast('삭제됐어요', { variant: 'success' });
    router.back();
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.card)]}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <View style={styles.headerActions}>
            <Pressable hitSlop={10}>
              <Icon name="square.and.pencil" tintColor={ink(0.6)} size={19} />
            </Pressable>
            <Pressable hitSlop={10} onPress={onDelete}>
              <Icon name="trash" tintColor={ink(0.6)} size={18} />
            </Pressable>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(ContentMax.card)]}>
        {/* 이미지 */}
        <View style={styles.image}>
          <View style={styles.catBadge}>
            <Text style={styles.catBadgeText}>상의 · 니트</Text>
          </View>
        </View>

        <View style={styles.body}>
          <Text style={styles.name}>크림 울 니트</Text>
          <Text style={styles.brand}>COS</Text>

          {/* 스펙 그리드 */}
          <View style={styles.specGrid}>
            {SPECS.map((s) => (
              <View key={s.label} style={styles.specTile}>
                <Text style={styles.specLabel}>{s.label}</Text>
                <Text style={styles.specValue}>{s.value}</Text>
              </View>
            ))}
          </View>

          {/* 착용 기록 */}
          <Text style={styles.sectionTitle}>착용 기록</Text>
          <View style={styles.wearRow}>
            <View style={styles.wearTile}>
              <Text style={styles.wearNum}>{wearCount}</Text>
              <Text style={styles.wearLabel}>착용 횟수</Text>
            </View>
            <View style={styles.wearTile}>
              <Text style={styles.wearNum}>21일 전</Text>
              <Text style={styles.wearLabel}>마지막 착용</Text>
            </View>
          </View>

          {underused ? (
            <View style={styles.warn}>
              <Icon name="exclamationmark.triangle" tintColor={WINE} size={15} />
              <Text style={styles.warnText}>
                최근 착용이 적어요. 이 니트로 새 코디를 받아볼까요?
              </Text>
            </View>
          ) : null}

          {/* 태그 */}
          <Text style={styles.sectionTitle}>태그</Text>
          <View style={styles.tags}>
            {TAGS.map((t) => (
              <View key={t} style={styles.tag}>
                <Text style={styles.tagText}>{t}</Text>
              </View>
            ))}
          </View>
        </View>
      </ScrollView>

      <View style={styles.bottomDivider} />
      <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.card)]}>
        <Pressable style={styles.cta} onPress={() => router.push('/chat-room')}>
          <Icon name="sparkles" tintColor="#fff" size={15} />
          <Text style={styles.ctaText}>이 옷으로 코디 추천받기</Text>
        </Pressable>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  headerSafe: { backgroundColor: '#ffffff' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 8,
  },
  headerActions: { flexDirection: 'row', gap: 18 },

  content: { paddingBottom: 24 },
  image: {
    /* 고정 높이로 두면 폭이 넓어지는 데스크톱에서 가로로 납작해져 세로 사진이 잘린다.
       폰 폭(400) 기준 비율을 유지한다. */
    aspectRatio: 1.053,
    backgroundColor: BONE,
    marginHorizontal: 20,
    borderRadius: 20,
    overflow: 'hidden',
  },
  catBadge: {
    position: 'absolute',
    top: 14,
    left: 14,
    backgroundColor: 'rgba(255,255,255,0.9)',
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: 999,
  },
  catBadgeText: { fontSize: 11, fontWeight: '600', color: ink(0.7) },

  body: { paddingHorizontal: 20, paddingTop: 22 },
  name: { fontFamily: Fonts.serif, fontSize: 26, color: INK },
  brand: { fontSize: 14, color: ink(0.45), marginTop: 5 },

  specGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 22,
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 16,
    overflow: 'hidden',
  },
  specTile: {
    width: '50%',
    paddingHorizontal: 16,
    paddingVertical: 15,
    gap: 5,
  },
  specLabel: { fontSize: 11, color: ink(0.4) },
  specValue: { fontSize: 14.5, fontWeight: '500', color: ink(0.9) },

  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 28, marginBottom: 12 },
  wearRow: { flexDirection: 'row', gap: 10 },
  wearTile: {
    flex: 1,
    backgroundColor: '#fcffff',
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 16,
    gap: 4,
  },
  wearNum: { fontFamily: Fonts.serif, fontSize: 22, fontWeight: '600', color: INK },
  wearLabel: { fontSize: 11.5, color: ink(0.45) },

  warn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    marginTop: 12,
    backgroundColor: '#f3e4de',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  warnText: { flex: 1, fontSize: 12.5, color: WINE, lineHeight: 18 },

  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tag: {
    backgroundColor: '#f3ece2',
    borderRadius: 999,
    paddingHorizontal: 13,
    paddingVertical: 7,
  },
  tagText: { fontSize: 12.5, color: ink(0.6), fontWeight: '500' },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { backgroundColor: '#fff', paddingHorizontal: 20, paddingTop: 12 },
  cta: {
    flexDirection: 'row',
    gap: 8,
    height: 52,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { fontSize: 14.5, color: '#fff', fontWeight: '500' },
});
