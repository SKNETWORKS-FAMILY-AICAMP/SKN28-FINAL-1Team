import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PhotoSourceSheet } from '@/components/closet/photo-source-sheet';
import { Icon } from '@/components/icon';
import { ModalShell, useToast } from '@/components/ui';
import { ContentMax, Editorial, ink, Type } from '@/constants/theme';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { draftItem, useDraftPhoto } from '@/state/draft-item';
import { uploadJobs } from '@/state/upload-jobs';

const INK = Editorial.ink;

/**
 * D2 아이템 등록 — 사진을 확인하고 등록을 시작한다.
 *
 * 등록은 서버 큐를 타서 시간이 걸리므로 **이 화면에서 기다리지 않는다.**
 * 시작하면 바로 옷장으로 돌아가고, 진행 상황은 옷장 위쪽에 표시된다
 * (state/upload-jobs.ts). 처리가 끝나면 옷장 목록에 자동으로 나타난다.
 */
export default function ItemAddScreen() {
  const { contentStyle } = useBreakpoint();
  const photo = useDraftPhoto();
  const toast = useToast();
  const [sourceOpen, setSourceOpen] = useState(false);

  const close = () => {
    draftItem.setPhoto(null);
    router.replace('/(tabs)/closet');
  };

  const start = () => {
    if (!photo) {
      setSourceOpen(true);
      return;
    }
    uploadJobs.start(photo);
    toast('등록을 시작했어요');
    close();
  };

  return (
    <ModalShell maxWidth={ContentMax.narrow}>
      <View style={styles.container}>
        <SafeAreaView edges={['top']} style={styles.headerSafe}>
          <View style={[styles.header, contentStyle(ContentMax.narrow)]}>
            <View style={styles.headerText}>
              <Text style={styles.title}>아이템 등록</Text>
              <Text style={styles.subtitle}>
                등록을 시작하면 옷장에서 진행 상황을 볼 수 있어요
              </Text>
            </View>
            <Pressable hitSlop={12} onPress={close} accessibilityLabel="닫기">
              <Icon name="xmark" tintColor={ink(0.5)} size={18} />
            </Pressable>
          </View>
        </SafeAreaView>
        <View style={styles.divider} />

        <ScrollView contentContainerStyle={[styles.content, contentStyle(ContentMax.narrow)]}>
          <Pressable style={styles.photo} onPress={() => setSourceOpen(true)}>
            {photo ? (
              <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} contentFit="cover" />
            ) : (
              <View style={styles.photoEmpty}>
                <Text style={styles.photoEmptyIcon}>＋</Text>
                <Text style={styles.photoEmptyText}>사진 추가하기</Text>
              </View>
            )}
          </Pressable>

          <Text style={styles.hint}>
            사진 한 장에 여러 벌이 있어도 괜찮아요. AI가 옷을 나눠 각각 등록해요.
          </Text>
        </ScrollView>

        <View style={styles.bottomDivider} />
        <SafeAreaView edges={['bottom']} style={[styles.bottomBar, contentStyle(ContentMax.narrow)]}>
          <Pressable
            style={[styles.primaryBtn, !photo && styles.primaryBtnOff]}
            onPress={start}
            disabled={!photo}>
            <Text style={styles.primaryText}>등록 시작</Text>
          </Pressable>
        </SafeAreaView>

        {/* 사진을 다시 고를 때도 화면을 옮기지 않고 시트로 띄운다 */}
        <PhotoSourceSheet visible={sourceOpen} onClose={() => setSourceOpen(false)} />
      </View>
    </ModalShell>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },

  headerSafe: { backgroundColor: Editorial.page },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 14,
    paddingBottom: 12,
  },
  headerText: { flex: 1, gap: 4 },
  title: { fontSize: Type.lead, fontWeight: '700', color: INK },
  subtitle: { fontSize: Type.caption, color: Editorial.textCaption },
  divider: { height: 1, backgroundColor: ink(0.08) },

  content: { paddingHorizontal: 20, paddingTop: 18, paddingBottom: 24, gap: 14 },

  photo: {
    height: 300,
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: Editorial.surface,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  photoEmpty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 6 },
  photoEmptyIcon: { fontSize: 26, color: ink(0.35) },
  photoEmptyText: { fontSize: Type.footnote, color: Editorial.textCaption },

  hint: { fontSize: Type.caption, color: Editorial.textCaption, lineHeight: 19 },

  bottomDivider: { height: 1, backgroundColor: ink(0.08) },
  bottomBar: { paddingHorizontal: 20, paddingTop: 12 },
  primaryBtn: {
    height: 52,
    borderRadius: 14,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnOff: { opacity: 0.35 },
  primaryText: { fontSize: Type.label, fontWeight: '600', color: '#fff' },
});
