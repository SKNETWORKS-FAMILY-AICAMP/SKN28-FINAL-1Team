from __future__ import annotations

from django.test import TestCase

from apps.lookbook.models import CuratedLook
from apps.lookbook.services import discovery


class DiscoveryServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        CuratedLook.objects.create(
            external_id="woman-casual-001",
            gender=CuratedLook.Gender.WOMAN,
            category="캐주얼",
            title="여성 캐주얼 룩",
            subtitle="여성 테스트",
            cover_image_url="images/woman-casual-001.png",
            tags=["캐주얼"],
        )
        CuratedLook.objects.create(
            external_id="man-casual-001",
            gender=CuratedLook.Gender.MAN,
            category="캐주얼",
            title="남성 캐주얼 룩",
            subtitle="남성 테스트",
            cover_image_url="images/man-casual-001.png",
            tags=["캐주얼"],
        )
        CuratedLook.objects.create(
            external_id="man-hidden-001",
            gender=CuratedLook.Gender.MAN,
            category="캐주얼",
            title="비공개 남성 룩",
            subtitle="노출되지 않음",
            cover_image_url="images/man-hidden-001.png",
            tags=["캐주얼"],
            is_active=False,
        )

    def test_default_feed_returns_all_active_genders(self) -> None:
        result = discovery.list_looks(discovery.DiscoveryQuery())

        self.assertEqual(result["count"], 2)
        self.assertEqual(
            {look["gender"] for look in result["results"]}, {"WOMAN", "MAN"}
        )

    def test_woman_filter_only_returns_active_woman_looks(self) -> None:
        result = discovery.list_looks(
            discovery.DiscoveryQuery(gender="WOMAN", limit=50)
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["id"], "curated-woman-casual-001")
        self.assertEqual(result["results"][0]["gender"], "WOMAN")

    def test_man_filter_only_returns_active_man_looks(self) -> None:
        result = discovery.list_looks(
            discovery.DiscoveryQuery(gender="MAN", limit=50)
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["id"], "curated-man-casual-001")
        self.assertEqual(result["results"][0]["gender"], "MAN")

    def test_tag_and_gender_filters_are_combined(self) -> None:
        result = discovery.list_looks(
            discovery.DiscoveryQuery(gender="MAN", tag="데이트")
        )

        self.assertEqual(result, {"count": 0, "next_offset": None, "results": []})
