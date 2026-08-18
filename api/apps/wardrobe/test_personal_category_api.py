import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.wardrobe import taxonomy as T
from apps.wardrobe.models import (
    WardrobeCategory,
    WardrobeItem,
    WardrobeItemCategory,
)

User = get_user_model()


class PersonalWardrobeCategoryApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="category-api-owner",
            email="category-api-owner@test.com",
            password="password",
        )
        self.other_user = User.objects.create_user(
            username="other-category-api-owner",
            email="other-category-api-owner@test.com",
            password="password",
        )
        self.added_item = WardrobeItem.objects.create(
            user=self.user,
            s3_key="wardrobe/category-api-owner/added-shirt.png",
            item_name="흰 셔츠",
            category_large="상의",
            category_small="셔츠/블라우스",
            confirmed=True,
            added_to_closet_at=timezone.now(),
        )
        self.unadded_item = WardrobeItem.objects.create(
            user=self.user,
            s3_key="wardrobe/category-api-owner/unadded-shirt.png",
            item_name="옷장 밖 셔츠",
            category_large="상의",
            category_small="셔츠/블라우스",
            confirmed=True,
        )
        self.category = WardrobeCategory.objects.create(
            user=self.user,
            name="출근룩",
            position=0,
        )
        WardrobeItemCategory.objects.create(
            wardrobe_item=self.added_item,
            category=self.category,
        )
        WardrobeItemCategory.objects.create(
            wardrobe_item=self.unadded_item,
            category=self.category,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.list_url = "/api/v1/wardrobe/categories/"

    def test_authentication_is_required(self):
        response = APIClient().get(self.list_url)

        self.assertEqual(response.status_code, 401)

    def test_list_returns_all_system_categories_and_owned_custom_categories(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["name"] for row in response.data["system_categories"]],
            T.CATEGORY_LARGE,
        )
        self.assertEqual(response.data["system_categories"][0]["id"], "system:상의")
        self.assertEqual(response.data["system_categories"][0]["item_count"], 1)
        self.assertFalse(response.data["system_categories"][0]["mutable"])
        self.assertEqual(len(response.data["custom_categories"]), 1)
        custom = response.data["custom_categories"][0]
        self.assertEqual(custom["id"], str(self.category.pk))
        self.assertEqual(custom["type"], "CUSTOM")
        self.assertEqual(custom["item_count"], 1)
        self.assertTrue(custom["mutable"])

    def test_create_normalizes_name_and_assigns_next_position(self):
        response = self.client.post(
            self.list_url,
            {"name": "  여행   준비  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "여행 준비")
        self.assertEqual(response.data["position"], 1)
        self.assertEqual(response.data["item_count"], 0)
        created = WardrobeCategory.objects.get(pk=response.data["id"])
        self.assertEqual(created.normalized_name, "여행 준비")

    def test_create_rejects_duplicate_normalized_name(self):
        response = self.client.post(
            self.list_url,
            {"name": "  출근룩  "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "CATEGORY_NAME_DUPLICATE")

    def test_create_rejects_system_and_virtual_names(self):
        for name in ["상의", "전체", "미분류"]:
            with self.subTest(name=name):
                response = self.client.post(
                    self.list_url,
                    {"name": name},
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["code"], "CATEGORY_NAME_RESERVED")

    def test_create_rejects_missing_blank_and_long_names(self):
        cases = [
            ({}, "CATEGORY_NAME_REQUIRED"),
            ({"name": "   "}, "CATEGORY_NAME_REQUIRED"),
            ({"name": "가" * 31}, "CATEGORY_NAME_TOO_LONG"),
        ]
        for payload, code in cases:
            with self.subTest(code=code):
                response = self.client.post(self.list_url, payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["code"], code)

    def test_patch_renames_category_without_changing_position(self):
        response = self.client.patch(
            f"{self.list_url}{self.category.pk}/",
            {"name": "  회사   코디  "},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "회사 코디")
        self.assertEqual(response.data["position"], 0)
        self.category.refresh_from_db()
        self.assertEqual(self.category.normalized_name, "회사 코디")

    def test_delete_removes_category_links_but_preserves_items(self):
        response = self.client.delete(f"{self.list_url}{self.category.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(WardrobeCategory.objects.filter(pk=self.category.pk).exists())
        self.assertTrue(WardrobeItem.objects.filter(pk=self.added_item.pk).exists())
        self.assertFalse(
            WardrobeItemCategory.objects.filter(category_id=self.category.pk).exists()
        )

    def test_other_users_category_is_forbidden(self):
        other_category = WardrobeCategory.objects.create(
            user=self.other_user,
            name="남의 카테고리",
        )

        response = self.client.patch(
            f"{self.list_url}{other_category.pk}/",
            {"name": "침범"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "CATEGORY_FORBIDDEN")

    def test_missing_category_returns_contract_error(self):
        response = self.client.delete(f"{self.list_url}{uuid.uuid4()}/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "CATEGORY_NOT_FOUND")
