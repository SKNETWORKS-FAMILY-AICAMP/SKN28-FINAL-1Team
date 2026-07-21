import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { formatBudget, parsePrice, usePrefs } from '@/state/prefs';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fonts , ContentMax} from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';

const INK = '#1c1917';
const WINE = '#5E2B2F';
const BONE = '#eae0d3';
const ink = (a: number) => `rgba(28,25,23,${a})`;

type Related = { name: string; brand: string; price: string; tone: number };
type Piece = {
  slot: string;
  name: string;
  brand: string;
  tone: number;
  mine: boolean;
  related: Related[];
};

// related = 이 슬롯의 대체/비슷한 상품. 예산 내 여부는 마이>예산 설정값과 price를 비교해 실시간 계산
const PIECES: Piece[] = [
  {
    slot: '상의',
    name: '크림 울 니트',
    brand: 'COS',
    tone: 0.06,
    mine: true,
    related: [
      { name: '램스울 라운드 니트', brand: 'Uniqlo U', price: '59,900', tone: 0.05 },
      { name: '캐시미어 블렌드 니트', brand: 'COS', price: '119,000', tone: 0.09 },
      { name: '핸드메이드 울 니트', brand: 'Andersson Bell', price: '198,000', tone: 0.13 },
    ],
  },
  {
    slot: '하의',
    name: '차콜 와이드 슬랙스',
    brand: 'Uniqlo',
    tone: 0.18,
    mine: true,
    related: [
      { name: '울 블렌드 와이드 슬랙스', brand: 'Uniqlo', price: '49,900', tone: 0.18 },
      { name: '테이퍼드 크롭 슬랙스', brand: 'COS', price: '135,000', tone: 0.2 },
    ],
  },
  {
    slot: '아우터',
    name: '오버핏 트렌치 코트',
    brand: 'Musinsa Standard',
    tone: 0.1,
    mine: false,
    related: [
      { name: '오버핏 트렌치 코트', brand: 'Musinsa Standard', price: '89,000', tone: 0.1 },
      { name: '벨티드 트렌치 코트', brand: 'COS', price: '259,000', tone: 0.12 },
    ],
  },
  {
    slot: '신발',
    name: '브라운 스웨이드 로퍼',
    brand: 'Dr.Martens',
    tone: 0.24,
    mine: true,
    related: [
      { name: '스웨이드 페니 로퍼', brand: 'SPUR', price: '69,000', tone: 0.24 },
      { name: '태슬 레더 로퍼', brand: 'Dr.Martens', price: '229,000', tone: 0.27 },
    ],
  },
];

const REASONS = [
  '8도의 쌀쌀한 날씨에 맞춰 니트+코트로 보온성을 확보했어요.',
  '추구하시는 미니멀 무드에 맞게 톤을 3가지로 절제했어요.',
  '옷장의 크림 니트를 중심으로 가진 아이템을 최대한 활용했어요.',
];

// C4 추천 룩 상세 — 2D 가상착장 + 구성 + 추천 이유 + 피드백
export default function LookDetail() {
  const { contentStyle } = useBreakpoint();
  const [saved, setSaved] = useState(false);
  const [vote, setVote] = useState<'up' | 'down' | null>(null);
  const [openSlot, setOpenSlot] = useState<string | null>(null);
  const toast = useToast();
  const { budget } = usePrefs();

  return (
    <View style={styles.container}>
      {/* 헤더 */}
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.card)]}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>추천 룩</Text>
          <Pressable hitSlop={12} onPress={() => setSaved((s) => !s)}>
            <Icon
              name={saved ? 'heart.fill' : 'heart'}
              tintColor={saved ? WINE : ink(0.5)}
              size={20}
            />
          </Pressable>
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(ContentMax.card)]}>
        {/* 2D 가상착장 — 탭하면 가상 피팅 화면으로 */}
        <Pressable style={styles.fitting} onPress={() => router.push('/fitting')}>
          <Text style={styles.fittingMark}>2D</Text>
          <Text style={styles.fittingLabel}>가상 착장 미리보기</Text>
          <View style={styles.fittingBadge}>
            <Icon name="figure.stand" tintColor="#fff" size={12} />
            <Text style={styles.fittingBadgeText}>내 체형 반영</Text>
          </View>
          <View style={styles.fittingCta}>
            <Icon name="sparkles" tintColor={INK} size={13} />
            <Text style={styles.fittingCtaText}>가상으로 입어보기</Text>
          </View>
        </Pressable>

        <View style={styles.body}>
          <Text style={styles.title}>포근한 니트 오피스룩</Text>
          <Text style={styles.subtitle}>서울 8° · 미니멀 · 출근</Text>

          {/* 구성 아이템 — 탭하면 비슷한/대체 상품 아코디언 */}
          <Text style={styles.sectionTitle}>구성 아이템</Text>
          <View style={styles.pieces}>
            {PIECES.map((p) => {
              const open = openSlot === p.slot;
              return (
                <View key={p.slot} style={[styles.pieceWrap, open && styles.pieceWrapOpen]}>
                  <Pressable style={styles.piece} onPress={() => setOpenSlot(open ? null : p.slot)}>
                    <View
                      style={[styles.pieceThumb, { backgroundColor: `rgba(28,25,23,${p.tone})` }]}
                    />
                    <View style={styles.pieceBody}>
                      <View style={styles.pieceTop}>
                        <Text style={styles.pieceSlot}>{p.slot}</Text>
                        <View style={[styles.ownTag, !p.mine && styles.newTag]}>
                          <Text style={[styles.ownTagText, !p.mine && styles.newTagText]}>
                            {p.mine ? '내 옷장' : '추천 구매'}
                          </Text>
                        </View>
                      </View>
                      <Text style={styles.pieceName}>{p.name}</Text>
                      <Text style={styles.pieceBrand}>{p.brand}</Text>
                    </View>
                    <Icon
                      name={open ? 'chevron.down' : 'chevron.right'}
                      tintColor={ink(0.3)}
                      size={16}
                    />
                  </Pressable>

                  {open ? (
                    <View style={styles.related}>
                      <Text style={styles.relatedHead}>
                        {budget != null
                          ? `비슷한 상품 · ${formatBudget(budget)} 예산 내 우선`
                          : '비슷한 상품'}
                      </Text>
                      {(budget != null
                        ? [...p.related].sort(
                            (a, b) =>
                              (parsePrice(a.price) <= budget ? 0 : 1) -
                              (parsePrice(b.price) <= budget ? 0 : 1),
                          )
                        : p.related
                      ).map((r) => {
                        const inBudget = budget != null && parsePrice(r.price) <= budget;
                        return (
                          <Pressable
                            key={r.name}
                            style={styles.relatedItem}
                            onPress={() => toast(`${r.brand} · ${r.name} 담았어요`)}>
                            <View
                              style={[
                                styles.relatedThumb,
                                { backgroundColor: `rgba(28,25,23,${r.tone})` },
                              ]}
                            />
                            <View style={styles.relatedBody}>
                              <Text style={styles.relatedName} numberOfLines={1}>
                                {r.name}
                              </Text>
                              <Text style={styles.relatedBrand}>{r.brand}</Text>
                            </View>
                            <View style={styles.relatedRight}>
                              <Text style={styles.relatedPrice}>{r.price}원</Text>
                              {inBudget ? (
                                <View style={styles.budgetTag}>
                                  <Text style={styles.budgetTagText}>예산 내</Text>
                                </View>
                              ) : null}
                            </View>
                          </Pressable>
                        );
                      })}
                      {budget == null ? (
                        <Pressable
                          style={styles.budgetPrompt}
                          onPress={() => router.push('/budget')}>
                          <Icon name="wallet" tintColor={ink(0.5)} size={14} />
                          <Text style={styles.budgetPromptText}>예산을 설정하면 예산 내 상품을 먼저 보여드려요</Text>
                        </Pressable>
                      ) : null}
                    </View>
                  ) : null}
                </View>
              );
            })}
          </View>

          {/* 추천 이유 */}
          <Text style={styles.sectionTitle}>왜 이 룩일까요?</Text>
          <View style={styles.reasonCard}>
            {REASONS.map((r, i) => (
              <View key={i} style={styles.reasonRow}>
                <View style={styles.pin}>
                  <Text style={styles.pinNum}>{i + 1}</Text>
                </View>
                <Text style={styles.reasonText}>{r}</Text>
              </View>
            ))}
          </View>

          {/* 피드백 */}
          <View style={styles.feedback}>
            <Text style={styles.feedbackLabel}>이 추천 어떠세요?</Text>
            <View style={styles.voteRow}>
              <Pressable
                style={[styles.voteBtn, vote === 'up' && styles.voteUpOn]}
                onPress={() => setVote('up')}>
                <Icon
                  name="hand.thumbsup"
                  tintColor={vote === 'up' ? '#fff' : ink(0.6)}
                  size={16}
                />
                <Text style={[styles.voteText, vote === 'up' && styles.voteTextOn]}>좋아요</Text>
              </Pressable>
              <Pressable
                style={[styles.voteBtn, vote === 'down' && styles.voteDownOn]}
                onPress={() => setVote('down')}>
                <Icon
                  name="hand.thumbsdown"
                  tintColor={vote === 'down' ? '#fff' : ink(0.6)}
                  size={16}
                />
                <Text style={[styles.voteText, vote === 'down' && styles.voteTextOn]}>별로예요</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </ScrollView>

      {/* 하단 바 */}
      <View style={styles.bottomDivider} />
      <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.card)]}>
        <Pressable style={styles.altBtn} onPress={() => router.back()}>
          <Text style={styles.altText}>다른 룩</Text>
        </Pressable>
        <Pressable
          style={styles.saveBtn}
          onPress={() => {
            setSaved(true);
            router.back();
          }}>
          <Icon name="bookmark.fill" tintColor="#fff" size={15} />
          <Text style={styles.saveText}>룩북에 저장</Text>
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
    paddingBottom: 10,
  },
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },

  content: { paddingBottom: 24 },

  fitting: {
    /* 고정 높이로 두면 폭이 넓어지는 데스크톱에서 가로로 납작해져 세로 사진이 잘린다.
       폰 폭(400) 기준 비율을 유지한다. */
    aspectRatio: 1.111,
    backgroundColor: BONE,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  fittingMark: { fontFamily: Fonts.serif, fontSize: 54, color: ink(0.2) },
  fittingLabel: { fontSize: 13, color: ink(0.4), letterSpacing: 0.5 },
  fittingBadge: {
    position: 'absolute',
    bottom: 16,
    right: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: INK,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderRadius: 999,
  },
  fittingBadgeText: { fontSize: 10.5, color: '#fff', fontWeight: '500' },
  fittingCta: {
    position: 'absolute',
    bottom: 16,
    left: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(255,255,255,0.92)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
  },
  fittingCtaText: { fontSize: 12.5, fontWeight: '600', color: INK },

  body: { paddingHorizontal: 20, paddingTop: 22 },
  title: { fontFamily: Fonts.serif, fontSize: 24, color: INK },
  subtitle: { fontSize: 13, color: ink(0.45), marginTop: 6 },

  sectionTitle: { fontSize: 13, fontWeight: '600', color: INK, marginTop: 28, marginBottom: 12 },

  pieces: { gap: 10 },
  pieceWrap: {
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 16,
    overflow: 'hidden',
  },
  pieceWrapOpen: { borderColor: ink(0.16) },
  piece: {
    flexDirection: 'row',
    gap: 12,
    padding: 10,
    alignItems: 'center',
  },
  pieceThumb: { width: 56, height: 56, borderRadius: 12, backgroundColor: BONE },
  pieceBody: { flex: 1, gap: 3 },
  pieceTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pieceSlot: { fontSize: 11, color: ink(0.4), fontWeight: '500' },
  ownTag: { backgroundColor: '#efe7db', paddingHorizontal: 7, paddingVertical: 2, borderRadius: 999 },
  ownTagText: { fontSize: 9.5, color: ink(0.55), fontWeight: '600' },
  newTag: { backgroundColor: '#f3e4de' },
  newTagText: { color: WINE },
  pieceName: { fontSize: 14, fontWeight: '500', color: ink(0.9) },
  pieceBrand: { fontSize: 12, color: ink(0.4) },

  // 관련/대체 상품 아코디언
  related: {
    borderTopWidth: 1,
    borderTopColor: ink(0.08),
    backgroundColor: '#faf9f7',
    paddingHorizontal: 10,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 10,
  },
  relatedHead: { fontSize: 11, color: ink(0.4), fontWeight: '600' },
  relatedItem: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  relatedThumb: { width: 44, height: 44, borderRadius: 10, backgroundColor: BONE },
  relatedBody: { flex: 1, gap: 2 },
  relatedName: { fontSize: 13, fontWeight: '500', color: ink(0.9) },
  relatedBrand: { fontSize: 11.5, color: ink(0.4) },
  relatedRight: { alignItems: 'flex-end', gap: 4 },
  relatedPrice: { fontSize: 13, fontWeight: '600', color: INK },
  budgetTag: {
    backgroundColor: '#e6efe6',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  budgetTagText: { fontSize: 9.5, color: '#3f6b3f', fontWeight: '700' },
  budgetPrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    marginTop: 2,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 10,
    backgroundColor: '#f3ece2',
  },
  budgetPromptText: { flex: 1, fontSize: 11.5, color: ink(0.55) },

  reasonCard: {
    backgroundColor: '#fcffff',
    borderRadius: 16,
    padding: 16,
    gap: 14,
  },
  reasonRow: { flexDirection: 'row', gap: 11, alignItems: 'flex-start' },
  pin: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: WINE,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  pinNum: { fontSize: 11, color: '#fff', fontWeight: '700' },
  reasonText: { flex: 1, fontSize: 13.5, color: ink(0.7), lineHeight: 20 },

  feedback: { marginTop: 28, alignItems: 'center', gap: 12 },
  feedbackLabel: { fontSize: 13, color: ink(0.5) },
  voteRow: { flexDirection: 'row', gap: 10 },
  voteBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingHorizontal: 22,
    height: 44,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  voteUpOn: { backgroundColor: INK, borderColor: INK },
  voteDownOn: { backgroundColor: ink(0.55), borderColor: ink(0.55) },
  voteText: { fontSize: 13.5, color: ink(0.6), fontWeight: '500' },
  voteTextOn: { color: '#fff' },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: '#fff',
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  altBtn: {
    height: 50,
    paddingHorizontal: 22,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
    alignItems: 'center',
    justifyContent: 'center',
  },
  altText: { fontSize: 14, color: ink(0.6), fontWeight: '500' },
  saveBtn: {
    flex: 1,
    flexDirection: 'row',
    gap: 8,
    height: 50,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveText: { fontSize: 14, color: '#fff', fontWeight: '500' },
});
