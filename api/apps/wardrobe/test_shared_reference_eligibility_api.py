from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.wardrobe.models import (
    SharedWardrobeItem,
    SharedWardrobeRoom,
    WardrobeItem,
)
from apps.wardrobe.services import shared_wardrobe as shared_service

User = get_user_model()


class SharedReferenceEligibilityApiTests(APITestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="reference-owner")
        self.room = shared_service.create_shared_room(self.owner, "참조 가능 테스트")
        self.client.force_authenticate(self.owner)
        self.url = f"/api/v1/shared-wardrobes/{self.room.pk}/items/"

    def _shared_item(
        self,
        *,
        name: str,
        status: str = SharedWardrobeItem.Status.AVAILABLE,
        confirmed: bool = True,
        embedding_version: str = "fashionsiglip-v1",
        s3_key: str = "wardrobe/reference.webp",
    ) -> SharedWardrobeItem:
        item = WardrobeItem.objects.create(
            user=self.owner,
            s3_key=s3_key,
            item_name=name,
            category_large="상의",
            confirmed=confirmed,
            added_to_closet_at=timezone.now(),
            embedding_version=embedding_version,
        )
        return SharedWardrobeItem.objects.create(
            room=self.room,
            registered_by=self.owner,
            wardrobe_item=item,
            status=status,
        )

    def test_shared_item_list_exposes_reference_eligibility_contract(self) -> None:
        available = self._shared_item(name="사용 가능")
        borrowed = self._shared_item(
            name="대여 중",
            status=SharedWardrobeItem.Status.BORROWED,
        )
        private = self._shared_item(
            name="나만 보기",
            status=SharedWardrobeItem.Status.PRIVATE,
        )
        unconfirmed = self._shared_item(name="미확정", confirmed=False)
        vector_not_ready = self._shared_item(
            name="벡터 준비 중",
            embedding_version="",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        by_id = {str(row["id"]): row for row in response.data}
        self.assertEqual(
            (
                by_id[str(available.pk)]["reference_eligible"],
                by_id[str(available.pk)]["reference_unavailable_reason"],
            ),
            (True, None),
        )
        self.assertEqual(
            (
                by_id[str(borrowed.pk)]["reference_eligible"],
                by_id[str(borrowed.pk)]["reference_unavailable_reason"],
            ),
            (True, None),
        )
        self.assertEqual(
            (
                by_id[str(private.pk)]["reference_eligible"],
                by_id[str(private.pk)]["reference_unavailable_reason"],
            ),
            (False, "PRIVATE"),
        )
        self.assertEqual(
            (
                by_id[str(unconfirmed.pk)]["reference_eligible"],
                by_id[str(unconfirmed.pk)]["reference_unavailable_reason"],
            ),
            (False, "NOT_CONFIRMED"),
        )
        self.assertEqual(
            (
                by_id[str(vector_not_ready.pk)]["reference_eligible"],
                by_id[str(vector_not_ready.pk)]["reference_unavailable_reason"],
            ),
            (False, "VECTOR_NOT_READY"),
        )
