import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { Editorial, ink } from '@/constants/theme';
import { joinSharedRoom } from '@/lib/wardrobeApi';

export default function InviteScreen() {
  const params = useLocalSearchParams<{ code?: string }>();
  const router = useRouter();
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const inviteCode = params.code || '';

  const handleAcceptInvite = async () => {
    if (!inviteCode) {
      toast('초대 코드가 유효하지 않습니다.', { variant: 'error' });
      return;
    }

    setLoading(true);
    try {
      await joinSharedRoom(inviteCode);
      toast('공유 옷장 초대를 수락했습니다!', { variant: 'success' });
      // closet 탭의 shared 서브탭이 켜지도록 closet으로 리디렉션
      router.replace('/(tabs)/closet?tab=shared');
    } catch (err) {
      console.error('초대 수락 실패:', err);
      toast(err instanceof Error ? err.message : '초대 수락에 실패했습니다.', { variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <View style={styles.iconContainer}>
          <Icon name="person.2" tintColor={Editorial.ink} size={36} />
        </View>

        <Text style={styles.title}>공유 옷장 초대장</Text>
        <Text style={styles.desc}>
          친구로부터 옷장 공유 초대장을 받았습니다.{"\n"}
          수락하시면 함께 옷장을 관리하고 코디를 나눌 수 있습니다.
        </Text>

        <View style={styles.codeBox}>
          <Text style={styles.codeLabel}>참여 코드</Text>
          <Text style={styles.codeText}>{inviteCode || 'CODE_MISSING'}</Text>
        </View>

        <Pressable
          style={[styles.primaryBtn, loading && styles.disabledBtn]}
          onPress={handleAcceptInvite}
          disabled={loading}
        >
          <Text style={styles.primaryBtnText}>
            {loading ? '참여하는 중...' : '초대 수락하고 입장하기'}
          </Text>
        </Pressable>

        <Pressable style={styles.secondaryBtn} onPress={() => router.replace('/(tabs)/closet')}>
          <Text style={styles.secondaryBtnText}>취소하고 홈으로</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 32,
    width: '100%',
    maxWidth: 400,
    alignItems: 'center',
    // 그림자 효과 (Premium Card Feel)
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.05,
    shadowRadius: 16,
    elevation: 4,
  },
  iconContainer: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: Editorial.ink,
    marginBottom: 12,
    textAlign: 'center',
  },
  desc: {
    fontSize: 14,
    color: ink(0.56),
    lineHeight: 20,
    textAlign: 'center',
    marginBottom: 28,
  },
  codeBox: {
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#E5E7EB',
    borderRadius: 16,
    paddingVertical: 16,
    paddingHorizontal: 24,
    width: '100%',
    alignItems: 'center',
    marginBottom: 28,
  },
  codeLabel: {
    fontSize: 12,
    color: ink(0.4),
    marginBottom: 4,
    fontWeight: '500',
  },
  codeText: {
    fontSize: 24,
    fontWeight: '800',
    color: Editorial.ink,
    letterSpacing: 2,
  },
  primaryBtn: {
    backgroundColor: Editorial.ink,
    borderRadius: 16,
    height: 52,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  disabledBtn: {
    backgroundColor: ink(0.3),
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  secondaryBtn: {
    height: 48,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryBtnText: {
    color: ink(0.5),
    fontSize: 14,
    fontWeight: '500',
  },
});
