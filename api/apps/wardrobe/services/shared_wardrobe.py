import random
import string
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.wardrobe.models import SharedWardrobeRoom, SharedWardrobeMember, SharedWardrobeItem, WardrobeItem

User = get_user_model()

def generate_unique_invite_code() -> str:
    """영문 대문자와 숫자가 혼합된 고유한 6자리 핀코드를 생성합니다."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(50):
        code = "".join(random.choices(chars, k=6))
        if not SharedWardrobeRoom.objects.filter(invite_code=code).exists():
            return code
    return "".join(random.choices(chars, k=6))


@transaction.atomic
def create_shared_room(user, title: str) -> SharedWardrobeRoom:
    """새로운 공유 옷장 방을 개설하고 생성자를 방장(owner)으로 자동 배정합니다."""
    code = generate_unique_invite_code()
    expires_at = timezone.now() + timedelta(hours=24)
    
    room = SharedWardrobeRoom.objects.create(
        title=title,
        invite_code=code,
        code_expires_at=expires_at
    )
    
    SharedWardrobeMember.objects.create(
        room=room,
        user=user,
        role=SharedWardrobeMember.Role.OWNER
    )
    
    # 데모용 가상 멤버 추가 (DEBUG=True일 때 파스텔 아바타 색상 테스트용)
    from django.conf import settings
    if settings.DEBUG:
        for mock_name in ["철수", "영희", "민수"]:
            mock_user, _ = User.objects.get_or_create(
                username=mock_name,
                defaults={"nickname": mock_name}
            )
            SharedWardrobeMember.objects.create(
                room=room,
                user=mock_user,
                role=SharedWardrobeMember.Role.MEMBER
            )
    
    return room


@transaction.atomic
def refresh_invite_code(user, room_id: str) -> SharedWardrobeRoom:
    """방의 기존 초대코드를 만료시키고, 24시간 동안 유효한 새 초대코드를 발급합니다.
    방장(owner)만 이 코드를 재발급할 수 있습니다.
    """
    room = SharedWardrobeRoom.objects.select_for_update().get(pk=room_id)
    
    # 방장 권한 체크
    member = SharedWardrobeMember.objects.filter(room=room, user=user).first()
    if not member or member.role != SharedWardrobeMember.Role.OWNER:
        raise PermissionError("초대코드 재발급 권한이 없습니다. 방장만 재발급할 수 있습니다.")
        
    code = generate_unique_invite_code()
    expires_at = timezone.now() + timedelta(hours=24)
    
    room.invite_code = code
    room.code_expires_at = expires_at
    room.save(update_fields=["invite_code", "code_expires_at"])
    return room


@transaction.atomic
def join_shared_room(user, invite_code: str) -> SharedWardrobeRoom:
    """6자리 초대코드를 입력하여 공유 옷장 방에 신규 참여(가입)합니다.
    초대코드의 24시간 만료 시간 체크가 적용됩니다.
    """
    code = invite_code.strip().upper()
    room = SharedWardrobeRoom.objects.filter(invite_code=code).first()
    
    if not room:
        raise ValueError("유효하지 않은 초대코드입니다.")
        
    # 만료 여부 체크
    if room.code_expires_at and room.code_expires_at < timezone.now():
        raise ValueError("초대코드가 24시간 만료 시간을 초과하여 사용할 수 없습니다. 방장에게 재발급을 요청하세요.")
        
    # 이미 참여 중인지 체크
    if SharedWardrobeMember.objects.filter(room=room, user=user).exists():
        return room
        
    # 인원 제한 체크 (최대 6명)
    if room.members.count() >= 6:
        raise ValueError("공유 옷장 정원(최대 6명)이 초과되어 가입할 수 없습니다.")
        
    # 멤버십 참여 등록
    SharedWardrobeMember.objects.create(
        room=room,
        user=user,
        role=SharedWardrobeMember.Role.MEMBER
    )
    return room


@transaction.atomic
def leave_shared_room(user, room_id: str, delete_my_items: bool = True) -> None:
    """공유 옷장 방을 자발적으로 탈퇴(퇴장)합니다.
    
    - 방장이 나갈 시:
      - 남은 멤버 중 가입일시가 가장 빠른 다른 유저에게 방장(owner) 권한을 자동으로 위임합니다.
      - 방 안에 더이상 남은 유저가 0명이면 방을 폐쇄(Delete) 처리합니다.
    - 아이템 처리:
      - delete_my_items 가 True이면 사용자가 해당 공유 옷장에 기여한 옷들을 일괄 삭제합니다.
      - False이면 옷은 기부되어 공유 옷장에 유지됩니다 (등록 유저는 NULL 처리).
    """
    try:
        room = SharedWardrobeRoom.objects.get(pk=room_id)
        membership = SharedWardrobeMember.objects.get(room=room, user=user)
    except (SharedWardrobeRoom.DoesNotExist, SharedWardrobeMember.DoesNotExist):
        raise ValueError("참여하고 있지 않은 공유 옷장 방입니다.")

    # 1. 탈퇴자 등록 옷 처리 분기
    if delete_my_items:
        # 내가 등록한 옷 완전 삭제
        SharedWardrobeItem.objects.filter(room=room, registered_by=user).delete()
    else:
        # 옷은 그대로 두고 등록자 연관관계만 NULL 처리하여 기부 유지
        SharedWardrobeItem.objects.filter(room=room, registered_by=user).update(registered_by=None)

    # 2. 멤버십 탈퇴
    is_owner = (membership.role == SharedWardrobeMember.Role.OWNER)
    membership.delete()

    # 3. 방장 퇴장 처리 및 방 유지/위임/폭파 연산
    remaining_members = SharedWardrobeMember.objects.filter(room=room).order_by("joined_at")
    remaining_count = remaining_members.count()

    if remaining_count == 0:
        # 남은 인원이 없으면 방 완전 폭파
        room.delete()
    else:
        # 방장이 나갔고 남은 인원이 있으면 가입 순서가 가장 빠른 사람에게 위임
        if is_owner:
            next_owner = remaining_members.first()
            if next_owner:
                next_owner.role = SharedWardrobeMember.Role.OWNER
                next_owner.save(update_fields=["role"])


@transaction.atomic
def register_item_to_shared_room(user, room_id: str, wardrobe_item_id: str, status: str = "available") -> SharedWardrobeItem:
    """개인 옷장에서 보유하고 있는 내 옷(confirmed=True인 옷만 가능)을 공유 옷장에 정식으로 등록(공유)합니다."""
    try:
        room = SharedWardrobeRoom.objects.get(pk=room_id)
        # 방 참여자인지 확인
        SharedWardrobeMember.objects.get(room=room, user=user)
    except (SharedWardrobeRoom.DoesNotExist, SharedWardrobeMember.DoesNotExist):
        raise ValueError("공유 옷장 참여 멤버만 옷을 공유할 수 있습니다.")

    try:
        wardrobe_item = WardrobeItem.objects.get(pk=wardrobe_item_id, user=user)
    except WardrobeItem.DoesNotExist:
        raise ValueError("내 개인 옷장에 소유 중인 옷만 공유 옷장에 공유할 수 있습니다.")

    # 이미 이 방에 등록했는지 확인
    shared_item = SharedWardrobeItem.objects.filter(room=room, wardrobe_item=wardrobe_item).first()
    if shared_item:
        return shared_item

    return SharedWardrobeItem.objects.create(
        room=room,
        registered_by=user,
        wardrobe_item=wardrobe_item,
        status=status
    )
