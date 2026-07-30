import { Icon } from '@/components/icon';
import { ErrorState, LoadingState, SmartImage, useConfirm, useToast } from '@/components/ui';
import { router, useLocalSearchParams } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ItemTagSheet } from '@/components/closet/item-tag-sheet';
import { DetailTwoPane } from '@/components/detail-two-pane';
import { Editorial, ink, Fonts } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useWardrobeItem } from '@/hooks/use-wardrobe';
import { deleteWardrobeItem, itemDisplayName, type WardrobeApiItem } from '@/lib/wardrobeApi';

const INK = Editorial.ink;
const BONE = Editorial.bone;

/** 스펙 표에 올릴 것 — 값이 빈 항목은 서버가 못 채운 것이라 아예 빼고 보여준다. */
function specsOf(item: WardrobeApiItem): { label: string; value: string }[] {
  return [
    { label: '색', value: item.color },
    { label: '소재', value: item.material },
    { label: '핏', value: item.fit },
    { label: '패턴', value: item.pattern },
    { label: '소매', value: item.sleeve },
    { label: '기장', value: item.length },
    { label: '계절', value: item.season.join('·') },
  ].filter((s) => s.value);
}

// D3 아이템 상세 — 태그 확인·수정·삭제
export default function ItemDetail() {
  const { contentStyle, width } = useBreakpoint();
  const maxW = width >= 1280 ? 960 : 720;
  const { id } = useLocalSearchParams<{ id?: string }>();

  const { item, loading, error, reload, setItem } = useWardrobeItem(id);
  const [editing, setEditing] = useState(false);
  const toast = useToast();
  const confirm = useConfirm();

  const onDelete = async () => {
    if (!item) return;
    const ok = await confirm({
      title: '이 아이템을 삭제할까요?',
      message: '삭제하면 되돌릴 수 없어요.',
      confirmLabel: '삭제',
      destructive: true,
    });
    if (!ok) return;
    try {
      await deleteWardrobeItem(item.id);
      toast('삭제했어요', { variant: 'success' });
      goBack('/(tabs)/closet');
    } catch (e) {
      toast(e instanceof Error ? e.message : '삭제하지 못했어요', { variant: 'error' });
    }
  };

  const header = (
    <SafeAreaView edges={['top']} style={styles.headerSafe}>
      <View style={[styles.header, contentStyle(maxW)]}>
        <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/closet')}>
          <Icon name="chevron.left" tintColor={INK} size={20} />
        </Pressable>
        {item ? (
          <View style={styles.headerActions}>
            <Pressable hitSlop={10} onPress={() => setEditing(true)} accessibilityLabel="태그 수정">
              <Icon name="square.and.pencil" tintColor={ink(0.6)} size={19} />
            </Pressable>
            <Pressable hitSlop={10} onPress={onDelete} accessibilityLabel="삭제">
              <Icon name="trash" tintColor={ink(0.6)} size={18} />
            </Pressable>
          </View>
        ) : null}
      </View>
    </SafeAreaView>
  );

  if (loading) {
    return (
      <View style={styles.container}>
        {header}
        <LoadingState message="아이템을 불러오는 중…" style={styles.state} />
      </View>
    );
  }

  if (error || !item) {
    return (
      <View style={styles.container}>
        {header}
        <ErrorState
          title="아이템을 불러오지 못했어요"
          description={error ?? '옷장에서 다시 열어 주세요.'}
          onRetry={reload}
          style={styles.state}
        />
      </View>
    );
  }

  const specs = specsOf(item);
  const category = [item.category_large, item.category_small].filter(Boolean).join(' · ');

  return (
    <View style={styles.container}>
      {header}

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[styles.content, contentStyle(maxW)]}>
        {/* 데스크톱: [사진 | 상세] 2단 / 태블릿·모바일: 세로 */}
        <DetailTwoPane
          image={
            <View style={styles.image}>
              {/* 바깥 View 가 비율로 크기를 잡으므로 사진은 그 안을 절대좌표로 채운다 */}
              <SmartImage
                uri={item.image_url}
                width="100%"
                radius={20}
                contentFit="cover"
                style={styles.imageFill}
              />
              <View style={styles.catBadge}>
                <Text style={styles.catBadgeText}>{category}</Text>
              </View>
            </View>
          }
          details={
            <View style={styles.body}>
              <Text style={styles.name}>{itemDisplayName(item)}</Text>
              {item.style.length > 0 ? (
                <Text style={styles.styleLine}>{item.style.join(' · ')}</Text>
              ) : null}

              {/* 확인 대기 — 확정 전에는 추천에 쓰이지 않는다는 걸 알려준다 */}
              {!item.confirmed ? (
                <View style={styles.pending}>
                  <Icon name="exclamationmark.triangle" tintColor={Editorial.wine} size={15} />
                  <Text style={styles.pendingText}>
                    아직 확인하지 않은 아이템이에요. 태그를 확인하면 추천에 함께 쓰여요.
                  </Text>
                </View>
              ) : null}

              {specs.length > 0 ? (
                <View style={styles.specGrid}>
                  {specs.map((s) => (
                    <View key={s.label} style={styles.specTile}>
                      <Text style={styles.specLabel}>{s.label}</Text>
                      <Text style={styles.specValue}>{s.value}</Text>
                    </View>
                  ))}
                </View>
              ) : (
                <Pressable style={styles.noSpec} onPress={() => setEditing(true)}>
                  <Text style={styles.noSpecText}>
                    태그가 아직 비어 있어요. 눌러서 채워 주세요.
                  </Text>
                </Pressable>
              )}

              <Pressable style={styles.editRow} onPress={() => setEditing(true)}>
                <Icon name="square.and.pencil" tintColor={ink(0.55)} size={15} />
                <Text style={styles.editText}>태그 수정</Text>
              </Pressable>
            </View>
          }
        />
      </ScrollView>

      <View style={styles.bottomDivider} />
      <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(maxW)]}>
        <Pressable style={styles.cta} onPress={() => router.push('/chat-mode')}>
          <Icon name="sparkles" tintColor="#fff" size={15} />
          <Text style={styles.ctaText}>이 옷으로 코디 추천받기</Text>
        </Pressable>
      </SafeAreaView>

      <ItemTagSheet
        visible={editing}
        item={item}
        onClose={() => setEditing(false)}
        onSaved={setItem}
      />
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
  state: { paddingTop: 80 },

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
  imageFill: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  catBadge: {
    position: 'absolute',
    top: 14,
    left: 14,
    backgroundColor: 'rgba(255,255,255,0.9)',
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: 999,
  },
  catBadgeText: { fontSize: 11, fontWeight: '600', color: Editorial.textSoft },

  body: { paddingHorizontal: 20, paddingTop: 22 },
  name: { fontFamily: Fonts.serif, fontSize: 26, color: INK },
  styleLine: { fontSize: 14, color: Editorial.textCaption, marginTop: 5 },

  pending: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    marginTop: 18,
    backgroundColor: Editorial.accent,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  pendingText: { flex: 1, fontSize: 12.5, color: Editorial.wine, lineHeight: 18 },

  specGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 22,
    borderWidth: 1,
    borderColor: ink(0.09),
    borderRadius: 16,
    overflow: 'hidden',
  },
  specTile: { width: '50%', paddingHorizontal: 16, paddingVertical: 15, gap: 5 },
  specLabel: { fontSize: 11, color: Editorial.textCaption },
  specValue: { fontSize: 14.5, fontWeight: '500', color: Editorial.ink },

  noSpec: {
    marginTop: 22,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: Editorial.line,
    borderRadius: 16,
    paddingVertical: 22,
    alignItems: 'center',
  },
  noSpecText: { fontSize: 13, color: Editorial.textCaption },

  editRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    alignSelf: 'flex-start',
    marginTop: 18,
    paddingHorizontal: 14,
    height: 40,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.14),
  },
  editText: { fontSize: 13, fontWeight: '600', color: INK },

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
