import { Icon } from '@/components/icon';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { SmartImage, useToast } from '@/components/ui';
import { Editorial, ink, Fonts , ContentMax} from '@/constants/theme';
import { TODAY_LOOK } from '@/constants/today-look';
import { useBottomTabInset } from '@/hooks/use-bottom-tab-inset';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useAuth } from '@/state/auth';
import { draftItem } from '@/state/draft-item';

const INK = Editorial.ink;
const BONE = Editorial.bone;

/* 구성 아이템은 룩 단일 출처를 그대로 쓴다 — 여기만 목업을 따로 두면 룩상세와 다른 옷이 나온다. */
const PIECES = TODAY_LOOK.pieces;

const HASHTAGS = ['#가을', '#출근', '#미니멀', '#포근함'];

// E2 저장 룩 상세 — 구성·추천이유 재확인·메모/해시태그
export default function SavedLook() {
  const { contentStyle } = useBreakpoint();
  const tabInset = useBottomTabInset();
  const toast = useToast();
  const { isLoggedIn } = useAuth();

  /**
   * 이 옷을 내 옷장에 등록한다.
   * 바로 올리지 않고 등록 화면을 거치는 이유 — 무엇이 등록되는지 사진으로 확인시키고,
   * 등록은 서버 큐를 타서 시간이 걸리므로 진행 상황을 옷장에서 보게 하기 위해서다.
   */
  const addToCloset = (photo: string) => {
    if (!isLoggedIn) {
      toast('옷장은 로그인하고 쓸 수 있어요');
      router.push('/login');
      return;
    }
    draftItem.setPhoto(photo);
    router.push('/item-add');
  };

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
                <View style={styles.pieceThumb}>
                  <SmartImage uri={p.image} width="100%" aspectRatio={1} radius={10} contentFit="cover" />
                </View>
                <View style={styles.pieceBody}>
                  <Text style={styles.pieceSlot}>{p.slot}</Text>
                  <Text style={styles.pieceName} numberOfLines={1}>
                    {p.name}
                  </Text>
                </View>
                <Pressable
                  style={styles.addBtn}
                  onPress={() => addToCloset(p.image)}
                  accessibilityLabel={`${p.name} 옷장에 추가`}>
                  <Icon name="plus" tintColor={INK} size={13} />
                  <Text style={styles.addBtnText}>옷장에 추가</Text>
                </Pressable>
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
      <View style={[styles.bottomBar, { paddingBottom: tabInset }, contentStyle(ContentMax.card)]}>
        <Pressable style={styles.cta} onPress={() => router.push('/chat-room')}>
          <Icon name="sparkles" tintColor="#fff" size={15} />
          <Text style={styles.ctaText}>비슷하게 추천받기</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  headerSafe: { backgroundColor: Editorial.page },
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
  subtitle: { fontSize: 13, color: Editorial.textCaption, marginTop: 6 },

  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 26, marginBottom: 12 },

  /* 아이템마다 '옷장에' 버튼이 붙어 2단으로 두면 이름이 잘린다 → 한 줄에 하나씩. */
  pieces: { gap: 10 },
  piece: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 14,
    padding: 10,
  },
  pieceThumb: { width: 44, height: 44, borderRadius: 10, backgroundColor: BONE, overflow: 'hidden' },
  pieceBody: { flex: 1, gap: 3 },
  pieceSlot: { fontSize: 10.5, color: Editorial.textCaption },
  pieceName: { fontSize: 13.5, fontWeight: '500', color: Editorial.ink },
  addBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    height: 30,
    paddingHorizontal: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  addBtnText: { fontSize: 11.5, fontWeight: '600', color: INK },

  reasonCard: { backgroundColor: Editorial.surfaceSoft, borderWidth: 1, borderColor: Editorial.line, borderRadius: 16, padding: 16 },
  reasonText: { fontSize: 13.5, color: Editorial.textSoft, lineHeight: 21 },

  memoCard: {
    borderWidth: 1,
    borderColor: ink(0.1),
    borderRadius: 14,
    padding: 15,
    paddingRight: 40,
  },
  memoText: { fontSize: 13.5, color: Editorial.textSoft, lineHeight: 20 },
  memoEdit: { position: 'absolute', top: 12, right: 12 },

  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 18 },
  tag: { backgroundColor: Editorial.control, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 7 },
  tagText: { fontSize: 12.5, color: Editorial.textCaption, fontWeight: '500' },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { backgroundColor: Editorial.page, paddingHorizontal: 20, paddingTop: 12 },
  cta: {
    flexDirection: 'row',
    gap: 8,
    height: 52,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaText: { fontSize: 14.5, color: '#fff', fontWeight: '500' },
});
