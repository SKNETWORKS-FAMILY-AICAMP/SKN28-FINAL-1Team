from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.recommend.models import DailyLook
from apps.recommend.services import daily_look
from apps.recommend.services.outfit_render import RenderSource
from apps.recommend.services.render_cache import RenderCacheEntry
from apps.recommend.services.retriever import OutfitCandidate, Reason

CONTEXT = {
    "weather": {"temperature": 18.4},
    "body": {"gender": "male", "height": 175, "weight": 70},
    "pursuit": {"preferred": {"style": ["casual"]}, "avoided": {}},
}


def candidate() -> OutfitCandidate:
    return OutfitCandidate(
        point_id="point-1",
        golden_id="golden-1",
        score=0.91,
        similarity=0.88,
        reasons=(Reason(source="rule", delta=0.1, text="균형 잡힌 실루엣입니다."),),
        payload={
            "presentation_group": "man",
            "source_bucket": "golden-bucket",
            "items": [
                {
                    "item_key": "top-1",
                    "item_name": "셔츠",
                    "category_large": "TOP",
                    "s3_key": "items/top.png",
                },
                {
                    "item_key": "bottom-1",
                    "item_name": "팬츠",
                    "category_large": "BOTTOM",
                    "s3_key": "items/bottom.png",
                },
            ],
        },
    )


@override_settings(
    CHAT_GOLDENSET_DATASET_VERSION="v2",
    CHAT_GOLDENSET_DATASET_STATUSES=("PUBLISHED",),
)
class DailyLookServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(username="daily-user")

    @patch("apps.recommend.services.daily_look.daily_look_queue.enqueue")
    @patch(
        "apps.recommend.services.daily_look.build_analysis_context",
        return_value=CONTEXT,
    )
    def test_ensure_is_one_row_per_day_and_enqueues_once(
        self, _context, enqueue
    ) -> None:
        first, created = daily_look.ensure_today_look(self.user)
        second, created_again = daily_look.ensure_today_look(self.user)

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(DailyLook.objects.count(), 1)
        enqueue.assert_called_once_with(first.pk)

    @patch("apps.recommend.services.daily_look.render_artifacts.get_or_render")
    @patch("apps.recommend.services.daily_look.gemini.write_daily_look_copy")
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    @patch("apps.recommend.services.daily_look.load_body_rules")
    def test_run_uses_current_gender_filter_and_shared_renderer(
        self, rules, retrieve, write_copy, get_or_render
    ) -> None:
        rules.return_value = SimpleNamespace(schema_version="rules-v1")
        retrieve.return_value = [candidate()]
        write_copy.side_effect = RuntimeError("optional copy disabled")
        get_or_render.return_value = (
            RenderCacheEntry(
                "f" * 64,
                "render-bucket",
                "shared/render",
                "image/png",
                100,
                "openrouter",
                "qwen/qwen-image-3-pro",
                "mixed-outfit-render-v2",
                2,
                {},
            ),
            False,
        )
        look = DailyLook.objects.create(
            user=self.user,
            look_date=daily_look.timezone.localdate(),
            status=DailyLook.Status.PROCESSING,
            weather=CONTEXT["weather"],
            body=CONTEXT["body"],
            body_profile={"silhouette": "rectangle", "bmi_band": "normal"},
            pursuit=CONTEXT["pursuit"],
        )

        daily_look.run(look)
        look.refresh_from_db()

        request = retrieve.call_args.args[0]
        self.assertEqual(set(request.presentation_groups), {"man", "unisex"})
        self.assertEqual(request.dataset_version, "v2")
        render_request = get_or_render.call_args.args[0]
        self.assertEqual(render_request.subject_presentation, "man")
        self.assertEqual(
            [item.source_type for item in render_request.items],
            [RenderSource.GOLDENSET_ITEM, RenderSource.GOLDENSET_ITEM],
        )
        self.assertEqual(look.status, DailyLook.Status.SUCCEEDED)
        self.assertEqual(look.result["render_image"]["s3_key"], "shared/render")

    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    @patch("apps.recommend.services.daily_look.load_body_rules")
    def test_missing_gender_is_empty_without_qdrant(self, rules, retrieve) -> None:
        rules.return_value = SimpleNamespace(schema_version="rules-v1")
        look = DailyLook.objects.create(
            user=self.user,
            look_date=daily_look.timezone.localdate(),
            status=DailyLook.Status.PROCESSING,
            body={"height": 175},
        )

        daily_look.run(look)
        look.refresh_from_db()

        self.assertEqual(look.status, DailyLook.Status.EMPTY)
        retrieve.assert_not_called()


class DailyLookApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(username="daily-api")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("apps.recommend.views.daily_look_service.refresh_render")
    @patch("apps.recommend.views.daily_look_service.ensure_today_look")
    def test_today_returns_pending_contract(self, ensure, refresh) -> None:
        look = DailyLook.objects.create(
            user=self.user,
            look_date=daily_look.timezone.localdate(),
        )
        ensure.return_value = (look, True)

        response = self.client.get(reverse("recommend:daily-look-today"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], DailyLook.Status.QUEUED)
        self.assertIsNotNone(response.data["poll_after_ms"])
        refresh.assert_called_once_with(look)

    def test_today_requires_authentication(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("recommend:daily-look-today"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
