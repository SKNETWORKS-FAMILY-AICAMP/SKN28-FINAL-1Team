from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from apps.wardrobe.models import (
    SharedWardrobeCategory,
    SharedWardrobeItem,
    SharedWardrobeMember,
    SharedWardrobeRoom,
    WardrobeItem,
)
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
            s3_key="wardrobe/hayoung/shirt.png",
            category_large="상의",
            category_small="티셔츠",
            item_name="hayoung_shirt",
            confirmed=True
        )
        self.unconfirmed_item = WardrobeItem.objects.create(
            user=self.user1,
            s3_key="wardrobe/hayoung/pending-shirt.png",
            category_large="상의",
            category_small="티셔츠",
            item_name="pending_shirt",
            confirmed=False,
        )
        self.client = APIClient()

    @override_settings(DEBUG=True)
    def test_create_room(self):
        """DEBUG 환경에서도 생성자만 방장으로 등록되는지 확인합니다."""
        room = shared_service.create_shared_room(self.user1, "하영이네 옷장")
        self.assertEqual(room.title, "하영이네 옷장")
        self.assertEqual(len(room.invite_code), 6)

        member = SharedWardrobeMember.objects.get(room=room, user=self.user1)
        self.assertEqual(member.role, SharedWardrobeMember.Role.OWNER)
        self.assertEqual(SharedWardrobeMember.objects.filter(room=room).count(), 1)

    def test_shared_room_full_api_lifecycle(self):
        """Swagger에 노출된 방 관리 API를 실제 요청 순서대로 전부 실행합니다."""
        self.client.force_authenticate(self.user1)
        created = self.client.post(
            "/api/v1/shared-wardrobes/",
            {"title": "API 검증방"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        room_id = created.data["id"]

        listed = self.client.get("/api/v1/shared-wardrobes/")
        detailed = self.client.get(f"/api/v1/shared-wardrobes/{room_id}/")
        renamed = self.client.patch(
            f"/api/v1/shared-wardrobes/{room_id}/",
            {"title": "수정된 검증방"},
            format="json",
        )
        refreshed = self.client.post(
            f"/api/v1/shared-wardrobes/{room_id}/refresh-code/"
        )
        self.assertEqual((listed.status_code, detailed.status_code), (200, 200))
        self.assertEqual((renamed.status_code, renamed.data["title"]), (200, "수정된 검증방"))
        self.assertEqual(refreshed.status_code, 200)
        invite_code = refreshed.data["invite_code"]

        preview = APIClient().get(
            f"/api/v1/shared-wardrobes/preview/?code={invite_code}"
        )
        self.assertEqual(preview.status_code, 200)

        member_client = APIClient()
        member_client.force_authenticate(self.user2)
        joined = member_client.post(
            "/api/v1/shared-wardrobes/join/",
            {"invite_code": invite_code},
            format="json",
        )
        self.assertEqual((joined.status_code, joined.data["status"]), (200, "joined"))

        members = self.client.get(
            f"/api/v1/shared-wardrobes/{room_id}/members/"
        )
        self.assertEqual((members.status_code, len(members.data)), (200, 2))

        left = member_client.post(
            f"/api/v1/shared-wardrobes/{room_id}/leave/",
            {"delete_my_items": False},
            format="json",
        )
        self.assertEqual(left.status_code, 204)
        self.assertFalse(
            SharedWardrobeMember.objects.filter(room_id=room_id, user=self.user2).exists()
        )

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

    def test_unconfirmed_item_cannot_be_registered(self):
        """사용자 확정 전 아이템은 공유 옷장에 등록할 수 없습니다."""
        room = shared_service.create_shared_room(self.user1, "공유 옷방")

        with self.assertRaisesMessage(ValueError, "사용자가 확정한 옷만"):
            shared_service.register_item_to_shared_room(
                self.user1,
                str(room.pk),
                str(self.unconfirmed_item.pk),
            )

        self.assertFalse(
            SharedWardrobeItem.objects.filter(
                room=room,
                wardrobe_item=self.unconfirmed_item,
            ).exists()
        )

    def test_member_cannot_delete_shared_room_via_api(self):
        """일반 멤버의 공유 옷장 DELETE는 403이고 방은 유지됩니다."""
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        self.client.force_authenticate(self.user2)

        response = self.client.delete(f"/api/v1/shared-wardrobes/{room.pk}/")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(SharedWardrobeRoom.objects.filter(pk=room.pk).exists())

    def test_owner_can_delete_shared_room_via_api(self):
        """방장의 공유 옷장 DELETE는 204이고 방을 삭제합니다."""
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        self.client.force_authenticate(self.user1)

        response = self.client.delete(f"/api/v1/shared-wardrobes/{room.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(SharedWardrobeRoom.objects.filter(pk=room.pk).exists())

    def test_member_can_create_list_and_delete_custom_category_via_api(self):
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        self.client.force_authenticate(self.user2)
        url = f"/api/v1/shared-wardrobes/{room.pk}/categories/"

        created = self.client.post(url, {"name": " 운동복 "}, format="json")
        self.assertEqual(created.status_code, 201)
        category = SharedWardrobeCategory.objects.get(pk=created.data["id"])
        self.assertEqual(category.name, "운동복")
        self.assertEqual(category.created_by, self.user2)

        listed = self.client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["name"] for row in listed.data], ["운동복"])

        deleted = self.client.delete(f"{url}?category_id={category.pk}")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(SharedWardrobeCategory.objects.filter(pk=category.pk).exists())

    def test_custom_category_rejects_default_and_duplicate_names(self):
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        self.client.force_authenticate(self.user1)
        url = f"/api/v1/shared-wardrobes/{room.pk}/categories/"

        default_name = self.client.post(url, {"name": "상의"}, format="json")
        first = self.client.post(url, {"name": "여행룩"}, format="json")
        duplicate = self.client.post(url, {"name": "여행룩"}, format="json")

        self.assertEqual(default_name.status_code, 400)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 400)

    def test_room_member_can_read_shared_item_detail_but_outsider_cannot(self):
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        shared_service.register_item_to_shared_room(
            self.user1, str(room.pk), str(self.item1.pk)
        )
        url = f"/api/v1/wardrobe/items/{self.item1.pk}/"

        self.client.force_authenticate(self.user2)
        member_response = self.client.get(url)
        self.assertEqual(member_response.status_code, 200)
        self.assertEqual(str(member_response.data["id"]), str(self.item1.pk))

        self.client.force_authenticate(self.user3)
        outsider_response = self.client.get(url)
        self.assertEqual(outsider_response.status_code, 404)

    def test_share_button_api_persists_item_and_exposes_it_to_room_members(self):
        """개인 옷 공유 요청이 DB에 저장되고 다른 방 멤버의 목록에도 노출됩니다."""
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        url = f"/api/v1/shared-wardrobes/{room.pk}/items/"

        self.client.force_authenticate(self.user1)
        created = self.client.post(
            url,
            {"wardrobe_item_id": str(self.item1.pk), "status": "available"},
            format="json",
        )

        self.assertEqual(created.status_code, 201)
        shared_item = SharedWardrobeItem.objects.get(
            room=room,
            wardrobe_item=self.item1,
        )
        self.assertEqual(shared_item.registered_by, self.user1)
        self.assertEqual(shared_item.status, SharedWardrobeItem.Status.AVAILABLE)

        self.client.force_authenticate(self.user2)
        listed = self.client.get(url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(
            str(listed.data[0]["wardrobe_item"]["id"]),
            str(self.item1.pk),
        )

        self.client.force_authenticate(self.user1)
        repeated = self.client.post(
            url,
            {"wardrobe_item_id": str(self.item1.pk), "status": "available"},
            format="json",
        )
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(
            SharedWardrobeItem.objects.filter(
                room=room, wardrobe_item=self.item1
            ).count(),
            1,
        )

    def test_unconfirmed_share_api_returns_actionable_error(self):
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        self.client.force_authenticate(self.user1)

        response = self.client.post(
            f"/api/v1/shared-wardrobes/{room.pk}/items/",
            {"wardrobe_item_id": str(self.unconfirmed_item.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("사용자가 확정한 옷만", response.data["detail"])
        self.assertFalse(
            SharedWardrobeItem.objects.filter(wardrobe_item=self.unconfirmed_item).exists()
        )

    def test_only_item_owner_or_room_owner_can_change_shared_item_status(self):
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        shared_service.join_shared_room(self.user3, room.invite_code)
        user2_item = WardrobeItem.objects.create(
            user=self.user2,
            s3_key="wardrobe/hyeji/jacket.png",
            item_name="hyeji_jacket",
            confirmed=True,
        )
        shared_item = shared_service.register_item_to_shared_room(
            self.user2, str(room.pk), str(user2_item.pk)
        )
        url = f"/api/v1/shared-wardrobes/{room.pk}/items/"

        self.client.force_authenticate(self.user3)
        denied = self.client.patch(
            url,
            {"item_id": str(shared_item.pk), "status": "borrowed"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.user1)
        changed = self.client.patch(
            url,
            {"item_id": str(shared_item.pk), "status": "borrowed"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        shared_item.refresh_from_db()
        self.assertEqual(shared_item.status, SharedWardrobeItem.Status.BORROWED)

    def test_private_item_is_visible_only_to_registrant(self):
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.join_shared_room(self.user2, room.invite_code)
        shared_service.register_item_to_shared_room(
            self.user1,
            str(room.pk),
            str(self.item1.pk),
            status=SharedWardrobeItem.Status.PRIVATE,
        )
        room_items_url = f"/api/v1/shared-wardrobes/{room.pk}/items/"
        detail_url = f"/api/v1/wardrobe/items/{self.item1.pk}/"

        self.client.force_authenticate(self.user1)
        owner_list = self.client.get(room_items_url)
        self.assertEqual(len(owner_list.data), 1)

        self.client.force_authenticate(self.user2)
        member_list = self.client.get(room_items_url)
        member_detail = self.client.get(detail_url)
        self.assertEqual(member_list.status_code, 200)
        self.assertEqual(member_list.data, [])
        self.assertEqual(member_detail.status_code, 404)

        self.client.force_authenticate(user=None)
        preview = self.client.get(
            "/api/v1/shared-wardrobes/preview/",
            {"code": room.invite_code},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data["items"], [])

    def test_unshare_deletes_link_but_preserves_personal_wardrobe_item(self):
        room = shared_service.create_shared_room(self.user1, "공유 옷방")
        shared_service.register_item_to_shared_room(
            self.user1, str(room.pk), str(self.item1.pk)
        )
        self.client.force_authenticate(self.user1)

        response = self.client.delete(
            f"/api/v1/shared-wardrobes/{room.pk}/items/",
            {"wardrobe_item_id": str(self.item1.pk)},
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            SharedWardrobeItem.objects.filter(room=room, wardrobe_item=self.item1).exists()
        )
        self.assertTrue(WardrobeItem.objects.filter(pk=self.item1.pk).exists())
