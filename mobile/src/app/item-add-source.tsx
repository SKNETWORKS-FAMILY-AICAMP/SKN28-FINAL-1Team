import { Icon, type IconName } from '@/components/icon';
import { useToast, ModalShell } from '@/components/ui';
import { Editorial, ink, ContentMax } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { pickFromAlbum, pickFromCamera } from '@/lib/pickItemPhoto';
import { draftItem } from '@/state/draft-item';
import { router } from 'expo-router';
import { goBack } from '@/lib/goBack';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = Editorial.ink;
const PAD = 20;

/* 타일 폭은 창 폭에서 파생 → 컴포넌트 안에서 useBreakpoint() 로 구한다. */
const GAP = 10;

type SourceKey = 'album' | 'camera' | 'web';

/* 세 갈래로 충분하다. 앨범·카메라는 내 사진, Web 은 쇼핑몰에서 가져오기.
   '라이브러리'(앱 카탈로그에서 고르기)는 뺐다 — 카탈로그 사진을 내 옷으로 업로드하면
   실제로 갖고 있지 않은 옷이 옷장에 들어간다. */
const SOURCES: { key: SourceKey; label: string; icon: IconName; hint: string }[] = [
  { key: 'album', label: '앨범', icon: 'photo.on.rectangle', hint: '갤러리에서 선택' },
  { key: 'camera', label: '카메라', icon: 'camera', hint: '직접 촬영' },
  { key: 'web', label: 'Web', icon: 'globe', hint: '쇼핑몰에서' },
];

export default function ItemAddSourceScreen() {
  const { contentStyle } = useBreakpoint();
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
    <ModalShell maxWidth={ContentMax.card}>
      <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
          <Pressable hitSlop={12} onPress={() => goBack('/(tabs)/closet')} style={styles.backBtn}>
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

        {/* 세 갈래를 한 줄에. 폭은 flex 로 나눠 가지므로 창 폭에 따라 계산할 필요가 없다. */}
        <View style={[styles.grid, contentStyle(ContentMax.narrow)]}>
          {SOURCES.map((src) => {
            const on = active === src.key;
            return (
              <Pressable
                key={src.key}
                style={[styles.tile, on && styles.tileOn]}
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
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
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
    backgroundColor: Editorial.control,
    borderWidth: 1, borderColor: Editorial.line,
  },
  searchPlaceholder: { flex: 1, fontSize: 14, color: Editorial.textCaption },
  helpBtn: { width: 28, alignItems: 'flex-end' },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: INK, marginBottom: 14 },

  grid: {
    flexDirection: 'row',
    gap: GAP,
  },
  tile: {
    /* 세 칸이 남는 폭을 똑같이 나눈다 — 폭을 직접 계산하면 좁은 창에서 넘쳐 줄이 바뀌었다. */
    flex: 1,
    minWidth: 0,
    aspectRatio: 0.92,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: ink(0.12),
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingHorizontal: 6,
  },
  tileOn: {
    backgroundColor: Editorial.selected,
    borderColor: Editorial.selected,
  },
  tileLabel: { fontSize: 15, fontWeight: '600', color: INK },
  tileLabelOn: { color: '#fff' },
  tileHint: { fontSize: 11, color: Editorial.textCaption },
  tileHintOn: { color: 'rgba(255,255,255,0.72)' },

  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginTop: 24,
  },
  loadingText: { fontSize: 13, color: Editorial.textCaption },
});
