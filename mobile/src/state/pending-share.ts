/**
 * 공유 예약 — "이 옷은 확정되면 이 방에 공유한다".
 *
 * 왜 필요한가:
 * 사진을 올리며 '공유 옷장에 공유' 토글을 켜면 업로드 완료 직후 공유를 시도하는데,
 * 그 시점의 옷은 아직 `confirmed=false` 다 (자동 태깅 결과를 사용자가 확인하기 전).
 * 서버는 확정된 옷만 공유를 허용하므로(`shared_wardrobe.py` `register_item_to_shared_room`)
 * 이 등록은 **반드시 400 으로 실패한다.** 예전 코드는 그 실패를 console 로만 삼켜서,
 * 토글을 켠 사용자에게 아무 일도 일어나지 않았다.
 *
 * 그래서 실패를 예약으로 바꾼다. 사용자가 태그를 확인해 확정하는 순간
 * (`confirmWardrobeItem`) 예약을 꺼내 그때 공유한다.
 *
 * 저장은 secureStore — 확정이 다음 세션에 일어날 수도 있다.
 */
import { registerItemToSharedRoom } from '@/lib/wardrobeApi';
import { clearPendingShare, getPendingShare, savePendingShare } from '@/lib/secureStore';

/** itemId → roomId */
type Reservations = Record<string, string>;

let cache: Reservations | null = null;

async function read(): Promise<Reservations> {
  if (cache) return cache;
  try {
    const raw = await getPendingShare();
    const parsed = raw ? JSON.parse(raw) : {};
    cache = parsed && typeof parsed === 'object' ? (parsed as Reservations) : {};
  } catch {
    cache = {}; // 저장값이 깨졌으면 버린다 — 공유 예약은 잃어도 치명적이지 않다
  }
  return cache;
}

async function write(next: Reservations): Promise<void> {
  cache = next;
  if (Object.keys(next).length === 0) {
    await clearPendingShare();
    return;
  }
  await savePendingShare(JSON.stringify(next));
}

/** 확정되면 공유할 옷을 예약한다. */
export async function reserveShare(itemIds: string[], roomId: string): Promise<void> {
  if (!itemIds.length || !roomId) return;
  const current = await read();
  const next = { ...current };
  for (const id of itemIds) next[id] = roomId;
  await write(next);
}

export async function cancelShareReservation(itemId: string): Promise<void> {
  const current = await read();
  if (!(itemId in current)) return;
  const next = { ...current };
  delete next[itemId];
  await write(next);
}

/**
 * 예약된 옷이면 지금 공유한다. 확정 직후에 부른다.
 *
 * Returns: 공유에 성공한 방 id. 예약이 없거나 실패하면 null.
 * 실패해도 예약은 지운다 — 방에서 나갔거나 방이 사라진 경우 영원히 재시도하게 된다.
 */
export async function redeemShareReservation(itemId: string): Promise<string | null> {
  const current = await read();
  const roomId = current[itemId];
  if (!roomId) return null;

  await cancelShareReservation(itemId);

  try {
    await registerItemToSharedRoom(roomId, itemId);
    return roomId;
  } catch {
    return null;
  }
}
