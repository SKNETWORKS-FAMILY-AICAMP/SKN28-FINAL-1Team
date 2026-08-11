import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { Editorial, ink, Type } from '@/constants/theme';
import { useMemo, useState } from 'react';
import { KAKAO_NATIVE_APP_KEY } from '@/constants/config';
import {
  Modal,
  Platform,
  Pressable,
  Share,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

export type SharedSpace = {
  id: string;
  name: string;
  inviteCode: string;
  members: string[];
};

const DEMO_JOIN_CODE = 'COZY24';

function makeInviteLink(code: string) {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return `${window.location.origin}/invite?code=${code}`;
  }
  return `https://skn-1st-mobile.expo.app/invite?code=${code}`;
}

async function copyToClipboard(text: string): Promise<boolean> {
  if (Platform.OS === 'web' && typeof navigator !== 'undefined' && navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  return false;
}

/** 스페이스가 없을 때 — 만들기 / 초대 링크로 참여 */
export function SharedSpaceOnboarding({
  onCreate,
  onJoin,
}: {
  onCreate: () => void;
  onJoin: () => void;
}) {
  return (
    <View style={styles.onboarding}>
      <View style={styles.onboardingIcon}>
        <Icon name="person.2" tintColor={ink(0.32)} size={28} />
      </View>
      <Text style={styles.onboardingTitle}>함께 쓰는 옷장</Text>
      <Text style={styles.onboardingDesc}>
        카톡·SNS·링크로 친구를 초대하고{'\n'}같은 공간에서 옷장을 공유해 보세요.
      </Text>
      <Pressable style={styles.primaryBtn} onPress={onCreate}>
        <Text style={styles.primaryBtnText}>옷장 만들기</Text>
      </Pressable>
      <Pressable style={styles.secondaryBtn} onPress={onJoin}>
        <Text style={styles.secondaryBtnText}>초대 링크로 참여하기</Text>
      </Pressable>
      <Text style={styles.demoHint}>데모 참여 코드: {DEMO_JOIN_CODE}</Text>
    </View>
  );
}

/** 스페이스가 있지만 멤버가 본인뿐일 때 — 초대 유도 */
export function SharedSpaceInviteBanner({ onInvite }: { onInvite: () => void }) {
  return (
    <Pressable style={styles.inviteBanner} onPress={onInvite}>
      <View style={styles.inviteBannerIcon}>
        <Icon name="person.2" tintColor={Editorial.ink} size={18} />
      </View>
      <View style={styles.inviteBannerBody}>
        <Text style={styles.inviteBannerTitle}>아직 혼자예요</Text>
        <Text style={styles.inviteBannerDesc}>친구를 초대하면 옷장을 함께 볼 수 있어요</Text>
      </View>
      <Icon name="chevron.right" tintColor={ink(0.35)} size={16} />
    </Pressable>
  );
}

/** 가입 순서(index) 기반 고정 색. 초대장 화면도 같은 색을 써야 해서 여기서 내보낸다. */
export const MEMBER_COLORS = [
  '#FFD54F', // 노랑
  '#4FC3F7', // 하늘
  '#81C784', // 연두
  '#F06292', // 핑크
  '#BA68C8', // 보라
  '#FFB74D', // 주황
];

export function getAvatarColor(name: string): string {
  // 하위 호환용 (혹시 다른 곳에서 사용 시)
  return MEMBER_COLORS[0];
}

/** 멤버 아바타 + 초대 버튼 */
export function SharedSpaceMembers({
  space,
  onInvite,
}: {
  space: SharedSpace;
  onInvite: () => void;
}) {
  return (
    <View style={styles.membersRow}>
      <View style={styles.memberAvatars}>
        {space.members.map((member, i) => {
          const ch = member.slice(0, 1);
          const bgColor = MEMBER_COLORS[i % MEMBER_COLORS.length];
          return (
            <View
              key={`${member}-${i}`}
              style={[
                styles.memberDot,
                i > 0 && styles.memberDotOverlap,
                { backgroundColor: bgColor },
              ]}>
              <Text style={styles.memberInitial}>{ch}</Text>
            </View>
          );
        })}
      </View>
      <Text style={styles.memberCount}>{space.members.length}명</Text>
      <Pressable style={styles.inviteChip} onPress={onInvite} hitSlop={6}>
        <Icon name="plus" tintColor={Editorial.ink} size={14} />
        <Text style={styles.inviteChipText}>초대</Text>
      </Pressable>
    </View>
  );
}

/** 초대 링크 공유 시트 */
export function SharedSpaceInviteSheet({
  space,
  visible,
  onClose,
}: {
  space: SharedSpace;
  visible: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const link = makeInviteLink(space.inviteCode);

  const shareLink = async (via: 'kakao' | 'sns' | 'copy') => {
    if (via === 'kakao') {
      if (Platform.OS === 'web') {
        const loadKakao = () => {
          return new Promise<void>((resolve, reject) => {
            if (typeof window === 'undefined') return resolve();
            if ((window as any).Kakao) return resolve();
            const script = document.createElement('script');
            script.src = 'https://t1.kakaocdn.net/kakao_js_sdk_2.7.2/kakao.min.js';
            script.onload = () => {
              try {
                if (!(window as any).Kakao.isInitialized()) {
                  (window as any).Kakao.init(KAKAO_NATIVE_APP_KEY);
                }
                resolve();
              } catch (e) {
                reject(e);
              }
            };
            script.onerror = () => reject(new Error('Kakao SDK load failed'));
            document.head.appendChild(script);
          });
        };

        try {
          await loadKakao();
          (window as any).Kakao.Share.sendDefault({
            objectType: 'feed',
            content: {
              title: '공유 옷장 초대',
              description: `[cozy] '${space.name}' 공유 옷장에 초대합니다!`,
              imageUrl: 'https://images.unsplash.com/photo-1540221652346-e5dd6b50f3e7?w=500&auto=format&fit=crop&q=60',
              link: {
                mobileWebUrl: link,
                webUrl: link,
              },
            },
            buttons: [
              {
                title: '초대장 확인하고 수락하기',
                link: {
                  mobileWebUrl: link,
                  webUrl: link,
                },
              },
            ],
          });
          toast('카카오톡 공유창을 열었습니다.', { variant: 'success' });
          return;
        } catch (err) {
          console.error('카카오 웹 공유 실패:', err);
        }
      }

      // 네이티브 앱 또는 웹 공유 실패 시 일반 공유 폴백
      try {
        await Share.share({
          message: `[cozy] ${space.name}에 초대합니다!\n${link}`,
          title: `${space.name} 초대`,
        });
        toast('카카오톡으로 공유했어요', { variant: 'success' });
      } catch {
        /* 사용자가 취소 */
      }
      return;
    }

    if (via === 'copy') {
      const copied = await copyToClipboard(link);
      if (copied) {
        toast('링크를 복사했어요', { variant: 'success' });
        return;
      }
      try {
        await Share.share({ message: link });
      } catch {
        /* 사용자가 취소 */
      }
      return;
    }

    try {
      await Share.share({
        message: `[cozy] ${space.name}에 함께 옷장을 공유해요!\n${link}`,
        title: `${space.name} 초대`,
      });
    } catch {
      /* 사용자가 취소 */
    }
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.sheetBackdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.sheetTitle}>친구 초대하기</Text>
          <Text style={styles.sheetSubtitle}>{space.name}</Text>

          <View style={styles.linkBox}>
            <Text style={styles.linkText} numberOfLines={1}>
              {link}
            </Text>
            <Pressable style={styles.linkCopyBtn} onPress={() => shareLink('copy')} hitSlop={6}>
              <Icon name="link" tintColor={Editorial.ink} size={16} />
            </Pressable>
          </View>
          <Text style={styles.codeLabel}>참여 코드</Text>
          <Text style={styles.codeValue}>{space.inviteCode}</Text>

          <Pressable style={styles.kakaoBtn} onPress={() => shareLink('kakao')}>
            <Text style={styles.kakaoBtnText}>카카오톡으로 공유</Text>
          </Pressable>
          <Pressable style={styles.snsBtn} onPress={() => shareLink('sns')}>
            <Icon name="square.and.arrow.up" tintColor={Editorial.ink} size={18} />
            <Text style={styles.snsBtnText}>다른 앱으로 공유</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

/** 초대 코드 입력으로 참여 */
export function SharedSpaceJoinSheet({
  visible,
  onClose,
  onJoin,
}: {
  visible: boolean;
  onClose: () => void;
  onJoin: (code: string) => Promise<boolean> | boolean;
}) {
  const [code, setCode] = useState('');
  const toast = useToast();

  const submit = async () => {
    const trimmed = code.trim().toUpperCase();
    if (!trimmed) {
      toast('초대 코드를 입력해 주세요', { variant: 'error' });
      return;
    }
    const ok = await onJoin(trimmed);
    if (ok) {
      setCode('');
      onClose();
      toast('공유 옷장에 참여했어요', { variant: 'success' });
    } else {
      toast('유효하지 않은 초대 코드예요', { variant: 'error' });
    }
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.sheetBackdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.sheetTitle}>초대 링크로 참여</Text>
          <Text style={styles.sheetSubtitle}>친구가 보낸 링크의 코드를 입력하세요</Text>

          <TextInput
            style={styles.codeInput}
            placeholder="예: COZY2024"
            placeholderTextColor={ink(0.3)}
            value={code}
            onChangeText={setCode}
            autoCapitalize="characters"
            autoCorrect={false}
          />

          <Pressable style={styles.primaryBtn} onPress={submit}>
            <Text style={styles.primaryBtnText}>참여하기</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function makeInviteCode(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let code = '';
  for (let i = 0; i < 6; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

export function createSharedSpace(name = '우리 옷장'): SharedSpace {
  return {
    id: `space-${Date.now()}`,
    name,
    inviteCode: makeInviteCode(),
    members: ['나'],
  };
}

export function joinSharedSpace(code: string): SharedSpace | null {
  if (code !== DEMO_JOIN_CODE) return null;
  return {
    id: 'space-demo',
    name: '지민 · 서연 · 민준',
    inviteCode: DEMO_JOIN_CODE,
    members: ['나', '지민', '서연', '민준'],
  };
}

const styles = StyleSheet.create({
  onboarding: {
    width: '100%',
    alignItems: 'center',
    paddingTop: 32,
    paddingBottom: 24,
  },
  onboardingIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: Editorial.surfaceSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  onboardingTitle: {
    fontSize: Type.lead,
    fontWeight: '600',
    color: Editorial.ink,
    textAlign: 'center',
  },
  onboardingDesc: {
    fontSize: Type.footnote,
    color: Editorial.textCaption,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 21,
  },
  primaryBtn: {
    marginTop: 28,
    width: '100%',
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnText: { fontSize: Type.footnote, fontWeight: '600', color: '#fff' },
  secondaryBtn: {
    marginTop: 12,
    width: '100%',
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.surface,
    borderWidth: 1, borderColor: Editorial.line,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryBtnText: { fontSize: Type.footnote, fontWeight: '600', color: Editorial.textSoft },
  demoHint: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 16 },

  inviteBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 20,
    marginBottom: 16,
    padding: 14,
    borderRadius: 14,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1, borderColor: Editorial.line,
    gap: 12,
  },
  inviteBannerIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inviteBannerBody: { flex: 1 },
  inviteBannerTitle: { fontSize: Type.footnote, fontWeight: '600', color: Editorial.ink },
  inviteBannerDesc: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 2 },

  membersRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginBottom: 12,
    gap: 8,
  },
  memberAvatars: { flexDirection: 'row' },
  memberDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Editorial.ink,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#fff',
  },
  memberDotOverlap: { marginLeft: -8 },
  memberInitial: { fontSize: 11, fontWeight: '600', color: '#fff' },
  memberCount: { fontSize: Type.micro, color: Editorial.textCaption, flex: 1 },
  inviteChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: Editorial.surface,
  },
  inviteChipText: { fontSize: Type.micro, fontWeight: '600', color: Editorial.textSoft },

  sheetBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(28,25,23,0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: Editorial.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 36,
  },
  sheetTitle: { fontSize: Type.label, fontWeight: '600', color: Editorial.ink },
  sheetSubtitle: { fontSize: Type.footnote, color: Editorial.textCaption, marginTop: 4, marginBottom: 20 },
  linkBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1, borderColor: Editorial.line,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 8,
  },
  linkText: { flex: 1, fontSize: Type.micro, color: Editorial.textCaption },
  linkCopyBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  codeLabel: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 16 },
  codeValue: {
    fontSize: 22,
    fontWeight: '700',
    letterSpacing: 4,
    color: Editorial.ink,
    marginTop: 4,
  },
  kakaoBtn: {
    marginTop: 24,
    height: 48,
    borderRadius: 12,
    backgroundColor: Editorial.kakao,
    alignItems: 'center',
    justifyContent: 'center',
  },
  kakaoBtnText: { fontSize: Type.footnote, fontWeight: '600', color: '#3c1e1e' },
  snsBtn: {
    marginTop: 10,
    height: 48,
    borderRadius: 12,
    backgroundColor: Editorial.surface,
    borderWidth: 1, borderColor: Editorial.line,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  snsBtnText: { fontSize: Type.footnote, fontWeight: '600', color: Editorial.textSoft },
  codeInput: {
    height: 48,
    borderRadius: 12,
    backgroundColor: Editorial.surfaceSoft,
    borderWidth: 1, borderColor: Editorial.line,
    paddingHorizontal: 16,
    fontSize: Type.body,
    color: Editorial.ink,
    letterSpacing: 2,
    marginBottom: 16,
  },
});
