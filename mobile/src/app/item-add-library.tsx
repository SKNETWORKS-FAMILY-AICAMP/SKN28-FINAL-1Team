import { ContentMax } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { Icon } from '@/components/icon';
import { SmartImage } from '@/components/ui';
import { draftItem } from '@/state/draft-item';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;
const PAD = 20;

/** 팀 카탈로그 연동 전 목업 — 탭하면 등록 화면으로 */
const LIBRARY_ITEMS = [
  {
    id: 'c1',
    name: '오버사이즈 셔츠',
    brand: '무신사 스탠다드',
    image: 'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=400&h=500&fit=crop',
  },
  {
    id: 'c2',
    name: '울 블렌드 코트',
    brand: 'COS',
    image: 'https://images.unsplash.com/photo-1544966503-7cc5ac882d5f?w=400&h=500&fit=crop',
  },
  {
    id: 'c3',
    name: '데님 팬츠',
    brand: '유니클로',
    image: 'https://images.unsplash.com/photo-1591195853828-11db59a44f6b?w=400&h=500&fit=crop',
  },
  {
    id: 'c4',
    name: '레더 스니커즈',
    brand: '나이키',
    image: 'https://images.unsplash.com/photo-1549298916-b41d501d3772?w=400&h=500&fit=crop',
  },
];

export default function ItemAddLibraryScreen() {
  const { contentStyle } = useBreakpoint();
  const pick = (uri: string) => {
    draftItem.setPhoto(uri);
    router.replace('/item-add');
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <View style={[styles.header, contentStyle(ContentMax.default)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/closet')}>
            <Icon name="chevron.left" tintColor={INK} size={22} />
          </Pressable>
          <Text style={styles.title}>라이브러리</Text>
          <View style={styles.headerSpacer} />
        </View>
        <Text style={styles.hint}>카탈로그에서 옷을 골라 옷장에 추가해요</Text>

        <ScrollView contentContainerStyle={[styles.list, contentStyle(ContentMax.default)]}>
          {LIBRARY_ITEMS.map((item) => (
            <Pressable key={item.id} style={styles.row} onPress={() => pick(item.image)}>
              <SmartImage uri={item.image} width={64} height={80} radius={10} />
              <View style={styles.rowText}>
                <Text style={styles.rowName}>{item.name}</Text>
                <Text style={styles.rowBrand}>{item.brand}</Text>
              </View>
              <Icon name="chevron.right" tintColor={ink(0.3)} size={18} />
            </Pressable>
          ))}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: PAD,
    paddingVertical: 12,
  },
  title: { flex: 1, textAlign: 'center', fontSize: 16, fontWeight: '700', color: INK },
  headerSpacer: { width: 22 },
  hint: {
    fontSize: 12,
    color: ink(0.45),
    paddingHorizontal: PAD,
    marginBottom: 12,
  },
  list: { paddingHorizontal: PAD, paddingBottom: 24, gap: 10 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: ink(0.1),
  },
  rowText: { flex: 1, gap: 3 },
  rowName: { fontSize: 14, fontWeight: '600', color: INK },
  rowBrand: { fontSize: 12, color: ink(0.45) },
});
