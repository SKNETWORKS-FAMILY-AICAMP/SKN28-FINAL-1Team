import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Icon } from '@/components/icon';
import { WishPanel } from '@/components/wish-panel';
import { ContentMax, Editorial } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { goBack } from '@/lib/goBack';
import { useWishlist } from '@/state/likes';

const INK = Editorial.ink;

/**
 * 찜한 상품 — 마이에서 들어오는 단독 화면.
 *
 * 같은 목록이 옷장의 [찜] 탭에도 선다. 본문은 WishPanel 하나를 같이 쓰고,
 * 여기서는 헤더와 '옷장에서 보기' 안내만 얹는다 — 두 자리가 어긋나면 어느 쪽이
 * 진짜인지 알 수 없게 된다.
 */
export default function WishlistScreen() {
  const { contentStyle } = useBreakpoint();
  const items = useWishlist();

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.headerSafe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/my')}>
            <Icon name="chevron.left" tintColor={INK} size={20} />
          </Pressable>
          <Text style={styles.headerTitle}>찜한 상품</Text>
          {items.length > 0 ? (
            <Pressable
              style={styles.headerRight}
              hitSlop={10}
              onPress={() => router.push('/(tabs)/closet?tab=wish')}>
              <Text style={styles.linkText}>옷장에서 보기</Text>
            </Pressable>
          ) : null}
        </View>
      </SafeAreaView>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.content,
          { paddingBottom: 24 },
          contentStyle(ContentMax.narrow),
        ]}>
        <WishPanel />
      </ScrollView>
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
  headerTitle: { fontSize: 15, fontWeight: '600', color: INK },
  headerRight: { marginLeft: 'auto' },
  linkText: { fontSize: 13, color: Editorial.textCaption },

  content: { paddingHorizontal: 20, paddingTop: 8 },
});
