import { Icon, type IconName } from '@/components/icon';
import { useToast } from '@/components/ui';
import { ContentMax } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { pickFromAlbum, pickFromCamera } from '@/lib/pickItemPhoto';
import { draftItem } from '@/state/draft-item';
import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;
const PAD = 20;

/* 타일 폭은 창 폭에서 파생 → 컴포넌트 안에서 useBreakpoint() 로 구한다. */
const GAP = 10;

type SourceKey = 'album' | 'camera' | 'web' | 'library';

const SOURCES: { key: SourceKey; label: string; icon: IconName; hint: string }[] = [
  { key: 'album', label: '앨범', icon: 'photo.on.rectangle', hint: '갤러리에서 선택' },
  { key: 'camera', label: '카메라', icon: 'camera', hint: '직접 촬영' },
  { key: 'web', label: 'Web', icon: 'globe', hint: '쇼핑몰에서 가져오기' },
  { key: 'library', label: '라이브러리', icon: 'building.columns', hint: '카탈로그에서 선택' },
];

export default function ItemAddSourceScreen() {
  const { frameWidth, contentStyle } = useBreakpoint();
  const tileW = (frameWidth - PAD * 2 - GAP) / 2;

  const toast = useToast();
  const [active, setActive] = useState<SourceKey | null>(null);
  const [loading, setLoading] = useState(false);

  const goToRegister = (uri: string) => {
    draftItem.setPhoto(uri);
    router.replace('/item-add');
  };

  const handlePick = async (key: SourceKey) => {
    setActive(key);
    if (key === 'web') {
      router.push('/import');
      return;
    }
    if (key === 'library') {
      router.push('/item-add-library');
      return;
    }

    setLoading(true);
    try {
      const uri =
        key === 'album' ? await pickFromAlbum() : await pickFromCamera();
      if (!uri) return;
      // TODO: rembg 누끼 처리 후 uri 교체
      goToRegister(uri);
    } catch {
      toast('사진을 불러오지 못했어요', { variant: 'error' });
    } finally {
      setLoading(false);
      setActive(null);
    }
  };

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => router.back()} style={styles.backBtn}>
            <Icon name="chevron.left" tintColor={INK} size={22} />
          </Pressable>
          <View style={styles.searchMock}>
            <Icon name="magnifyingglass" tintColor={ink(0.35)} size={16} />
            <Text style={styles.searchPlaceholder}>아이템 설명</Text>
            <Icon name="camera" tintColor={ink(0.35)} size={16} />
          </View>
          <Pressable hitSlop={12} style={styles.helpBtn}>
            <Icon name="questionmark.circle" tintColor={ink(0.45)} size={20} />
          </Pressable>
        </View>

        <Text style={styles.sectionTitle}>직접 추가</Text>
        <Text style={styles.sectionHint}>사진을 올리면 AI가 누끼 처리·분류해요</Text>

        <View style={[styles.grid, contentStyle(ContentMax.narrow)]}>
          {SOURCES.map((src) => {
            const on = active === src.key;
            return (
              <Pressable
                key={src.key}
                style={[styles.tile, { width: tileW, height: tileW * 0.88 }, on && styles.tileOn]}
                onPress={() => handlePick(src.key)}
                disabled={loading}>
                <Icon
                  name={src.icon}
                  tintColor={on ? '#fff' : ink(0.55)}
                  size={26}
                />
                <Text style={[styles.tileLabel, on && styles.tileLabelOn]}>{src.label}</Text>
                <Text style={[styles.tileHint, on && styles.tileHintOn]} numberOfLines={1}>
                  {src.hint}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {loading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator color={INK} />
            <Text style={styles.loadingText}>사진 불러오는 중…</Text>
          </View>
        ) : null}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#ffffff' },
  safe: { flex: 1, paddingHorizontal: PAD },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 8,
    marginBottom: 28,
  },
  backBtn: { width: 28, alignItems: 'flex-start' },
  searchMock: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    height: 44,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#f3ece2',
  },
  searchPlaceholder: { flex: 1, fontSize: 14, color: ink(0.35) },
  helpBtn: { width: 28, alignItems: 'flex-end' },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: INK },
  sectionHint: { fontSize: 12, color: ink(0.45), marginTop: 4, marginBottom: 16 },

  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: GAP,
  },
  // width/height 는 창 폭에서 파생되므로 컴포넌트에서 인라인으로 덧붙인다.
  tile: {
    borderRadius: 14,
    borderWidth: 1,
    borderColor: ink(0.12),
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingHorizontal: 8,
  },
  tileOn: {
    backgroundColor: INK,
    borderColor: INK,
  },
  tileLabel: { fontSize: 15, fontWeight: '600', color: INK },
  tileLabelOn: { color: '#fff' },
  tileHint: { fontSize: 11, color: ink(0.4) },
  tileHintOn: { color: 'rgba(255,255,255,0.72)' },

  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginTop: 24,
  },
  loadingText: { fontSize: 13, color: ink(0.5) },
});
