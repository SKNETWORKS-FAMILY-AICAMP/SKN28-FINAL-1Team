import { PROFILE_IMAGE } from '@/constants/look-images';
import type { AuthUser } from '@/state/auth';

/**
 * 표시용 이름과 사진을 한 곳에서 정한다.
 *
 * 예전에는 홈이 이름을 `'코지'` 로 박아 두고 아바타도 번들 목업을 넘겨서, 카카오·네이버·
 * 구글로 들어온 사람도 남의 이름과 사진을 봤다. 서버는 이미 provider 의 닉네임·사진을
 * 저장하고 **로그인할 때마다 갱신**하고 있었는데 화면이 그걸 안 쓰고 있었다.
 */

/** 소셜 가입 시 서버가 자동으로 만드는 username (kakao_123456 등) — 이름으로 쓰면 안 된다. */
const AUTO_USERNAME = /^(naver|kakao|google)_/;

/** 소셜 프로필이 없을 때 쓰는 기본값. 서비스 페르소나 이름이다. */
export const DEFAULT_NAME = '코지';

/**
 * 화면에 보일 이름.
 *
 * 소셜로 들어왔으면 provider 닉네임을, 아니면 기본값을 쓴다. 이메일 앞부분을 쓰지 않는
 * 이유는 팀 결정이다 — 이메일 계정에는 처음 세팅해 둔 이름·사진을 그대로 보여 주기로 했다.
 */
export function displayName(user: AuthUser | null | undefined): string {
  const nickname = user?.nickname?.trim();
  if (nickname && !AUTO_USERNAME.test(nickname)) return nickname;
  return DEFAULT_NAME;
}

/**
 * 아바타에 넘길 사진.
 *
 * 서버의 profile_image 는 '내가 올린 사진(presigned URL) → 없으면 소셜 사진' 순으로
 * 이미 정리돼 내려온다. 둘 다 없으면 번들 기본 사진으로 떨어진다.
 * ⚠️ presigned URL 은 만료되므로(기본 1시간) 오래 캐시하지 말 것.
 */
export function profilePhoto(user: AuthUser | null | undefined): {
  uri?: string;
  asset?: number;
} {
  const uri = user?.profile_image?.trim();
  return uri ? { uri } : { asset: PROFILE_IMAGE };
}
