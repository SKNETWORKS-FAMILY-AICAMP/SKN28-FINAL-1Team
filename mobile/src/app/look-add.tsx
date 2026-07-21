import { Icon } from '@/components/icon';
import { SmartImage, useToast } from '@/components/ui';
import { GridCard, gridCardImageHeight, gridCardWidth } from '@/constants/theme';
import { pickFromAlbum, pickFromCamera } from '@/lib/pickItemPhoto';
import {
  ALLOWED_HASHTAGS,
  type AllowedHashtag,
  lookbookStore,
} from '@/state/lookbook';
import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const INK = '#1c1917';
const ink = (a: number) => `rgba(28,25,23,${a})`;
const PAD = 20;

const CARD_W = gridCardWidth(Dimensions.get('window').width);
const PREVIEW_H = gridCardImageHeight(CARD_W);

export default function LookAddScreen() {
  const toast = useToast();
  const [image, setImage] = useState<string | null>(null);
  const [tags, setTags] = useState<AllowedHashtag[]>([]);
  const [loading, setLoading] = useState(false);

  const toggleTag = (tag: AllowedHashtag) => {
    setTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag],
    );
  };

  const pick = async (kind: 'album' | 'camera') => {
    setLoading(true);
    try {
      const uri = kind === 'album' ? await pickFromAlbum() : await pickFromCamera();
      if (uri) setImage(uri);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = () => {
    if (!image || tags.length === 0) return;
    lookbookStore.addLook({ image, tags });
    toast('룩을 올렸어요', { variant: 'success' });
    router.back();
  };

  const canSave = Boolean(image && tags.length > 0);

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top', 'bottom']} style={styles.safe}>
        <View style={styles.header}>
          <Pressable hitSlop={12} onPress={() => router.back()}>
            <Icon name="chevron.left" tintColor={INK} size={22} />
          </Pressable>
          <Text style={styles.title}>룩 올리기</Text>
          <View style={styles.headerSpacer} />
        </View>

        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.previewWrap}>
            {image ? (
              <SmartImage uri={image} width="100%" height={PREVIEW_H} radius={GridCard.radius} />
            ) : (
              <View style={[styles.previewEmpty, { height: PREVIEW_H }]}>
                <Icon name="photo" tintColor={ink(0.28)} size={36} />
                <Text style={styles.previewHint}>룩 사진을 추가해 주세요</Text>
              </View>
            )}
          </View>

          <View style={styles.pickRow}>
            <Pressable style={styles.pickBtn} onPress={() => pick('album')} disabled={loading}>
              <Icon name="photo.on.rectangle" tintColor={INK} size={18} />
              <Text style={styles.pickLabel}>앨범</Text>
            </Pressable>
            <Pressable style={styles.pickBtn} onPress={() => pick('camera')} disabled={loading}>
              <Icon name="camera" tintColor={INK} size={18} />
              <Text style={styles.pickLabel}>카메라</Text>
            </Pressable>
          </View>

          {loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={INK} />
            </View>
          ) : null}

          <Text style={styles.sectionTitle}>해시태그</Text>
          <Text style={styles.sectionHint}>아래 목록에서만 선택할 수 있어요</Text>
          <View style={styles.tagRow}>
            {ALLOWED_HASHTAGS.map((tag) => {
              const on = tags.includes(tag);
              return (
                <Pressable
                  key={tag}
                  onPress={() => toggleTag(tag)}
                  style={[styles.tag, on && styles.tagOn]}>
                  <Text style={[styles.tagText, on && styles.tagTextOn]}>#{tag}</Text>
                </Pressable>
              );
            })}
          </View>
        </ScrollView>

        <View style={styles.footer}>
          <Pressable
            style={[styles.saveBtn, !canSave && styles.saveBtnDisabled]}
            onPress={handleSave}
            disabled={!canSave}>
            <Text style={styles.saveText}>룩북에 올리기</Text>
          </Pressable>
        </View>
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
  content: { paddingHorizontal: PAD, paddingBottom: 24 },
  previewWrap: { marginBottom: 14 },
  previewEmpty: {
    borderRadius: GridCard.radius,
    backgroundColor: '#eae0d3',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  previewHint: { fontSize: 13, color: ink(0.45) },
  pickRow: { flexDirection: 'row', gap: 10, marginBottom: 24 },
  pickBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 44,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: ink(0.12),
    backgroundColor: '#f3ece2',
  },
  pickLabel: { fontSize: 14, fontWeight: '600', color: INK },
  loadingRow: { alignItems: 'center', marginBottom: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: INK },
  sectionHint: { fontSize: 12, color: ink(0.45), marginTop: 4, marginBottom: 14 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tag: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: ink(0.12),
  },
  tagOn: { backgroundColor: INK, borderColor: INK },
  tagText: { fontSize: 13, fontWeight: '500', color: ink(0.55) },
  tagTextOn: { color: '#fff' },
  footer: { paddingHorizontal: PAD, paddingTop: 12, paddingBottom: 8 },
  saveBtn: {
    height: 48,
    borderRadius: 999,
    backgroundColor: INK,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveBtnDisabled: { opacity: 0.35 },
  saveText: { fontSize: 15, fontWeight: '600', color: '#fff' },
});
