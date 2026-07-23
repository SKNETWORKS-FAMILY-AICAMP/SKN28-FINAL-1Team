import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = Editorial.ink;
const BONE = Editorial.bone;

const PIECES = [
  { slot: '상의', name: '크림 울 니트', tone: 0.06 },
  { slot: '하의', name: '차콜 슬랙스', tone: 0.18 },
  { slot: '아우터', name: '트렌치 코트', tone: 0.1 },
  { slot: '신발', name: '스웨이드 로퍼', tone: 0.24 },
];

const HASHTAGS = ['#가을', '#출근', '#미니멀', '#포근함'];

// E2 저장 룩 상세 — 구성·추천이유 재확인·메모/해시태그
export default function SavedLook() {
  const { contentStyle } = useBreakpoint();
  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.card)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/lookbook')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <View style={styles.headerActions}>
            <Pressable hitSlop={10}>
              <Icon name="square.and.pencil" tintColor={ink(0.6)} size={19} />
            </Pressable>
            <Pressable hitSlop={10}>
              <Icon name="trash" tintColor={ink(0.6)} size={18} />
            </Pressable>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(ContentMax.card)]}>
        {/* 룩 이미지 */}
        <View style={styles.image}>
          <View style={styles.savedBadge}>
            <Icon name="heart.fill" tintColor="#fff" size={11} />
            <Text style={styles.savedText}>저장한 룩</Text>
          </View>
        </View>

        <View style={styles.body}>
          <Text style={styles.title}>포근한 니트 데이</Text>
          <Text style={styles.subtitle}>2026. 7. 6. 저장 · 미니멀</Text>

          {/* 구성 (칩 나열) */}
          <Text style={styles.sectionTitle}>구성 아이템</Text>
          <View style={styles.pieces}>
            {PIECES.map((p) => (
              <View key={p.slot} style={styles.piece}>
                <View style={[styles.pieceThumb, { backgroundColor: `rgba(28,25,23,${p.tone})` }]} />
                <Text style={styles.pieceSlot}>{p.slot}</Text>
                <Text style={styles.pieceName}>{p.name}</Text>
              </View>
            ))}
          </View>

          {/* 추천 이유 */}
          <Text style={styles.sectionTitle}>추천받은 이유</Text>
          <View style={styles.reasonCard}>
            <Text style={styles.reasonText}>
              8도의 쌀쌀한 날씨에 맞춰 니트와 코트로 보온성을 확보하고,
              미니멀 무드에 맞게 톤을 절제한 오피스 코디예요.
            </Text>
          </View>

          {/* 메모 */}
          <Text style={styles.sectionTitle}>메모</Text>
          <Pressable style={styles.memoCard}>
            <Text style={styles.memoText}>회사 발표 있는 날 입기 좋았음. 로퍼 대신 부츠도 잘 어울릴 듯.</Text>
            <View style={styles.memoEdit}>
              <Icon name="pencil" tintColor={ink(0.4)} size={13} />
            </View>
          </Pressable>

          {/* 해시태그 */}
          <View style={styles.tags}>
            {HASHTAGS.map((t) => (
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
          <Text style={styles.ctaText}>비슷하게 추천받기</Text>
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
    aspectRatio: 1.176,
    backgroundColor: BONE,
    marginHorizontal: 20,
    borderRadius: 20,
    overflow: 'hidden',
  },
  savedBadge: {
    position: 'absolute',
    top: 14,
    left: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: INK,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderRadius: 999,
  },
  savedText: { fontSize: 10.5, color: '#fff', fontWeight: '500' },

  body: { paddingHorizontal: 20, paddingTop: 22 },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK },
  subtitle: { fontSize: 13, color: ink(0.45), marginTop: 6 },

  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 26, marginBottom: 12 },

  pieces: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  piece: {
    width: '47.5%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 14,
    padding: 8,
  },
  pieceThumb: { width: 38, height: 38, borderRadius: 9, backgroundColor: BONE },
  pieceSlot: { fontSize: 10, color: ink(0.4), position: 'absolute', left: 56, top: 8 },
  pieceName: { flex: 1, fontSize: 12.5, fontWeight: '500', color: ink(0.85), marginTop: 12 },

  reasonCard: { backgroundColor: Editorial.surfaceSoft, borderRadius: 16, padding: 16 },
  reasonText: { fontSize: 13.5, color: ink(0.7), lineHeight: 21 },

  memoCard: {
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 14,
    padding: 15,
    paddingRight: 40,
  },
  memoText: { fontSize: 13.5, color: ink(0.75), lineHeight: 20 },
  memoEdit: { position: 'absolute', top: 12, right: 12 },

  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 18 },
  tag: { backgroundColor: Editorial.surface, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 7 },
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
