import { Icon } from '@/components/icon';
import { useToast } from '@/components/ui';
import { Editorial, ink, Type } from '@/constants/theme';
import { useMemo, useState } from 'react';
import { copyText, inviteMessage, openShareSheet, shareInviteViaKakao } from '@/lib/kakaoShare';
import { Modal, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

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

  const invite = { roomName: space.name, code: space.inviteCode, link };

  const shareLink = async (via: 'kakao' | 'sns') => {
    if (via === 'kakao') {
      // 모바일은 카카오톡을 열고, PC 웹은 초대 문구만 복사한다.
      const result = await shareInviteViaKakao(invite);
      if (result === 'kakao') {
        toast('카카오톡 공유창을 열었어요', { variant: 'success' });
      } else if (result === 'share-sheet') {
        toast('공유 앱을 골라 주세요 — 초대 문구는 복사해 뒀어요', { variant: 'success' });
      } else if (result === 'clipboard') {
        toast('초대 문구를 복사했어요. 카카오톡 대화방에 붙여넣어 주세요', {
          variant: 'success',
        });
      } else if (result === 'no-key') {
        // 설정 누락은 사용자가 아무리 다시 눌러도 안 된다 — 원인을 그대로 말한다.
        toast('카카오 공유 설정이 없어요 (EXPO_PUBLIC_KAKAO_JAVASCRIPT_KEY)', {
          variant: 'error',
        });
      } else {
        toast('공유하지 못했어요. 아래 참여 코드를 눌러 복사해 주세요', { variant: 'error' });
      }
      return;
    }

    /* 다른 앱으로 공유해도 참여 코드가 빠지지 않도록 카카오와 같은 문구를 쓴다.
       공유 시트를 못 여는 환경(웹 Share API 미지원·비보안 컨텍스트)에서는
       아무 일도 안 일어난 것처럼 보이므로 복사로 대신하고 그렇다고 말해 준다. */
    const message = inviteMessage(invite);
    if (await openShareSheet(message, `${space.name} 초대`)) return;

    if (await copyText(message)) {
      toast('공유 앱을 열 수 없어 초대 문구를 복사했어요', { variant: 'success' });
    } else {
      toast('공유하지 못했어요. 아래 참여 코드를 눌러 복사해 주세요', { variant: 'error' });
    }
  };

  const copyCode = async () => {
    if (await copyText(space.inviteCode)) {
      toast('참여 코드를 복사했어요', { variant: 'success' });
    }
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.sheetBackdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.sheetHeader}>
            <View style={styles.sheetHeaderText}>
              <Text style={styles.sheetTitle}>친구 초대하기</Text>
              <Text style={styles.sheetSubtitle}>{space.name}</Text>
            </View>
            {/* 배경을 눌러도 닫히지만, 모달 안에서 닫을 곳이 없으면 갇힌 느낌이 든다 */}
            <Pressable onPress={onClose} hitSlop={12} accessibilityLabel="닫기">
              <Icon name="xmark" tintColor={ink(0.5)} size={18} />
            </Pressable>
          </View>

          {/* URL 은 노출하지 않는다 — 참여는 6자리 코드로만 받기로 했다.
              링크 자체는 카카오 카드 버튼용으로 내부에서만 쓴다. */}
          <Text style={styles.codeLabel}>참여 코드</Text>
          <View style={styles.codeRow}>
            <Text style={styles.codeValue}>{space.inviteCode}</Text>
            <Pressable style={styles.codeCopyBtn} onPress={copyCode} hitSlop={8}>
              <Icon name="link" tintColor={Editorial.ink} size={14} />
              <Text style={styles.codeCopyText}>코드복사</Text>
            </Pressable>
          </View>
          <Text style={styles.codeHint}>친구가 이 코드를 입력하면 바로 들어와요</Text>

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
      return;
    }
    /* 실패 사유는 onJoin 이 이미 서버 문구로 띄웠다(정원 초과·만료·없는 코드).
       여기서 '유효하지 않은 초대 코드'를 덧씌우면 정원이 꽉 찬 경우까지
       코드가 틀린 것처럼 보여서 사용자가 엉뚱한 곳을 고치게 된다.
       시트도 닫지 않는다 — 코드를 고쳐 다시 넣을 수 있어야 한다. */
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
  sheetHeader: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 20 },
  sheetHeaderText: { flex: 1 },
  sheetTitle: { fontSize: Type.label, fontWeight: '600', color: Editorial.ink },
  sheetSubtitle: { fontSize: Type.footnote, color: Editorial.textCaption, marginTop: 4 },
  /* 참여는 6자리 코드로만 받는다 — 코드가 이 시트의 주인공이라 크게 키웠다.
     (URL 을 보여주던 linkBox 계열 스타일은 링크 노출을 걷어내면서 함께 삭제) */
  codeLabel: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 4 },
  /* 코드와 복사 버튼을 한 줄에 둔다 — 코드 오른쪽이 비어 있었다 */
  codeRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 6 },
  codeValue: {
    flex: 1,
    fontSize: 30,
    fontWeight: '700',
    letterSpacing: 6,
    color: Editorial.ink,
  },
  codeCopyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    height: 36,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: Editorial.line,
    backgroundColor: Editorial.surfaceSoft,
  },
  codeCopyText: { fontSize: Type.micro, fontWeight: '600', color: Editorial.ink },
  codeHint: { fontSize: Type.micro, color: Editorial.textCaption, marginTop: 8 },
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
