import { Icon } from '@/components/icon';
import { SmartImage, useToast } from '@/components/ui';
import { formatBudget, parsePrice, usePrefs } from '@/state/prefs';
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Editorial, ink, Fonts } from '@/constants/theme';
import { TODAY_LOOK_IMAGE } from '@/constants/look-images';
import { LOOK_VARIANTS, resolveLookVariant } from '@/constants/today-look';
import { savedLookStore } from '@/state/saved';
import { useAuth } from '@/state/auth';
import { draftItem } from '@/state/draft-item';
import { brandScores, likesStore, useWishlist, wishKey } from '@/state/likes';
import { backTo, goBack } from '@/lib/goBack';
import { mallLabel, openExternal, productUrl } from '@/lib/mall';
import type { LookRelated } from '@/constants/today-look';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useHome } from '@/hooks/use-home';
import { DetailTwoPane } from '@/components/detail-two-pane';

const INK = Editorial.ink;
const WINE = Editorial.wine;
const BONE = Editorial.bone;

/** 저장 시 태그 — 무드·상황 서브텍스트에서 뽑는다('미니멀 · 데일리' → ['미니멀','데일리']) */
function tagsOf(subtitle: string): string[] {
  return subtitle.split('·').map((s) => s.trim()).filter(Boolean);
}

// C4 추천 룩 상세 — 2D 가상착장 + 구성 + 추천 이유 + 피드백
export default function LookDetail() {
  const { contentStyle, width } = useBreakpoint();
  // 2단(≥1280)일 땐 본문을 넓게, 세로로 쌓일 땐 좁게 잡아 사진·카드가 과하게 커지지 않게 한다.
  const maxW = width >= 1280 ? 960 : 720;
  /* 어떤 룩을 볼지는 주소가 정한다. 없으면 오늘의 룩. */
  const { id, from } = useLocalSearchParams<{ id?: string; from?: string }>();
  const look = resolveLookVariant(id);
  const PIECES = look.pieces;
  const lookTags = tagsOf(look.subtitle);
  /* 사진은 원격 URL 이 있으면 그것, 없으면 번들 목업(오늘의 룩) */
  const lookKey = look.image ? { image: look.image } : { asset: TODAY_LOOK_IMAGE };

  const [saved, setSaved] = useState(() => savedLookStore.isSaved(lookKey));
  const [vote, setVote] = useState<'up' | 'down' | null>(null);
  const [openSlot, setOpenSlot] = useState<string | null>(null);
  const toast = useToast();
  const { budget } = usePrefs();
  const wishlist = useWishlist();
  const { isLoggedIn } = useAuth();

  /* 찜한 브랜드 = 취향. 예산 다음 순위로 써서 관련 상품 순서를 정한다(아래 sortRelated). */
  const brands = useMemo(() => brandScores(wishlist), [wishlist]);
  const wishedIds = useMemo(() => new Set(wishlist.map((w) => w.id)), [wishlist]);

  /**
   * 관련 상품 정렬 — ①예산 안 ②찜한 브랜드 순.
   * 예산을 앞에 두는 이유: 살 수 없는 것을 아무리 취향에 맞게 올려도 소용이 없다.
   */
  const sortRelated = (items: LookRelated[]) =>
    [...items].sort((a, b) => {
      if (budget != null) {
        const fit = (p: LookRelated) => (parsePrice(p.price) <= budget ? 0 : 1);
        if (fit(a) !== fit(b)) return fit(a) - fit(b);
      }
      return (brands[b.brand] ?? 0) - (brands[a.brand] ?? 0);
    });

  const relatedHead = (() => {
    const parts: string[] = [];
    if (budget != null) parts.push(`${formatBudget(budget)} 예산 내 우선`);
    if (Object.keys(brands).length > 0) parts.push('찜한 브랜드 우선');
    return parts.length ? `비슷한 상품 · ${parts.join(' · ')}` : '비슷한 상품';
  })();

  /* [다른 룩] = 다음 변형으로. 이름 그대로 다른 룩을 보여준다 —
     예전엔 룩북으로 나가버려서 버튼 이름과 하는 일이 어긋나 있었다. */
  const showAnotherLook = () => {
    const at = LOOK_VARIANTS.findIndex((l) => l.id === look.id);
    const next = LOOK_VARIANTS[(at + 1) % LOOK_VARIANTS.length];
    router.setParams({ id: next.id });
    setOpenSlot(null);
    setVote(null);
  };

  /**
   * 이 옷을 내 옷장에 등록한다 — 등록 화면에서 사진을 확인하고 시작한다.
   * (같은 흐름을 저장 룩 상세에서도 쓴다)
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

  const toggleWish = (r: LookRelated, slot: string) => {
    const added = likesStore.toggleWish({
      name: r.name,
      brand: r.brand,
      price: r.price,
      tone: r.tone,
      link: r.link,
      mall: r.mall,
      slot,
    });
    toast(added ? '위시리스트에 담았어요' : '위시리스트에서 뺐어요');
  };

  /* 북마크 = 저장 토글. 켜면 '저장됨'에 담고, 끄면 뺀다.
     하트를 안 쓰는 이유 — 하트는 룩북 피드의 '좋아요'가 가져갔다. 한 아이콘이 화면마다
     다른 뜻이면 누르기 전에 무슨 일이 생길지 알 수 없다. */
  const toggleSave = () => {
    if (saved) {
      const found = savedLookStore
        .getLooks()
        .find((l) => (look.image ? l.image === look.image : l.asset === TODAY_LOOK_IMAGE));
      if (found) savedLookStore.removeLook(found.id);
      setSaved(false);
    } else {
      savedLookStore.addLook({
        ...lookKey,
        comment: look.title,
        tags: lookTags,
        reason: look.reasons[0],
      });
      setSaved(true);
      toast('저장됨에 담았어요');
    }
  };

  // 하단 '룩북에 저장' = 담고 룩북 저장됨 탭으로 이동.
  const saveAndGoLookbook = () => {
    savedLookStore.addLook({
      ...lookKey,
      comment: look.title,
      tags: lookTags,
      reason: look.reasons[0],
    });
    setSaved(true);
    router.push('/(tabs)/lookbook?tab=saved');
  };

  /* 서브텍스트의 날씨는 홈과 같은 출처(useHome)에서 실시간 값을 가져와 통일한다.
     아직 안 불러왔거나 API 실패 시엔 날씨를 생략하고 무드·상황만 보여준다. */
  const { data: home } = useHome();
  const w = home?.weather;
  const weatherPart = w && w.temperature != null ? `${w.region ?? '서울'} ${w.temperature}°` : null;
  const subtitle = [weatherPart, look.subtitle].filter(Boolean).join(' · ');

  return (
    <View style={styles.container}>
      {/* 헤더 */}
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(maxW)]}>
          {/* 들어온 자리(from)로 돌아간다. 없으면 홈.
              ⚠️ router.replace 를 직접 쓰지 말 것 — 웹에서 조용히 무시돼 버튼이 먹통이 된다(lib/goBack.ts). */}
          <Pressable hitSlop={12} onPress={() => goBack(backTo(from, '/(tabs)/home'))}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>추천 룩</Text>
          <Pressable
            style={styles.headerRight}
            hitSlop={12}
            onPress={toggleSave}
            accessibilityLabel={saved ? '저장 취소' : '저장'}>
            <Icon
              name={saved ? 'bookmark.fill' : 'bookmark'}
              tintColor={saved ? WINE : ink(0.5)}
              size={20}
            />
          </Pressable>
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(maxW)]}>
        {/* 데스크톱: [사진 | 상세·아이템] 2단 / 태블릿·모바일: 세로 */}
        <DetailTwoPane
          image={
            /* 2D 가상착장 — 탭하면 가상 피팅 화면으로 */
            <Pressable style={styles.fitting} onPress={() => router.push('/fitting')}>
          <SmartImage
            uri={look.image}
            asset={look.image ? undefined : TODAY_LOOK_IMAGE}
            width="100%"
            radius={0}
            contentFit="cover"
            style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
          />
          <View style={styles.fittingBadge}>
            <Icon name="figure.stand" tintColor="#fff" size={12} />
            <Text style={styles.fittingBadgeText}>내 체형 반영</Text>
          </View>
          <View style={styles.fittingCta}>
            <Icon name="sparkles" tintColor={INK} size={13} />
            <Text style={styles.fittingCtaText}>가상으로 입어보기</Text>
          </View>
            </Pressable>
          }
          details={
            <View style={styles.body}>
          <Text style={styles.title}>{look.title}</Text>
          <Text style={styles.subtitle}>{subtitle}</Text>

          {/* 구성 아이템 — 탭하면 비슷한/대체 상품 아코디언 */}
          <Text style={styles.sectionTitle}>구성 아이템</Text>
          <View style={styles.pieces}>
            {PIECES.map((p) => {
              const open = openSlot === p.slot;
              return (
                <View key={p.slot} style={[styles.pieceWrap, open && styles.pieceWrapOpen]}>
                  <Pressable style={styles.piece} onPress={() => setOpenSlot(open ? null : p.slot)}>
                    <View style={styles.pieceThumb}>
                      <SmartImage uri={p.image} width="100%" aspectRatio={1} radius={12} contentFit="cover" />
                    </View>
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
                    {/* 내 옷장에 없는 옷만 담을 수 있다. 이미 가진 옷을 또 넣으면 옷장이 겹친다.
                        사진이 없는 아이템도 뺀다 — 옷장 등록은 사진 한 장에서 시작한다. */}
                    {!p.mine && p.image ? (
                      <Pressable
                        style={styles.pieceAdd}
                        hitSlop={6}
                        onPress={() => addToCloset(p.image!)}
                        accessibilityLabel={`${p.name} 옷장에 추가`}>
                        <Icon name="plus" tintColor={INK} size={13} />
                        <Text style={styles.pieceAddText}>옷장에</Text>
                      </Pressable>
                    ) : null}
                    <Icon
                      name={open ? 'chevron.down' : 'chevron.right'}
                      tintColor={ink(0.3)}
                      size={16}
                    />
                  </Pressable>

                  {open ? (
                    <View style={styles.related}>
                      <Text style={styles.relatedHead}>{relatedHead}</Text>
                      {sortRelated(p.related).map((r) => {
                        const inBudget = budget != null && parsePrice(r.price) <= budget;
                        const wished = wishedIds.has(wishKey(r));
                        const url = productUrl(r, r.mall);
                        return (
                          <View key={r.name} style={styles.relatedItem}>
                            {/* 상품 본문을 누르면 판매처로 나간다 — 우리는 결제를 받지 않는다. */}
                            <Pressable
                              style={styles.relatedMain}
                              onPress={() => openExternal(url)}
                              accessibilityLabel={`${r.brand} ${r.name} — ${mallLabel(url)}에서 보기`}>
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
                                <View style={styles.relatedMeta}>
                                  <Text style={styles.relatedBrand}>{r.brand}</Text>
                                  <Icon name="arrow.up.right.square" tintColor={ink(0.32)} size={11} />
                                  <Text style={styles.relatedMall}>{mallLabel(url)}</Text>
                                </View>
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
                            <Pressable
                              style={styles.wishBtn}
                              hitSlop={6}
                              onPress={() => toggleWish(r, p.slot)}
                              accessibilityLabel={wished ? '위시리스트에서 빼기' : '위시리스트에 담기'}>
                              <Icon
                                name={wished ? 'heart.fill' : 'heart'}
                                tintColor={wished ? WINE : ink(0.35)}
                                size={17}
                              />
                            </Pressable>
                          </View>
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

          {/* 담아 둔 상품으로 가는 길 — 아코디언을 닫으면 찜한 게 어디 갔는지 알 수 없어서 둔다. */}
          {wishlist.length > 0 ? (
            <Pressable style={styles.wishLink} onPress={() => router.push('/wishlist')}>
              <Icon name="heart.fill" tintColor={WINE} size={14} />
              <Text style={styles.wishLinkText}>위시리스트 {wishlist.length}개 보기</Text>
              <Icon name="chevron.right" tintColor={ink(0.3)} size={14} />
            </Pressable>
          ) : null}

          {/* 추천 이유 */}
          <Text style={styles.sectionTitle}>왜 이 룩일까요?</Text>
          <View style={styles.reasonCard}>
            {look.reasons.map((r, i) => (
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
          }
        />
      </ScrollView>

      {/* 하단 바 */}
      <View style={styles.bottomDivider} />
      <View style={[styles.bottomBar, { paddingBottom: 12 }, contentStyle(maxW)]}>
        <Pressable style={styles.altBtn} onPress={showAnotherLook}>
          <Text style={styles.altText}>다른 룩</Text>
        </Pressable>
        <Pressable style={styles.saveBtn} onPress={saveAndGoLookbook}>
          <Icon name="bookmark.fill" tintColor="#fff" size={15} />
          <Text style={styles.saveText}>룩북에 저장</Text>
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
    gap: 10,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
  },
  // 제목을 뒤로가기 버튼 바로 옆에 붙이고, 우측 아이콘은 끝으로 민다.
  headerRight: { marginLeft: 'auto' },
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
    /* 절대배치된 미리보기 사진이 밖으로 넘쳐 헤더·하단 버튼을 덮지 않도록 잘라낸다. */
    overflow: 'hidden',
  },
  fittingMark: { fontFamily: Fonts.serif, fontSize: 54, color: Editorial.textMuted },
  fittingLabel: { fontSize: 13, color: Editorial.textCaption, letterSpacing: 0.5 },
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
  subtitle: { fontSize: 13, color: Editorial.textCaption, marginTop: 6 },

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
  pieceThumb: { width: 56, height: 56, borderRadius: 12, backgroundColor: BONE, overflow: 'hidden' },
  pieceBody: { flex: 1, gap: 3 },
  pieceTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pieceSlot: { fontSize: 11, color: Editorial.textCaption, fontWeight: '500' },
  ownTag: { backgroundColor: Editorial.surfaceTag, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 999 },
  ownTagText: { fontSize: 9.5, color: Editorial.textCaption, fontWeight: '600' },
  newTag: { backgroundColor: Editorial.accent },
  newTagText: { color: WINE },
  pieceName: { fontSize: 14, fontWeight: '500', color: Editorial.ink },
  pieceAdd: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    height: 28,
    paddingHorizontal: 9,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  pieceAddText: { fontSize: 11, fontWeight: '600', color: INK },
  pieceBrand: { fontSize: 12, color: Editorial.textCaption },

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
  relatedHead: { fontSize: 11, color: Editorial.textCaption, fontWeight: '600' },
  relatedItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  // 상품 본문(→판매처)과 찜 버튼을 갈라 놓는다. 한 행에서 두 동작이 갈리므로 영역도 나눈다.
  relatedMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 },
  relatedThumb: { width: 44, height: 44, borderRadius: 10, backgroundColor: BONE },
  relatedBody: { flex: 1, gap: 2 },
  relatedName: { fontSize: 13, fontWeight: '500', color: Editorial.ink },
  relatedMeta: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  relatedBrand: { fontSize: 11.5, color: Editorial.textCaption },
  relatedMall: { fontSize: 11, color: Editorial.textMuted },
  wishBtn: { width: 32, height: 32, alignItems: 'center', justifyContent: 'center' },
  wishLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  wishLinkText: { flex: 1, fontSize: 13, color: Editorial.textSoft, fontWeight: '500' },
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
    backgroundColor: Editorial.surface,
    borderWidth: 1, borderColor: Editorial.line,
  },
  budgetPromptText: { flex: 1, fontSize: 11.5, color: Editorial.textCaption },

  reasonCard: {
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1, borderColor: Editorial.line,
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
  reasonText: { flex: 1, fontSize: 13.5, color: Editorial.textSoft, lineHeight: 20 },

  feedback: { marginTop: 28, alignItems: 'center', gap: 12 },
  feedbackLabel: { fontSize: 13, color: Editorial.textCaption },
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
  voteUpOn: { backgroundColor: Editorial.selected, borderColor: Editorial.selected },
  voteDownOn: { backgroundColor: ink(0.55), borderColor: ink(0.55) },
  voteText: { fontSize: 13.5, color: Editorial.textCaption, fontWeight: '500' },
  voteTextOn: { color: '#fff' },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: {
    flexDirection: 'row',
    gap: 10,
    backgroundColor: Editorial.page,
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
  altText: { fontSize: 14, color: Editorial.textCaption, fontWeight: '500' },
  saveBtn: {
    flex: 1,
    flexDirection: 'row',
    gap: 8,
    height: 50,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveText: { fontSize: 14, color: '#fff', fontWeight: '500' },
});
