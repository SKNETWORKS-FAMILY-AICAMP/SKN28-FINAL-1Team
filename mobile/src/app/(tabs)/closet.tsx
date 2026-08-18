import {
  SharedSpaceInviteSheet,
  SharedSpaceJoinSheet,
  SharedSpaceMembers,
  SharedSpaceOnboarding,
  type SharedSpace,
} from '@/components/closet/shared-space-flow';
import { SharedItemAddSheet } from '@/components/closet/shared-item-add-sheet';
import { PhotoSourceSheet } from '@/components/closet/photo-source-sheet';
import { CategoryItemManageSheet } from '@/components/closet/category-item-manage-sheet';
import { WardrobeViewControls } from '@/components/closet/wardrobe-view-controls';
import { CategoryEditSheet, EmptyState, ErrorState, LoadingState, LoginGate, SearchFilterBar, SegmentedToggle, SmartImage, useConfirm, useToast } from '@/components/ui';
import { useMultiSelectFilter } from '@/hooks/useMultiSelectFilter';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ContentMax, Editorial, GridCard, gridCardImageHeight, gridCardWidth, ink } from '@/constants/theme';
import { SHARED_CLOSET_ITEMS } from '@/constants/wardrobe';
import { WARDROBE_FILTER_OPTIONS } from '@/constants/wardrobe-taxonomy';
import { useBreakpoint } from '@/hooks/use-breakpoint';
import { useRefresh } from '@/hooks/use-refresh';
import {
  createWardrobeCategory,
  deleteWardrobeCategory,
  useWardrobeCategories,
  useWardrobeItems,
} from '@/hooks/use-wardrobe';
import { itemDisplayName, getMySharedRooms, createSharedRoom, joinSharedRoom, listSharedRoomMembers, listSharedRoomItems, listSharedRoomCategories, createSharedRoomCategory, deleteSharedRoomCategory, renameSharedRoom, deleteSharedRoom, unregisterItemFromSharedRoom, sharedUserDisplayName, updateWardrobeCategoryItems, type SharedRoomCategory } from '@/lib/wardrobeApi';
import {
  buildWardrobeSections,
  uniqueWardrobeItemCount,
  type WardrobeGroupMode,
  type WardrobeItemSort,
} from '@/lib/wardrobeSections';
import {
  DEFAULT_WARDROBE_VIEW_PREFERENCES,
  loadWardrobeViewPreferences,
  saveWardrobeViewPreferences,
} from '@/lib/wardrobeViewPreferences';
import { Icon } from '@/components/icon';
import { useAuth } from '@/state/auth';
import {
  isBatchRunning,
  type ImportBatchState,
  uploadJobs,
  useImportBatches,
  useUploadCompleted,
  useUploadJobs,
  useWardrobeRevision,
} from '@/state/upload-jobs';

const INK = Editorial.ink;

const MEMBER_COLORS = [
  '#FFD54F', // 노랑
  '#4FC3F7', // 하늘
  '#81C784', // 연두
  '#F06292', // 핑크
  '#BA68C8', // 보라
  '#FFB74D', // 주황
];
/**
 * 가져오기 배치 한 줄 문구 — 진행 중엔 어디까지 왔는지, 끝나면 결과만.
 * 실패 건수를 감추지 않는다. 몇 벌이 안 들어왔는지 알아야 다시 담을지 정할 수 있다.
 */
function batchMessage(b: ImportBatchState): string {
  if (b.error) return b.error;
  if (isBatchRunning(b)) return `가져온 옷 정리 중 · ${b.done + b.failed}/${b.total}장`;
  if (!b.done) return '가져온 옷을 옷장에 담지 못했어요';
  if (b.failed) return `${b.done}벌을 담았어요 · ${b.failed}장은 실패했어요`;
  return `${b.done}벌을 옷장에 담았어요`;
}

/* 카드 크기는 창 폭에서 파생되므로 모듈 최상단이 아니라 컴포넌트 안에서 useBreakpoint() 로 구한다.
   (모듈 최상단에서 읽으면 리사이즈에 반응하지 않는다) */
const PAD = GridCard.pad;

/* 카테고리는 백엔드 taxonomy(대분류 8종)를 따른다 — 프론트가 임의 목록을 쓰면 필터가 서버와 어긋난다. */
const DEFAULT_CATEGORIES = WARDROBE_FILTER_OPTIONS;

/** 그리드 카드가 쓰는 최소 형태 — 내 옷장(API)과 공유 옷장(목업)을 한 모양으로 맞춘다. */
type Card = {
  id: string;
  wardrobeItemId?: string;
  name: string;
  category: string;
  filterCategories: string[];
  image?: string;
  owner?: string;
};

/* 공유 옷장은 아직 백엔드가 없어 목업을 그대로 쓴다. */
const SHARED_ITEMS: Card[] = SHARED_CLOSET_ITEMS.map((i) => ({
  id: i.id,
  name: i.name,
  category: i.category,
  filterCategories: [i.category],
  image: i.image,
  owner: i.owner,
}));

function matchesQuery(item: Card, query: string): boolean {
  const q = query.trim();
  if (!q) return true;
  return item.name.includes(q) || item.category.includes(q);
}

export default function ClosetScreen() {
  const { isLoggedIn, user: me } = useAuth();
  const { frameWidth, contentStyle } = useBreakpoint();
  const cardW = gridCardWidth(frameWidth);
  const cardH = gridCardImageHeight(cardW);

  const toast = useToast();
  const confirm = useConfirm();
  const params = useLocalSearchParams<{ tab?: 'mine' | 'shared' }>();
  const [tab, setTab] = useState<'mine' | 'shared'>('mine');

  // URL 탭 파라미터 감지 및 자동 전환
  useEffect(() => {
    if (params.tab && (params.tab === 'mine' || params.tab === 'shared')) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTab(params.tab);
    }
  }, [params.tab]);

  const [query, setQuery] = useState('');
  const [sharedSpace, setSharedSpace] = useState<SharedSpace | null>(null);
  const [sharedRooms, setSharedRooms] = useState<any[]>([]);
  const [sharedItems, setSharedItems] = useState<Card[]>([]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [shareAddOpen, setShareAddOpen] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);
  const [manageRoom, setManageRoom] = useState<{ id: string; title: string; draftTitle: string } | null>(null);
  const [deleteRoom, setDeleteRoom] = useState<{ id: string; title: string } | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createDraftTitle, setCreateDraftTitle] = useState('공유 옷장');
  const [sharedCategories, setSharedCategories] = useState<SharedRoomCategory[]>([]);
  const [editOpen, setEditOpen] = useState(false);
  const [managedCategoryId, setManagedCategoryId] = useState<string | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const { selected, toggle, reset, prune, isActive, matches, label } = useMultiSelectFilter();
  const [groupMode, setGroupMode] = useState<WardrobeGroupMode>(
    DEFAULT_WARDROBE_VIEW_PREFERENCES.group_mode,
  );
  const [itemSort, setItemSort] = useState<WardrobeItemSort>(
    DEFAULT_WARDROBE_VIEW_PREFERENCES.item_sort,
  );
  const [viewPreferencesReady, setViewPreferencesReady] = useState(false);

  /* 내 옷장은 서버가 출처. 카테고리 필터는 여러 개를 고를 수 있어(멀티) 서버 파라미터로
     넘기지 않고 전체를 받아 프론트에서 걸러낸다 — 서버는 단일 category_large 만 받는다.

     확정 여부로 거르지 않는다. 예전엔 confirmed=true 만 받았는데, 그러면 백엔드에서
     직접 넣은 옷처럼 확인 단계를 거치지 않은 아이템이 옷장에 영영 안 보인다.
     대신 미확인 아이템에는 배지를 달아 구분한다. */
  const { items: apiItems, loading, error, reload: reloadItems } = useWardrobeItems({}, isLoggedIn);
  const {
    data: personalCategoryData,
    error: personalCategoryError,
    reload: reloadPersonalCategories,
  } = useWardrobeCategories(isLoggedIn);

  const mineCategories = useMemo(
    () =>
      personalCategoryData
        ? [
            '전체',
            ...personalCategoryData.system_categories.map((category) => category.name),
            ...personalCategoryData.custom_categories.map((category) => category.name),
          ]
        : DEFAULT_CATEGORIES,
    [personalCategoryData],
  );
  const sharedCategoryOptions = useMemo(
    () => [...DEFAULT_CATEGORIES, ...sharedCategories.map((category) => category.name)],
    [sharedCategories],
  );
  const categories = tab === 'mine' ? mineCategories : sharedCategoryOptions;
  const lockedCategories = tab === 'mine'
    ? personalCategoryData
      ? ['전체', ...personalCategoryData.system_categories.map((category) => category.name)]
      : DEFAULT_CATEGORIES
    : DEFAULT_CATEGORIES;
  const managedCategory = personalCategoryData?.custom_categories.find(
    (category) => category.id === managedCategoryId,
  ) ?? null;

  useEffect(() => {
    let active = true;
    void loadWardrobeViewPreferences().then((preferences) => {
      if (!active) return;
      setGroupMode(preferences.group_mode);
      setItemSort(preferences.item_sort);
      setViewPreferencesReady(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!viewPreferencesReady) return;
    void saveWardrobeViewPreferences({ group_mode: groupMode, item_sort: itemSort });
  }, [groupMode, itemSort, viewPreferencesReady]);

  const reloadAll = useCallback(
    () => Promise.all([reloadItems(), reloadPersonalCategories()]),
    [reloadItems, reloadPersonalCategories],
  );
  const { refreshing, onRefresh } = useRefresh(reloadAll);

  /* 탭 화면은 스택에 남아 있어 다른 화면에서 돌아와도 다시 마운트되지 않는다.
     첫 진입은 훅의 초기 조회가 담당하고, 이후 포커스 복귀 때 서버 카테고리로 재복원한다. */
  const categoryFocusedOnce = useRef(false);
  useFocusEffect(
    useCallback(() => {
      if (!categoryFocusedOnce.current) {
        categoryFocusedOnce.current = true;
        return;
      }
      if (isLoggedIn) void reloadPersonalCategories();
    }, [isLoggedIn, reloadPersonalCategories]),
  );

  /* 등록은 이 화면을 떠나도 계속 돈다(state/upload-jobs.ts). 진행 중인 것을 위에 보여주고,
     하나 끝날 때마다 목록을 다시 불러와 새 옷이 바로 보이게 한다. */
  const jobs = useUploadJobs();
  const completed = useUploadCompleted();
  const running = jobs.filter((j) => j.phase !== 'failed');
  const failed = jobs.filter((j) => j.phase === 'failed');

  const seenCompleted = useRef(completed);
  useEffect(() => {
    if (completed === seenCompleted.current) return;
    seenCompleted.current = completed;
    reloadItems();
    toast('옷장에 추가됐어요', { variant: 'success' });
  }, [completed, reloadItems, toast]);

  const handleUnshareItem = async (itemId: string) => {
    /* 옷 이름을 문구에 넣지 않는다 — 이름이 길거나 비어 있으면 문장이 깨진다.
       어느 옷을 눌렀는지는 방금 누른 카드로 이미 분명하다. */
    const ok = await confirm({
      title: '공유 해제',
      message: '이 아이템 공유를 해제할까요? (내 옷장에는 그대로 유지됩니다.)',
      confirmLabel: '공유 해제',
      destructive: true,
    });
    if (!ok) return;
    try {
      if (!sharedSpace) return;
      const target = sharedItems.find((x) => x.id === itemId);
      if (target && target.wardrobeItemId) {
        await unregisterItemFromSharedRoom(sharedSpace.id, target.wardrobeItemId);
        toast('공유를 해제했어요', { variant: 'success' });
        await loadRoomData(sharedSpace.id);
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : '공유를 해제하지 못했어요', { variant: 'error' });
    }
  };

  /* 가져오기(일괄 등록)는 옷이 여러 벌 들어온다 — 한 벌마다 토스트를 띄우면 시끄러우니
     목록만 조용히 갱신하고, 진행 상황은 아래 줄이 대신 말해준다. */
  const batches = useImportBatches();
  const revision = useWardrobeRevision();
  const seenRevision = useRef(revision);
  useEffect(() => {
    if (revision === seenRevision.current) return;
    seenRevision.current = revision;
    reloadItems();
  }, [revision, reloadItems]);

  const myItems = useMemo<Card[]>(
    () =>
      apiItems.map((i) => ({
        id: i.id,
        name: itemDisplayName(i),
        category: i.category_large,
        filterCategories: [
          i.category_large,
          ...i.custom_categories.map((category) => category.name),
        ],
        image: i.image_url,
      })),
    [apiItems],
  );

  const customCategoryOrder = useMemo(() => {
    if (personalCategoryData) return personalCategoryData.custom_categories;
    const byId = new Map(
      apiItems.flatMap((item) => item.custom_categories).map((category) => [category.id, category]),
    );
    return [...byId.values()].sort(
      (left, right) => left.position - right.position || left.id.localeCompare(right.id),
    );
  }, [apiItems, personalCategoryData]);
  const systemCategoryOrder = useMemo(
    () =>
      personalCategoryData
        ? personalCategoryData.system_categories.map((category) => category.name)
        : DEFAULT_CATEGORIES.slice(1),
    [personalCategoryData],
  );
  const mineSections = useMemo(
    () =>
      buildWardrobeSections(
        apiItems,
        {
          selectedCategories: selected,
          query,
          systemCategoryOrder,
          customCategoryOrder,
        },
        groupMode,
        itemSort,
      ),
    [
      apiItems,
      customCategoryOrder,
      groupMode,
      itemSort,
      query,
      selected,
      systemCategoryOrder,
    ],
  );
  const mineUniqueItemCount = useMemo(
    () => uniqueWardrobeItemCount(mineSections),
    [mineSections],
  );
  const myCardById = useMemo(
    () => new Map(myItems.map((item) => [item.id, item])),
    [myItems],
  );
  const mineFilteredItems = useMemo(() => {
    const seen = new Set<string>();
    return mineSections
      .flatMap((section) => section.items)
      .filter((item) => {
        if (seen.has(item.id)) return false;
        seen.add(item.id);
        return true;
      })
      .map((item) => myCardById.get(item.id))
      .filter((item): item is Card => !!item);
  }, [mineSections, myCardById]);

  const sharedFilteredItems = useMemo(
    () =>
      (sharedSpace ? sharedItems : []).filter(
        (i) => i.filterCategories.some((category) => matches(category)) && matchesQuery(i, query),
      ),
    [matches, query, sharedItems, sharedSpace],
  );
  const items = tab === 'mine' ? mineFilteredItems : sharedFilteredItems;

  useEffect(() => {
    prune(categories.slice(1));
  }, [categories, prune]);

  const loadRoomData = async (roomId: string, currentRoomsList?: any[]) => {
    try {
      const [membersList, itemsList, categoryList] = await Promise.all([
        listSharedRoomMembers(roomId),
        listSharedRoomItems(roomId),
        listSharedRoomCategories(roomId),
      ]);
      setSharedCategories(categoryList);
      /* '나' 판정은 내 user id 로 한다. 예전엔 username === 'dev_autologin' 문자열
         비교였는데, 실사용자 username 은 email_<uuid>/kakao_<id> 라 절대 매칭되지 않아
         공유 해제(X) 버튼이 프로덕션에서 아예 안 그려졌다. */
      const memberNames = membersList.map((m) =>
        m.user.id === me?.id ? '나' : sharedUserDisplayName(m.user)
      );
      const targetRoom = (currentRoomsList || sharedRooms).find((r) => r.id === roomId);
      setSharedSpace({
        id: roomId,
        name: targetRoom?.title || '공유 옷장',
        inviteCode: targetRoom?.invite_code || '',
        members: memberNames,
      });
      setSharedItems(
        itemsList.map((si) => ({
          id: si.id,
          wardrobeItemId: si.wardrobe_item.id,
          name: si.wardrobe_item.item_name || '옷',
          category: si.wardrobe_item.category_large,
          filterCategories: [si.wardrobe_item.category_large],
          image: si.wardrobe_item.image_url,
          owner:
            si.registered_by?.id === me?.id
              ? '나'
              : si.registered_by
                ? sharedUserDisplayName(si.registered_by)
                : undefined,
        }))
      );
    } catch (err) {
      console.error('공유방 세부 정보 로드 실패:', err);
    }
  };

  // 첫 마운트 또는 로그인 상태 변경 시 내 공유 옷장 방 로드
  useEffect(() => {
    if (isLoggedIn && tab === 'shared') {
      getMySharedRooms()
        .then(async (rooms) => {
          setSharedRooms(rooms || []);
          if (rooms && rooms.length > 0) {
            const selectedId =
              sharedSpace?.id && rooms.some((r) => r.id === sharedSpace.id)
                ? sharedSpace.id
                : rooms[0].id;
            await loadRoomData(selectedId, rooms);
          } else {
            setSharedSpace(null);
            setSharedItems([]);
          }
        })
        .catch(() => {
          setSharedRooms([]);
          setSharedSpace(null);
          setSharedItems([]);
          setSharedCategories([]);
        });
    }
  }, [isLoggedIn, tab]);

  /* 예전엔 웹에서 window.prompt 를 썼는데, 브라우저가 그리는 창이라 우리 다이얼로그와
     생김새가 전혀 달랐다(그리고 네이티브에선 아예 물어보지도 못해 이름이 고정이었다).
     이름 수정 모달과 같은 우리 모달로 통일한다. */
  const handleCreateSpace = () => {
    setCreateDraftTitle('공유 옷장');
    setCreateOpen(true);
  };

  const submitCreateSpace = async () => {
    const title = createDraftTitle.trim();
    if (!title) {
      toast('옷장 이름을 입력해 주세요.', { variant: 'error' });
      return;
    }
    if (title.length > 10) {
      toast('10글자 이내로 작성해주세요.', { variant: 'error' });
      return;
    }
    setCreateOpen(false);
    try {
      const room = await createSharedRoom(title);
      toast(`'${title}'을 만들었어요`, { variant: 'success' });
      const rooms = await getMySharedRooms();
      setSharedRooms(rooms || []);
      await loadRoomData(room.id, rooms);
      setInviteOpen(true);
    } catch (err) {
      console.error('공유 옷장 개설 실패:', err);
      toast(err instanceof Error ? err.message : '공유 옷장 개설에 실패했습니다', { variant: 'error' });
    }
  };

  const openRoomManager = (roomId: string, title: string) => {
    setManageRoom({ id: roomId, title, draftTitle: title });
  };

  const handleRenameSpace = async () => {
    if (!manageRoom) return;
    const newTitle = manageRoom.draftTitle.trim();
    if (!newTitle) {
      toast('옷장 이름을 입력해 주세요.', { variant: 'error' });
      return;
    }
    /* 입력 자체는 10글자 넘게 쳐지게 두고(maxLength 로 조용히 잘리면 왜 안 되는지 모른다)
       저장 시점에 팝업으로 알린다. 서버도 같은 기준으로 400 을 낸다. */
    if (newTitle.length > 10) {
      toast('10글자 이내로 작성해주세요.', { variant: 'error' });
      return;
    }
    if (newTitle === manageRoom.title) {
      setManageRoom(null);
      return;
    }

    try {
      await renameSharedRoom(manageRoom.id, newTitle);
      setManageRoom(null);
      const rooms = await getMySharedRooms();
      setSharedRooms(rooms);
      if (sharedSpace?.id === manageRoom.id) {
        setSharedSpace((prev) => (prev ? { ...prev, name: newTitle } : null));
      }
      toast('옷장 이름을 수정했어요', { variant: 'success' });
    } catch (err) {
      console.error('공유 옷장 이름 수정 실패:', err);
      toast('이름을 수정하지 못했습니다.', { variant: 'error' });
    }
  };

  const handleDeleteSpace = async (deletePersonalItems: boolean) => {
    if (!deleteRoom) return;
    const room = deleteRoom;

    try {
      await deleteSharedRoom(room.id, deletePersonalItems);
      setDeleteRoom(null);
      const rooms = await getMySharedRooms();
      setSharedRooms(rooms);

      if (rooms.length > 0) {
        await loadRoomData(rooms[0].id, rooms);
      } else {
        setSharedSpace(null);
          setSharedItems([]);
          setSharedCategories([]);
      }
      toast('공유 옷장을 삭제했어요', { variant: 'success' });
    } catch (err) {
      console.error('공유 옷장 삭제 실패:', err);
      toast(err instanceof Error ? err.message : '공유 옷장을 삭제하지 못했습니다.', { variant: 'error' });
    }
  };

  const handleJoinSpace = async (code: string) => {
    try {
      const res = await joinSharedRoom(code);
      /* 이미 멤버였는데 "참여했어요"라고 하면, 정원이 꽉 차 못 들어간 경우와
         구분이 안 돼 사용자가 방에 들어간 줄 안다. 서버가 준 status 로 갈라 말한다. */
      toast(
        res.status === 'already_member' ? '이미 참여 중인 공유 옷장이에요' : '공유 옷장에 참여했어요',
        { variant: 'success' },
      );
      const rooms = await getMySharedRooms();
      setSharedRooms(rooms || []);
      await loadRoomData(res.room_id, rooms);
      return true;
    } catch (err) {
      console.error('공유 옷장 참여 실패:', err);
      toast(err instanceof Error ? err.message : '유효하지 않거나 만료된 초대 코드입니다', { variant: 'error' });
      return false;
    }
  };

  const emptyTitle = useMemo(() => {
    if (query.trim()) return `'${query.trim()}' 검색 결과가 없어요`;
    if (label !== '전체') return `'${label}' 결과가 없어요`;
    return tab === 'shared' ? '공유 옷장이 비어있어요' : '옷장이 비어있어요';
  }, [query, label, tab]);

  const emptyDescription = useMemo(() => {
    if (query.trim() || label !== '전체') {
      return '다른 검색어나 카테고리를 선택해 보세요.';
    }
    return tab === 'shared'
      ? '내 옷을 공유하거나, 친구를 초대해 보세요.'
      : '첫 아이템을 추가해 옷장을 채워보세요.';
  }, [query, label, tab]);

  const handleTabChange = (key: 'mine' | 'shared') => {
    setTab(key);
    reset();
    setQuery('');
  };

  const handleSaveCategories = async (next: string[]) => {
    if (tab === 'mine') {
      const current = personalCategoryData ?? (await reloadPersonalCategories());
      if (!current) {
        toast(personalCategoryError ?? '카테고리를 불러온 뒤 다시 시도해 주세요', {
          variant: 'error',
        });
        return false;
      }

      const systemNames = new Set(current.system_categories.map((category) => category.name));
      const nextCustomNames = next.filter(
        (name) => name !== '전체' && !systemNames.has(name),
      );
      const nextNames = new Set(nextCustomNames);
      const existingNames = new Set(
        current.custom_categories.map((category) => category.name),
      );
      try {
        await Promise.all([
          ...nextCustomNames
            .filter((name) => !existingNames.has(name))
            .map((name) => createWardrobeCategory(name)),
          ...current.custom_categories
            .filter((category) => !nextNames.has(category.name))
            .map((category) => deleteWardrobeCategory(category.id)),
        ]);
        const saved = await reloadPersonalCategories();
        if (!saved) throw new Error('저장한 카테고리를 다시 불러오지 못했어요');
        prune([
          ...saved.system_categories.map((category) => category.name),
          ...saved.custom_categories.map((category) => category.name),
        ]);
        toast('카테고리를 저장했어요', { variant: 'success' });
        return true;
      } catch (saveError) {
        await reloadPersonalCategories();
        toast(
          saveError instanceof Error ? saveError.message : '카테고리를 저장하지 못했어요',
          { variant: 'error' },
        );
        return false;
      }
    }

    if (!sharedSpace) return false;

    const customNames = next.filter((name) => !DEFAULT_CATEGORIES.includes(name));
    const existingNames = new Set(sharedCategories.map((category) => category.name));
    const nextNames = new Set(customNames);
    try {
      await Promise.all([
        ...customNames
          .filter((name) => !existingNames.has(name))
          .map((name) => createSharedRoomCategory(sharedSpace.id, name)),
        ...sharedCategories
          .filter((category) => !nextNames.has(category.name))
          .map((category) => deleteSharedRoomCategory(sharedSpace.id, category.id)),
      ]);
      const saved = await listSharedRoomCategories(sharedSpace.id);
      setSharedCategories(saved);
      const savedCategories = [...DEFAULT_CATEGORIES, ...saved.map((category) => category.name)];
      prune(savedCategories.slice(1));
      toast('카테고리를 저장했어요', { variant: 'success' });
      return true;
    } catch (error) {
      toast(error instanceof Error ? error.message : '카테고리를 저장하지 못했어요', { variant: 'error' });
      const saved = await listSharedRoomCategories(sharedSpace.id).catch(() => sharedCategories);
      setSharedCategories(saved);
      return false;
    }
  };

  const openCategoryItemManager = (categoryName: string) => {
    const category = personalCategoryData?.custom_categories.find(
      (entry) => entry.name === categoryName,
    );
    if (!category) {
      toast('카테고리를 다시 불러온 뒤 시도해 주세요', { variant: 'error' });
      void reloadPersonalCategories();
      return;
    }
    setEditOpen(false);
    setManagedCategoryId(category.id);
  };

  const saveCategoryItems = async (
    categoryId: string,
    changes: { add_item_ids: string[]; remove_item_ids: string[] },
  ) => {
    try {
      const result = await updateWardrobeCategoryItems(categoryId, changes);
      await reloadAll();
      toast(`${result.item_count}벌을 카테고리에 저장했어요`, { variant: 'success' });
      return true;
    } catch (saveError) {
      toast(
        saveError instanceof Error ? saveError.message : '옷 구성을 저장하지 못했어요',
        { variant: 'error' },
      );
      await reloadAll();
      return false;
    }
  };

  const wardrobeToggle = (
    <SegmentedToggle
      value={tab}
      options={[
        { value: 'mine', label: '내 옷장' },
        { value: 'shared', label: '공유 옷장' },
      ]}
      onChange={handleTabChange}
    />
  );

  /* 두 탭 모두 `+`를 띄우되 하는 일이 다르다.
     내 옷장 = 새 옷 등록(사진), 공유 옷장 = 내 옷을 방에 연결.
     공유 옷장은 옷을 소유하지 않으므로(설계 §2.3) 여기서 사진을 받지 않는다. */
  const showAddFab = tab === 'mine' || (tab === 'shared' && !!sharedSpace);
  const onAddFabPress = () => (tab === 'mine' ? setSourceOpen(true) : setShareAddOpen(true));

  /* 이미 방에 올라간 옷은 선택 목록에서 빼야 해서 원본 아이템 id 로 넘긴다.
     참조가 매번 바뀌면 시트가 재조회를 반복하므로 메모한다. */
  const sharedWardrobeItemIds = useMemo(
    () => sharedItems.map((i) => i.wardrobeItemId).filter((id): id is string => !!id),
    [sharedItems],
  );

  const renderCard = (it: Card) => (
    <Pressable
      key={it.id}
      style={[styles.card, { width: cardW }]}
      onPress={() =>
        router.push({
          pathname: '/item-detail',
          params: {
            id: it.wardrobeItemId ?? it.id,
            ...(tab === 'shared' ? { readonly: '1' } : {}),
          },
        })
      }
      {...{
        draggable: true,
        onDragStart: (event: any) => {
          if (Platform.OS === 'web') {
            event.dataTransfer.setData(
              'text/plain',
              JSON.stringify({ id: it.id, name: it.name || it.category, image: it.image }),
            );
          }
        },
      }}>
      <View style={[styles.cardImage, { height: cardH }]}>
        <SmartImage
          uri={it.image}
          width="100%"
          height={cardH}
          radius={GridCard.radius}
          contentFit="cover"
        />
        {it.owner ? (
          <View
            style={[
              styles.ownerBadge,
              {
                backgroundColor: sharedSpace
                  ? MEMBER_COLORS[sharedSpace.members.indexOf(it.owner) % MEMBER_COLORS.length] ||
                    Editorial.ink
                  : Editorial.ink,
              },
            ]}>
            <Text
              style={[
                styles.ownerText,
                sharedSpace &&
                  sharedSpace.members.indexOf(it.owner) === 0 && { color: '#1C1917' },
              ]}>
              {it.owner}
            </Text>
          </View>
        ) : null}
        {tab === 'shared' && it.owner === '나' ? (
          <Pressable
            style={styles.unshareBtn}
            onPress={(event) => {
              event.stopPropagation();
              handleUnshareItem(it.id);
            }}
            hitSlop={8}>
            <Icon name="xmark" tintColor="#FFFFFF" size={10} />
          </Pressable>
        ) : null}
      </View>
      <View style={styles.cardMeta}>
        <Text style={styles.cardName} numberOfLines={1}>{it.name}</Text>
        <Text style={styles.cardCat}>{it.category}</Text>
      </View>
    </Pressable>
  );

  // 옷장은 내 데이터라 비회원에게 보여줄 것이 없다. (훅 순서 유지를 위해 전부 호출한 뒤 분기)
  if (!isLoggedIn) {
    return (
      <LoginGate
        title="옷장은 로그인하고 쓸 수 있어요"
        body="내 옷을 등록해 두면 가진 옷 안에서 추천을 만들어요."
      />
    );
  }

  return (
    <View style={styles.container}>
      <SafeAreaView edges={['top']} style={styles.safe}>
        <View style={styles.filterArea}>
          <SearchFilterBar
            trailing={wardrobeToggle}
            middle={
              tab === 'mine' ? (
                <WardrobeViewControls
                  groupMode={groupMode}
                  itemSort={itemSort}
                  onGroupModeChange={setGroupMode}
                  onItemSortChange={setItemSort}
                />
              ) : undefined
            }
            showFilters={!(tab === 'shared' && !sharedSpace)}
            query={query}
            onQueryChange={setQuery}
            searchPlaceholder="옷장에서 검색"
            options={categories}
            onToggle={toggle}
            isActive={isActive}
            onEditCategories={() => setEditOpen(true)}
          />
        </View>

        {/* 등록 진행 — 화면을 닫아도 계속 도는 작업의 상태 */}
        {tab === 'mine' && running.length > 0 ? (
          <View style={[styles.jobStrip, contentStyle(ContentMax.wide)]}>
            <ActivityIndicator color={INK} size="small" />
            <Text style={styles.jobText}>
              {`옷 등록 중 · ${running.length}장`}
            </Text>
          </View>
        ) : null}
        {/* 가져오기 배치 — 진행 중에는 남은 장수, 끝나면 결과 요약(사용자가 닫는다) */}
        {tab === 'mine'
          ? batches.map((b) => {
              const running = isBatchRunning(b);
              const bad = !running && (b.done === 0 || b.failed > 0 || Boolean(b.error));
              return (
                <View
                  key={b.batchId}
                  style={[
                    styles.jobStrip,
                    bad && styles.jobStripFail,
                    contentStyle(ContentMax.wide),
                  ]}>
                  {running ? (
                    <ActivityIndicator color={INK} size="small" />
                  ) : (
                    <Icon
                      name={bad ? 'exclamationmark.triangle' : 'checkmark'}
                      tintColor={bad ? Editorial.danger : INK}
                      size={15}
                    />
                  )}
                  <Text style={[styles.jobText, bad && styles.jobTextFail]} numberOfLines={2}>
                    {batchMessage(b)}
                  </Text>
                  {running ? null : (
                    <Pressable
                      hitSlop={10}
                      onPress={() => uploadJobs.dismissBatch(b.batchId)}
                      accessibilityLabel="닫기">
                      <Icon name="xmark" tintColor={ink(0.45)} size={14} />
                    </Pressable>
                  )}
                </View>
              );
            })
          : null}
        {tab === 'mine'
          ? failed.map((j) => (
              <View key={j.key} style={[styles.jobStrip, styles.jobStripFail, contentStyle(ContentMax.wide)]}>
                <Icon name="exclamationmark.triangle" tintColor={Editorial.danger} size={15} />
                <Text style={[styles.jobText, styles.jobTextFail]} numberOfLines={2}>
                  {j.error}
                </Text>
                <Pressable hitSlop={10} onPress={() => uploadJobs.dismiss(j.key)} accessibilityLabel="닫기">
                  <Icon name="xmark" tintColor={ink(0.45)} size={14} />
                </Pressable>
              </View>
            ))
          : null}

        {tab === 'shared' && sharedRooms.length > 0 ? (
          <View style={styles.roomTabsWrap}>
            {/* 추가 버튼은 맨 앞 — 방이 많아지면 끝의 버튼은 가로 스크롤에 묻혀
                '방을 더 만들 수 있다'는 사실 자체가 안 보인다. */}
            <Pressable
              style={[styles.roomTab, styles.roomTabAdd]}
              onPress={handleCreateSpace}
              accessibilityLabel="공유 옷장 추가"
            >
              <Icon name="plus" tintColor={ink(0.6)} size={12} />
              <Text style={[styles.roomTabText, { marginLeft: 4, color: ink(0.6) }]}>
                추가
              </Text>
            </Pressable>
            {sharedRooms.map((room) => {
              const isSelected = room.id === sharedSpace?.id;
              return (
                <Pressable
                  key={room.id}
                  style={[
                    styles.roomTab,
                    isSelected && styles.roomTabActive,
                    { flexDirection: 'row', alignItems: 'center' }
                  ]}
                  onPress={() => loadRoomData(room.id)}
                  onLongPress={() => openRoomManager(room.id, room.title)}
                >
                  <Text style={[styles.roomTabText, isSelected && styles.roomTabTextActive]}>
                    {room.title}
                  </Text>
                  {isSelected && (
                    <View style={styles.roomTabActions}>
                      <Pressable
                        hitSlop={8}
                        onPress={() => openRoomManager(room.id, room.title)}
                        accessibilityLabel="공유 옷장 이름 수정">
                        <Icon name="pencil" tintColor="#FFFFFF" size={12} />
                      </Pressable>
                    </View>
                  )}
                </Pressable>
              );
            })}
            {/* '코드로 참여'는 멤버 줄의 [초대] 옆 입력칸으로 옮겼다 —
                가로 스크롤 끝에 묻혀 있어 눈에 띄지 않았다. */}
          </View>
        ) : null}

        {tab === 'shared' && sharedSpace ? (
          /* '아직 혼자예요' 초대 유도 배너는 없앴다 — 바로 윗줄에 [+초대] 버튼과
             참여코드 입력칸이 이미 있어서, 같은 말을 세 번 하는 화면이 된다. */
          <SharedSpaceMembers
            space={sharedSpace}
            onInvite={() => setInviteOpen(true)}
            onJoin={handleJoinSpace}
          />
        ) : null}

        {tab === 'shared' && !sharedSpace ? (
          <View style={styles.onboardingWrap}>
            <SharedSpaceOnboarding
              onCreate={handleCreateSpace}
              onJoin={() => setJoinOpen(true)}
            />
          </View>
        ) : (
          <ScrollView
            style={styles.gridScroll}
            showsVerticalScrollIndicator={false}
            /* 공유 옷장은 아직 목업이라 다시 불러올 것이 없다 — 내 옷장에서만 당길 수 있게 둔다. */
            refreshControl={
              tab === 'mine' && isLoggedIn ? (
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={INK} />
              ) : undefined
            }
            contentContainerStyle={[
              styles.gridContent,
              { paddingBottom: 24 },
              contentStyle(ContentMax.wide),
            ]}>
            {/* 내 옷장만 서버에서 온다 — 공유 옷장은 아직 목업이라 로딩·에러가 없다. */}
            {tab === 'mine' && loading ? (
              <LoadingState message="옷장을 불러오는 중…" style={styles.empty} />
            ) : tab === 'mine' && error ? (
              <ErrorState
                title="옷장을 불러오지 못했어요"
                description={error}
                onRetry={reloadAll}
                style={styles.empty}
              />
            ) : items.length === 0 ? (
              <EmptyState
                icon={tab === 'shared' ? 'person' : 'tshirt'}
                title={emptyTitle}
                description={emptyDescription}
                actionLabel={
                  tab === 'mine' && !query.trim() && label === '전체'
                    ? '아이템 추가하기'
                    : tab === 'shared' && sharedSpace && !query.trim() && label === '전체'
                      ? /* 빈 공유방에서 할 일은 둘인데(옷 넣기·친구 부르기),
                           옷이 없으면 초대해도 볼 게 없으니 옷 넣기를 먼저 권한다.
                           친구 초대는 상단 멤버 줄의 [초대] 칩에 그대로 있다. */
                        '내 옷 공유하기'
                      : undefined
                }
                onAction={
                  tab === 'mine' && !query.trim() && label === '전체'
                    ? () => setSourceOpen(true)
                    : tab === 'shared' && sharedSpace && !query.trim() && label === '전체'
                      ? () => setShareAddOpen(true)
                      : undefined
                }
                style={styles.empty}
              />
            ) : tab === 'mine' ? (
              <View style={styles.sectionList}>
                <Text style={styles.resultSummary}>
                  {mineUniqueItemCount}벌 · {mineSections.length}개 섹션
                </Text>
                {mineSections.map((section) => (
                  <View key={section.id} style={styles.section}>
                    <View style={styles.sectionHeader}>
                      <Text style={styles.sectionTitle}>{section.title}</Text>
                      <Text style={styles.sectionCount}>{section.items.length}벌</Text>
                    </View>
                    <View style={styles.grid}>
                      {section.items.map((item) => {
                        const card = myCardById.get(item.id);
                        return card ? renderCard(card) : null;
                      })}
                    </View>
                  </View>
                ))}
              </View>
            ) : (
              <View style={styles.grid}>{items.map(renderCard)}</View>
            )}
          </ScrollView>
        )}

        {sharedSpace ? (
          <SharedSpaceInviteSheet
            space={sharedSpace}
            visible={inviteOpen}
            onClose={() => setInviteOpen(false)}
          />
        ) : null}
        <SharedSpaceJoinSheet
          visible={joinOpen}
          onClose={() => setJoinOpen(false)}
          onJoin={handleJoinSpace}
        />
        <PhotoSourceSheet visible={sourceOpen} onClose={() => setSourceOpen(false)} />

        {/* 공유 옷장 만들기 — 이름 수정 모달과 같은 껍데기를 쓴다 */}
        <Modal
          visible={createOpen}
          transparent
          animationType="fade"
          onRequestClose={() => setCreateOpen(false)}>
          <Pressable style={styles.dialogBackdrop} onPress={() => setCreateOpen(false)}>
            <Pressable style={styles.dialogCard} onPress={() => {}}>
              <Text style={styles.dialogTitle}>새 공유 옷장</Text>
              <Text style={styles.dialogMessage}>옷장 이름을 지어 주세요. (10글자 이내)</Text>
              <TextInput
                style={styles.dialogInput}
                value={createDraftTitle}
                onChangeText={setCreateDraftTitle}
                maxLength={20} // 10글자 초과는 저장 시 안내한다 — 타이핑을 막지 않는다
                autoFocus
                selectTextOnFocus
                returnKeyType="done"
                onSubmitEditing={submitCreateSpace}
                placeholder="공유 옷장"
                placeholderTextColor={ink(0.3)}
              />
              <View style={styles.dialogActions}>
                <Pressable
                  style={[styles.dialogButton, styles.dialogCancel]}
                  onPress={() => setCreateOpen(false)}>
                  <Text style={styles.dialogCancelText}>취소</Text>
                </Pressable>
                <Pressable
                  style={[styles.dialogButton, styles.dialogSave]}
                  onPress={submitCreateSpace}>
                  <Text style={styles.dialogConfirmText}>만들기</Text>
                </Pressable>
              </View>
            </Pressable>
          </Pressable>
        </Modal>

        <Modal
          visible={!!manageRoom}
          transparent
          animationType="fade"
          onRequestClose={() => setManageRoom(null)}>
          <Pressable style={styles.dialogBackdrop} onPress={() => setManageRoom(null)}>
            <Pressable style={styles.dialogCard} onPress={() => {}}>
              <Text style={styles.dialogTitle}>공유 옷장 관리</Text>
              <Text style={styles.dialogMessage}>옷장 이름을 수정하거나 삭제할 수 있어요.</Text>
              <TextInput
                style={styles.dialogInput}
                value={manageRoom?.draftTitle ?? ''}
                onChangeText={(draftTitle) =>
                  setManageRoom((room) => (room ? { ...room, draftTitle } : room))
                }
                maxLength={20} // 10글자 초과는 저장 시 팝업으로 거른다 — 타이핑을 막지 않는다
                autoFocus
                returnKeyType="done"
                onSubmitEditing={handleRenameSpace}
              />
              <View style={styles.dialogActions}>
                <Pressable style={[styles.dialogButton, styles.dialogCancel]} onPress={() => setManageRoom(null)}>
                  <Text style={styles.dialogCancelText}>취소</Text>
                </Pressable>
                <Pressable style={[styles.dialogButton, styles.dialogSave]} onPress={handleRenameSpace}>
                  <Text style={styles.dialogConfirmText}>이름 수정</Text>
                </Pressable>
              </View>
              <Pressable
                style={styles.dialogDelete}
                onPress={() => {
                  if (!manageRoom) return;
                  setDeleteRoom({ id: manageRoom.id, title: manageRoom.title });
                  setManageRoom(null);
                }}>
                <Text style={styles.dialogDeleteText}>이 옷장 삭제</Text>
              </Pressable>
            </Pressable>
          </Pressable>
        </Modal>

        <Modal
          visible={!!deleteRoom}
          transparent
          animationType="fade"
          onRequestClose={() => setDeleteRoom(null)}>
          <Pressable style={styles.dialogBackdrop} onPress={() => setDeleteRoom(null)}>
            <Pressable style={styles.dialogCard} onPress={() => {}}>
              <Text style={styles.dialogTitle}>공유 옷장을 삭제할까요?</Text>
              {/* 개인 옷장 원본은 공유 옷장 작업으로 절대 지워지지 않는다(서버 정책).
                  방을 지우면 방의 공유 목록·초대 링크만 사라지므로, 예전의
                  "공유한 내 옷도 삭제" 선택지는 없앴다 — 고를 수 있는 게 없다. */}
              <Text style={styles.dialogMessage}>
                공유 목록과 초대 링크가 삭제됩니다.{"\n"}내 옷장의 아이템은 그대로 유지됩니다.
              </Text>
              <Pressable style={styles.deleteItemsButton} onPress={() => handleDeleteSpace(false)}>
                <Text style={styles.dialogConfirmText}>삭제</Text>
              </Pressable>
              <Pressable style={styles.dialogCancelOnly} onPress={() => setDeleteRoom(null)}>
                <Text style={styles.dialogCancelText}>취소</Text>
              </Pressable>
            </Pressable>
          </Pressable>
        </Modal>

        <CategoryEditSheet
          visible={editOpen}
          title="카테고리 관리"
          categories={categories}
          lockedCategories={lockedCategories}
          lockedHint="기본 카테고리는 고정되고, 직접 만든 카테고리만 삭제할 수 있어요."
          onClose={() => setEditOpen(false)}
          onSave={handleSaveCategories}
          onManageCategory={tab === 'mine' ? openCategoryItemManager : undefined}
        />

        <CategoryItemManageSheet
          visible={!!managedCategory}
          category={managedCategory}
          items={apiItems}
          onClose={() => setManagedCategoryId(null)}
          onSave={saveCategoryItems}
        />

        {showAddFab ? (
          <Pressable
            style={[styles.addFab, { bottom: 12 }]}
            onPress={onAddFabPress}
            accessibilityLabel={tab === 'mine' ? '아이템 추가' : '내 옷 공유하기'}>
            <Icon name="plus" tintColor={INK} size={22} />
          </Pressable>
        ) : null}

        {sharedSpace ? (
          <SharedItemAddSheet
            visible={shareAddOpen}
            roomId={sharedSpace.id}
            roomName={sharedSpace.name}
            alreadySharedItemIds={sharedWardrobeItemIds}
            onClose={() => setShareAddOpen(false)}
            onDone={() => loadRoomData(sharedSpace.id)}
          />
        ) : null}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Editorial.page },
  safe: { flex: 1 },

  filterArea: { marginTop: 30 },

  jobStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginHorizontal: PAD,
    marginBottom: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: Editorial.control,
    borderWidth: 1,
    borderColor: Editorial.line,
  },
  jobStripFail: { backgroundColor: Editorial.surface },
  jobText: { flex: 1, fontSize: 13, color: Editorial.textCaption, fontWeight: '500' },
  jobTextFail: { color: Editorial.ink },

  gridScroll: { flex: 1, marginTop: 8 },
  onboardingWrap: { flex: 1, paddingHorizontal: PAD, paddingTop: 8 },
  gridContent: { flexGrow: 1 },
  sectionList: { width: '100%', gap: 28 },
  resultSummary: {
    paddingHorizontal: PAD,
    fontSize: 12,
    color: Editorial.textCaption,
  },
  section: { width: '100%' },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 7,
    paddingHorizontal: PAD,
    marginBottom: 12,
  },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: Editorial.ink },
  sectionCount: { fontSize: 12, fontWeight: '500', color: Editorial.textCaption },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    /* space-between 으로 두면 마지막 줄의 카드가 양 끝으로 밀려 가운데가 빈다.
       왼쪽부터 차례로 채우고 간격은 columnGap 으로 준다. */
    justifyContent: 'flex-start',
    columnGap: GridCard.gap,
    paddingHorizontal: PAD,
  },
  // width/height 는 창 폭에서 파생되므로 컴포넌트에서 인라인으로 덧붙인다.
  card: { marginBottom: 16 },
  cardImage: {
    width: '100%',
    borderRadius: GridCard.radius,
    overflow: 'hidden',
  },
  ownerBadge: {
    position: 'absolute',
    top: 10,
    left: 10,
    backgroundColor: INK,
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 999,
  },
  ownerText: { fontSize: 11, fontWeight: '600', color: '#fff' },
  unshareBtn: {
    position: 'absolute',
    top: 10,
    right: 10,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  cardMeta: {
    flexDirection: 'row',
    alignItems: 'baseline',
    /* 분류는 이름에 이어 붙인다. space-between 으로 두면 카드 오른쪽 끝으로 밀려
       이름과 멀어져 한 덩어리로 읽히지 않는다. */
    justifyContent: 'flex-start',
    gap: 6,
    marginTop: 8,
  },
  // flex:1 이면 이름이 남는 폭을 다 차지해 분류를 끝으로 밀어낸다 → 글자 길이만큼만.
  cardName: { flexShrink: 1, fontSize: 14, fontWeight: '500', color: Editorial.ink },
  cardCat: { fontSize: 12, color: Editorial.textCaption, flexShrink: 0 },

  empty: { width: '100%', paddingTop: 40 },

  addFab: {
    position: 'absolute',
    right: PAD,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Editorial.surface,
    borderWidth: 1.5,
    borderColor: ink(0.16),
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: INK,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.12,
    shadowRadius: 14,
    elevation: 8,
  },

  // ── 공유방 탭 스타일 (한눈에 나열) ──
  roomTabsWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    paddingHorizontal: PAD,
    gap: 8,
    marginTop: 0,
    marginBottom: 12,
  },
  roomTab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: '#F3F4F6',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  roomTabActive: {
    backgroundColor: INK,
    borderColor: INK,
  },
  roomTabAdd: {
    flexDirection: 'row',
    alignItems: 'center',
    borderStyle: 'dashed',
    borderColor: ink(0.3),
    backgroundColor: 'transparent',
  },
  roomTabText: {
    fontSize: 13,
    fontWeight: '600',
    color: ink(0.6),
  },
  roomTabTextActive: {
    color: '#FFFFFF',
  },
  roomTabActions: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 7,
  },
  dialogBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(28,25,23,0.42)',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  dialogCard: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: Editorial.surface,
    borderRadius: 20,
    paddingHorizontal: 24,
    paddingTop: 26,
    paddingBottom: 16,
  },
  dialogTitle: { fontSize: 19, fontWeight: '700', color: Editorial.ink, textAlign: 'center' },
  dialogMessage: {
    fontSize: 13,
    color: Editorial.textCaption,
    textAlign: 'center',
    marginTop: 10,
    lineHeight: 21,
  },
  dialogInput: {
    height: 48,
    marginTop: 20,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: Editorial.line,
    borderRadius: 12,
    color: Editorial.ink,
    fontSize: 15,
  },
  dialogActions: { flexDirection: 'row', gap: 10, marginTop: 16 },
  dialogButton: { flex: 1, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  dialogCancel: { backgroundColor: Editorial.surface, borderWidth: 1, borderColor: Editorial.line },
  dialogSave: { backgroundColor: Editorial.cta },
  dialogCancelText: { fontSize: 14, fontWeight: '600', color: Editorial.textCaption },
  dialogConfirmText: { fontSize: 14, fontWeight: '600', color: '#fff' },
  dialogDelete: { height: 44, marginTop: 12, alignItems: 'center', justifyContent: 'center' },
  dialogDeleteText: { fontSize: 14, fontWeight: '600', color: Editorial.danger },
  keepItemsButton: {
    height: 48,
    marginTop: 22,
    borderRadius: 14,
    backgroundColor: Editorial.cta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  keepItemsText: { fontSize: 14, fontWeight: '600', color: '#fff' },
  deleteItemsButton: {
    height: 48,
    marginTop: 10,
    borderRadius: 14,
    backgroundColor: Editorial.danger,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dialogCancelOnly: { height: 44, marginTop: 4, alignItems: 'center', justifyContent: 'center' },
});
