import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { Editorial, ink, Type } from '@/constants/theme';
import { useMemo, useState } from 'react';
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

const DEMO_JOIN_CODE = 'COZY2024';

function makeInviteLink(code: string) {
  return `https://cozy.app/join/${code}`;
}

function makeInviteCode() {
  return Math.random().toString(36).slice(2, 8).toUpperCase();
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

/** 멤버 아바타 + 초대 버튼 */
export function SharedSpaceMembers({
  space,
  onInvite,
}: {
  space: SharedSpace;
  onInvite: () => void;
}) {
  const initials = useMemo(
    () => space.members.map((m) => m.slice(0, 1)),
    [space.members],
  );

  return (
    <View style={styles.membersRow}>
      <View style={styles.memberAvatars}>
        {initials.map((ch, i) => (
          <View key={`${ch}-${i}`} style={[styles.memberDot, i > 0 && styles.memberDotOverlap]}>
            <Text style={styles.memberInitial}>{ch}</Text>
          </View>
        ))}
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
  onJoin: (code: string) => boolean;
}) {
  const [code, setCode] = useState('');
  const toast = useToast();

  const submit = () => {
    const trimmed = code.trim().toUpperCase();
    if (!trimmed) {
      toast('초대 코드를 입력해 주세요', { variant: 'error' });
      return;
    }
    const ok = onJoin(trimmed);
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
    color: ink(0.9),
    textAlign: 'center',
  },
  onboardingDesc: {
    fontSize: Type.footnote,
    color: ink(0.45),
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 21,
  },
  primaryBtn: {
    marginTop: 28,
    width: '100%',
    height: 48,
    borderRadius: 999,
    backgroundColor: Editorial.ink,
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
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryBtnText: { fontSize: Type.footnote, fontWeight: '600', color: ink(0.75) },
  demoHint: { fontSize: Type.micro, color: ink(0.3), marginTop: 16 },

  inviteBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 20,
    marginBottom: 16,
    padding: 14,
    borderRadius: 14,
    backgroundColor: Editorial.surfaceSoft,
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
  inviteBannerTitle: { fontSize: Type.footnote, fontWeight: '600', color: ink(0.85) },
  inviteBannerDesc: { fontSize: Type.micro, color: ink(0.45), marginTop: 2 },

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
  memberCount: { fontSize: Type.micro, color: ink(0.45), flex: 1 },
  inviteChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: Editorial.surface,
  },
  inviteChipText: { fontSize: Type.micro, fontWeight: '600', color: ink(0.75) },

  sheetBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(28,25,23,0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 36,
  },
  sheetTitle: { fontSize: Type.label, fontWeight: '600', color: ink(0.9) },
  sheetSubtitle: { fontSize: Type.footnote, color: ink(0.45), marginTop: 4, marginBottom: 20 },
  linkBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Editorial.surfaceSoft,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 8,
  },
  linkText: { flex: 1, fontSize: Type.micro, color: ink(0.6) },
  linkCopyBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Editorial.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  codeLabel: { fontSize: Type.micro, color: ink(0.4), marginTop: 16 },
  codeValue: {
    fontSize: 22,
    fontWeight: '700',
    letterSpacing: 4,
    color: ink(0.9),
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  snsBtnText: { fontSize: Type.footnote, fontWeight: '600', color: ink(0.75) },
  codeInput: {
    height: 48,
    borderRadius: 12,
    backgroundColor: Editorial.surfaceSoft,
    paddingHorizontal: 16,
    fontSize: Type.body,
    color: ink(0.9),
    letterSpacing: 2,
    marginBottom: 16,
  },
});
