from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.wardrobe.models import (
    WardrobeCategory,
    WardrobeItem,
    WardrobeItemCategory,
)

User = get_user_model()


class PersonalWardrobeCategoryModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="category-owner",
            email="category-owner@test.com",
            password="password",
        )
        self.other_user = User.objects.create_user(
            username="other-category-owner",
            email="other-category-owner@test.com",
            password="password",
        )
        self.item = WardrobeItem.objects.create(
            user=self.user,
            s3_key="wardrobe/category-owner/shirt.png",
            item_name="흰 셔츠",
            category_large="상의",
            category_small="셔츠/블라우스",
            confirmed=True,
        )

    def test_category_name_is_normalized_before_save(self):
        category = WardrobeCategory.objects.create(
            user=self.user,
            name="  Work   Look  ",
            position=0,
        )

        self.assertEqual(category.name, "Work Look")
        self.assertEqual(category.normalized_name, "work look")

    def test_normalized_name_is_unique_per_user(self):
        WardrobeCategory.objects.create(user=self.user, name="Work Look")

        with self.assertRaises(IntegrityError), transaction.atomic():
            WardrobeCategory.objects.create(user=self.user, name=" work   look ")

        other_category = WardrobeCategory.objects.create(
            user=self.other_user,
            name="WORK LOOK",
        )
        self.assertEqual(other_category.normalized_name, "work look")

    def test_empty_normalized_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            WardrobeCategory.objects.create(user=self.user, name="   ")

    def test_categories_use_position_then_creation_order(self):
        later = WardrobeCategory.objects.create(
            user=self.user,
            name="여행",
            position=2,
        )
        first = WardrobeCategory.objects.create(
            user=self.user,
            name="출근룩",
            position=0,
        )

        self.assertEqual(
            list(WardrobeCategory.objects.filter(user=self.user)),
            [first, later],
        )

    def test_item_can_belong_to_multiple_custom_categories(self):
        work = WardrobeCategory.objects.create(user=self.user, name="출근룩")
        winter = WardrobeCategory.objects.create(user=self.user, name="겨울옷")

        WardrobeItemCategory.objects.create(
            wardrobe_item=self.item,
            category=work,
        )
        WardrobeItemCategory.objects.create(
            wardrobe_item=self.item,
            category=winter,
        )

        self.assertCountEqual(
            self.item.custom_categories.values_list("id", flat=True),
            [work.id, winter.id],
        )

    def test_duplicate_item_category_pair_is_rejected(self):
        category = WardrobeCategory.objects.create(user=self.user, name="출근룩")
        WardrobeItemCategory.objects.create(
            wardrobe_item=self.item,
            category=category,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            WardrobeItemCategory.objects.create(
                wardrobe_item=self.item,
                category=category,
            )

    def test_item_and_category_owners_must_match(self):
        other_category = WardrobeCategory.objects.create(
            user=self.other_user,
            name="남의 카테고리",
        )

        with self.assertRaises(ValidationError):
            WardrobeItemCategory.objects.create(
                wardrobe_item=self.item,
                category=other_category,
            )

    def test_deleting_category_removes_link_but_preserves_item(self):
        category = WardrobeCategory.objects.create(user=self.user, name="출근룩")
        link = WardrobeItemCategory.objects.create(
            wardrobe_item=self.item,
            category=category,
        )

        category.delete()

        self.assertTrue(WardrobeItem.objects.filter(pk=self.item.pk).exists())
        self.assertFalse(WardrobeItemCategory.objects.filter(pk=link.pk).exists())

    def test_deleting_item_removes_link_but_preserves_category(self):
        category = WardrobeCategory.objects.create(user=self.user, name="출근룩")
        link = WardrobeItemCategory.objects.create(
            wardrobe_item=self.item,
            category=category,
        )

        self.item.delete()

        self.assertTrue(WardrobeCategory.objects.filter(pk=category.pk).exists())
        self.assertFalse(WardrobeItemCategory.objects.filter(pk=link.pk).exists())
