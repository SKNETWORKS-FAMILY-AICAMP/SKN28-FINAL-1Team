from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.wardrobe.models import SharedWardrobeRoom, SharedWardrobeMember, SharedWardrobeItem, WardrobeItem
from apps.wardrobe.services import shared_wardrobe as shared_service

User = get_user_model()

class SharedWardrobeTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="hayoung", email="hayoung@test.com", password="password")
        self.user2 = User.objects.create_user(username="hyeji", email="hyeji@test.com", password="password")
        self.user3 = User.objects.create_user(username="lkw", email="lkw@test.com", password="password")
        
        # 개인 옷장 아이템 생성
        self.item1 = WardrobeItem.objects.create(
            user=self.user1,
            category_large="상의",
            category_small="티셔츠",
            item_name="hayoung_shirt",
            confirmed=True
        )

    @override_settings(DEBUG=True)
    def test_create_room(self):
        """DEBUG 환경에서도 생성자만 방장으로 등록되는지 확인합니다."""
        room = shared_service.create_shared_room(self.user1, "하영이네 옷장")
        self.assertEqual(room.title, "하영이네 옷장")
        self.assertEqual(len(room.invite_code), 6)

        member = SharedWardrobeMember.objects.get(room=room, user=self.user1)
        self.assertEqual(member.role, SharedWardrobeMember.Role.OWNER)
        self.assertEqual(SharedWardrobeMember.objects.filter(room=room).count(), 1)

    def test_invite_code_expiry(self):
        """초대코드가 24시간을 경과하면 만료 처리되어 가입할 수 없는지 확인합니다."""
        room = shared_service.create_shared_room(self.user1, "하영이네 옷장")
        
        # 만료 시각을 과거로 강제 조작
        room.code_expires_at = timezone.now() - timedelta(seconds=1)
        room.save()
        
        # user2 가 가입 시도할 때 ValueError 발생해야 함
        with self.assertRaises(ValueError) as ctx:
            shared_service.join_shared_room(self.user2, room.invite_code)
        self.assertIn("초대코드가 24시간 만료 시간을 초과", str(ctx.exception))

    def test_refresh_invite_code(self):
        """방장만 초대코드를 24시간짜리 새 코드로 재발급할 수 있는지 확인합니다."""
        room = shared_service.create_shared_room(self.user1, "하영이네 옷장")
        old_code = room.invite_code
        
        # 방장이 아닌 user2 가 재발급 시도 시 PermissionError 발생
        with self.assertRaises(PermissionError):
            shared_service.refresh_invite_code(self.user2, str(room.pk))
            
        # 방장인 user1 이 재발급
        updated_room = shared_service.refresh_invite_code(self.user1, str(room.pk))
        self.assertNotEqual(updated_room.invite_code, old_code)
        self.assertGreater(updated_room.code_expires_at, timezone.now() + timedelta(hours=23))

    def test_leave_room_owner_delegation(self):
        """방장이 나갈 때 가입일시 순서대로 방장 권한이 위임되는지 확인합니다."""
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        
        # user2 가입
        shared_service.join_shared_room(self.user2, room.invite_code)
        # user3 가입
        shared_service.join_shared_room(self.user3, room.invite_code)
        
        # 방장인 user1 이 퇴장
        shared_service.leave_shared_room(self.user1, str(room.pk))
        
        # user2 가 새로운 방장(owner)으로 자동 승격되었는지 확인
        user2_member = SharedWardrobeMember.objects.get(room=room, user=self.user2)
        self.assertEqual(user2_member.role, SharedWardrobeMember.Role.OWNER)

    def test_leave_room_item_option(self):
        """탈퇴 시 아이템 삭제 옵션(A/B)이 올바르게 분기 처리되는지 확인합니다."""
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        
        # user1 이 방에 옷 등록
        shared_item = shared_service.register_item_to_shared_room(self.user1, str(room.pk), str(self.item1.pk))
        self.assertEqual(SharedWardrobeItem.objects.filter(room=room).count(), 1)
        
        # 옵션 B: 아이템 유지하고 탈퇴 (delete_my_items = False)
        shared_service.leave_shared_room(self.user1, str(room.pk), delete_my_items=False)
        
        # 옷은 남아있고 등록자는 None 처리되어야 함
        shared_item.refresh_from_db()
        self.assertIsNone(shared_item.registered_by)
        
        # user2 도 방에서 나가며 옵션 A: 아이템 삭제 탈퇴 (delete_my_items = True)
        shared_service.leave_shared_room(self.user2, str(room.pk), delete_my_items=True)
        # 방에 남은 인원이 없으므로 방 자체가 삭제되어야 함
        self.assertFalse(SharedWardrobeRoom.objects.filter(pk=room.pk).exists())
