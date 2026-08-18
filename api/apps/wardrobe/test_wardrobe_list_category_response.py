import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.wardrobe.models import (
    WardrobeCategory,
    WardrobeItem,
    WardrobeItemCategory,
)
from apps.wardrobe.serializers import WardrobeItemSerializer

User = get_user_model()


@patch(
    "apps.wardrobe.serializers.storage.presigned_get",
    return_value="https://example.test/item.png",
)
class WardrobeListCategoryResponseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="wardrobe-list-category-owner",
            email="wardrobe-list-category-owner@test.com",
            password="password",
        )
        self.other_user = User.objects.create_user(
            username="wardrobe-list-category-other",
            email="wardrobe-list-category-other@test.com",
            password="password",
        )
        self.first_category = WardrobeCategory.objects.create(
            user=self.user,
            name="출근룩",
            position=0,
        )
        self.second_category = WardrobeCategory.objects.create(
            user=self.user,
            name="여행룩",
            position=1,
        )
        self.items = [self._create_item(index) for index in range(3)]
        for item in self.items:
            WardrobeItemCategory.objects.create(
                wardrobe_item=item,
                category=self.first_category,
            )
            WardrobeItemCategory.objects.create(
                wardrobe_item=item,
                category=self.second_category,
            )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _create_item(self, index):
        return WardrobeItem.objects.create(
            user=self.user,
            s3_key=f"wardrobe/{self.user.pk}/{uuid.uuid4()}.png",
            item_name=f"셔츠 {index}",
            category_large="상의",
            category_small="셔츠/블라우스",
            confirmed=True,
            added_to_closet_at=timezone.now(),
        )

    def test_list_returns_ordered_category_summaries_without_n_plus_one(
        self,
        _presigned_get,
    ):
        with self.assertNumQueries(2):
            response = self.client.get("/api/v1/wardrobe/items/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        for item in response.data:
            self.assertEqual(
                item["custom_categories"],
                [
                    {
                        "id": str(self.first_category.pk),
                        "name": "출근룩",
                        "position": 0,
                    },
                    {
                        "id": str(self.second_category.pk),
                        "name": "여행룩",
                        "position": 1,
                    },
                ],
            )

    def test_list_query_count_stays_constant_with_fifty_items(
        self,
        _presigned_get,
    ):
        extra_items = [self._create_item(index) for index in range(3, 50)]
        WardrobeItemCategory.objects.bulk_create(
            [
                WardrobeItemCategory(
                    wardrobe_item=item,
                    category=category,
                )
                for item in extra_items
                for category in (self.first_category, self.second_category)
            ]
        )

        with self.assertNumQueries(2):
            response = self.client.get("/api/v1/wardrobe/items/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 50)
        self.assertEqual(
            response.data[-1]["custom_categories"],
            [
                {
                    "id": str(self.first_category.pk),
                    "name": "출근룩",
                    "position": 0,
                },
                {
                    "id": str(self.second_category.pk),
                    "name": "여행룩",
                    "position": 1,
                },
            ],
        )

    def test_detail_uses_the_same_custom_category_contract(self, _presigned_get):
        response = self.client.get(
            f"/api/v1/wardrobe/items/{self.items[0].pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["custom_categories"],
            [
                {
                    "id": str(self.first_category.pk),
                    "name": "출근룩",
                    "position": 0,
                },
                {
                    "id": str(self.second_category.pk),
                    "name": "여행룩",
                    "position": 1,
                },
            ],
        )

    def test_other_users_item_does_not_expose_personal_categories(
        self,
        _presigned_get,
    ):
        other_category = WardrobeCategory.objects.create(
            user=self.other_user,
            name="비공개 정리",
        )
        other_item = WardrobeItem.objects.create(
            user=self.other_user,
            s3_key=f"wardrobe/{self.other_user.pk}/{uuid.uuid4()}.png",
            item_name="남의 셔츠",
            category_large="상의",
            confirmed=True,
            added_to_closet_at=timezone.now(),
        )
        WardrobeItemCategory.objects.create(
            wardrobe_item=other_item,
            category=other_category,
        )
        request = SimpleNamespace(user=self.user)

        data = WardrobeItemSerializer(
            other_item,
            context={"request": request},
        ).data

        self.assertEqual(data["custom_categories"], [])
