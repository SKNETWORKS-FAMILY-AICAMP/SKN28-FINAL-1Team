import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.wardrobe.models import (
    WardrobeCategory,
    WardrobeItem,
    WardrobeItemCategory,
)

User = get_user_model()


class PersonalWardrobeCategoryAssignmentApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="category-assignment-owner",
            email="category-assignment-owner@test.com",
            password="password",
        )
        self.other_user = User.objects.create_user(
            username="other-category-assignment-owner",
            email="other-category-assignment-owner@test.com",
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
        self.other_category = WardrobeCategory.objects.create(
            user=self.other_user,
            name="남의 카테고리",
            position=0,
        )
        self.first_item = self._create_item(self.user, "첫 번째 셔츠")
        self.second_item = self._create_item(self.user, "두 번째 셔츠")
        self.unadded_item = self._create_item(
            self.user,
            "옷장 밖 셔츠",
            added=False,
        )
        self.other_item = self._create_item(self.other_user, "남의 셔츠")
        WardrobeItemCategory.objects.create(
            wardrobe_item=self.first_item,
            category=self.first_category,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @staticmethod
    def _create_item(user, name, *, added=True):
        return WardrobeItem.objects.create(
            user=user,
            s3_key=f"wardrobe/{user.pk}/{uuid.uuid4()}.png",
            item_name=name,
            category_large="상의",
            category_small="셔츠/블라우스",
            confirmed=True,
            added_to_closet_at=timezone.now() if added else None,
        )

    def _category_items_url(self, category=None):
        category = category or self.first_category
        return f"/api/v1/wardrobe/categories/{category.pk}/items/"

    def _item_categories_url(self, item=None):
        item = item or self.first_item
        return f"/api/v1/wardrobe/items/{item.pk}/categories/"

    def test_category_patch_adds_and_removes_items_atomically(self):
        response = self.client.patch(
            self._category_items_url(),
            {
                "add_item_ids": [str(self.second_item.pk)],
                "remove_item_ids": [str(self.first_item.pk)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["added_item_ids"], [str(self.second_item.pk)])
        self.assertEqual(response.data["removed_item_ids"], [str(self.first_item.pk)])
        self.assertEqual(response.data["item_count"], 1)
        self.assertEqual(
            set(
                WardrobeItemCategory.objects.filter(
                    category=self.first_category
                ).values_list("wardrobe_item_id", flat=True)
            ),
            {self.second_item.pk},
        )

    def test_category_patch_is_idempotent(self):
        response = self.client.patch(
            self._category_items_url(),
            {
                "add_item_ids": [str(self.first_item.pk), str(self.first_item.pk)],
                "remove_item_ids": [str(self.second_item.pk)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["added_item_ids"], [])
        self.assertEqual(response.data["removed_item_ids"], [])
        self.assertEqual(response.data["item_count"], 1)

    def test_category_patch_rejects_add_remove_conflict_without_mutation(self):
        response = self.client.patch(
            self._category_items_url(),
            {
                "add_item_ids": [str(self.second_item.pk)],
                "remove_item_ids": [str(self.second_item.pk)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CATEGORY_ASSIGNMENT_CONFLICT")
        self.assertFalse(
            WardrobeItemCategory.objects.filter(
                wardrobe_item=self.second_item,
                category=self.first_category,
            ).exists()
        )

    def test_category_patch_rejects_foreign_item_atomically(self):
        response = self.client.patch(
            self._category_items_url(),
            {
                "add_item_ids": [str(self.second_item.pk), str(self.other_item.pk)],
                "remove_item_ids": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "WARDROBE_ITEM_FORBIDDEN")
        self.assertFalse(
            WardrobeItemCategory.objects.filter(
                wardrobe_item=self.second_item,
                category=self.first_category,
            ).exists()
        )

    def test_category_patch_rejects_unadded_and_missing_items(self):
        cases = [self.unadded_item.pk, uuid.uuid4()]
        for item_id in cases:
            with self.subTest(item_id=item_id):
                response = self.client.patch(
                    self._category_items_url(),
                    {"add_item_ids": [str(item_id)]},
                    format="json",
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.data["code"], "WARDROBE_ITEM_NOT_FOUND")

    def test_category_patch_rejects_foreign_category(self):
        response = self.client.patch(
            self._category_items_url(self.other_category),
            {"add_item_ids": [str(self.first_item.pk)]},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "CATEGORY_FORBIDDEN")

    def test_item_put_replaces_all_categories_in_position_order(self):
        response = self.client.put(
            self._item_categories_url(),
            {
                "category_ids": [
                    str(self.second_category.pk),
                    str(self.first_category.pk),
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["custom_categories"]],
            [str(self.first_category.pk), str(self.second_category.pk)],
        )
        self.assertEqual(
            set(self.first_item.custom_categories.values_list("pk", flat=True)),
            {self.first_category.pk, self.second_category.pk},
        )

    def test_item_put_empty_list_removes_all_categories(self):
        response = self.client.put(
            self._item_categories_url(),
            {"category_ids": []},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["custom_categories"], [])
        self.assertFalse(
            WardrobeItemCategory.objects.filter(wardrobe_item=self.first_item).exists()
        )

    def test_item_put_rejects_duplicate_category_ids(self):
        response = self.client.put(
            self._item_categories_url(),
            {
                "category_ids": [
                    str(self.first_category.pk),
                    str(self.first_category.pk),
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CATEGORY_IDS_DUPLICATE")

    def test_item_put_rejects_foreign_and_missing_categories(self):
        cases = [
            (self.other_category.pk, 403, "CATEGORY_FORBIDDEN"),
            (uuid.uuid4(), 404, "CATEGORY_NOT_FOUND"),
        ]
        for category_id, expected_status, expected_code in cases:
            with self.subTest(category_id=category_id):
                response = self.client.put(
                    self._item_categories_url(),
                    {"category_ids": [str(category_id)]},
                    format="json",
                )
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.data["code"], expected_code)
                self.assertEqual(
                    set(
                        self.first_item.custom_categories.values_list("pk", flat=True)
                    ),
                    {self.first_category.pk},
                )

    def test_item_put_rejects_foreign_unadded_and_missing_items(self):
        cases = [
            (self.other_item.pk, 403, "WARDROBE_ITEM_FORBIDDEN"),
            (self.unadded_item.pk, 404, "WARDROBE_ITEM_NOT_FOUND"),
            (uuid.uuid4(), 404, "WARDROBE_ITEM_NOT_FOUND"),
        ]
        for item_id, expected_status, expected_code in cases:
            with self.subTest(item_id=item_id):
                response = self.client.put(
                    f"/api/v1/wardrobe/items/{item_id}/categories/",
                    {"category_ids": [str(self.first_category.pk)]},
                    format="json",
                )
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.data["code"], expected_code)

    def test_item_list_includes_custom_category_summaries(self):
        response = self.client.get("/api/v1/wardrobe/items/")

        self.assertEqual(response.status_code, 200)
        first_item = next(
            row for row in response.data if row["id"] == str(self.first_item.pk)
        )
        self.assertEqual(
            first_item["custom_categories"],
            [
                {
                    "id": str(self.first_category.pk),
                    "name": "출근룩",
                    "position": 0,
                }
            ],
        )

    def test_authentication_is_required(self):
        response = APIClient().put(
            self._item_categories_url(),
            {"category_ids": []},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
