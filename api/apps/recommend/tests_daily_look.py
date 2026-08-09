"""오늘의 룩 테스트.

사용자 입력이 없는 기능이라, 사람이 눌러서 확인할 수 있는 지점이 적다. 대신
아래 네 가지가 어긋나면 사용자는 조용히 잘못된 화면을 본다.

- 하루 1건 멱등성 (여러 기기 동시 로그인)
- '생성 중'과 '후보 없음'의 구분 (폴링할지 말지가 갈린다)
- 큐가 죽었을 때 행이 고아로 남지 않는지
- LLM이 후보에 없는 코디를 지어내지 않는지
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.recommend.models import DailyLook
from apps.recommend.services import daily_look as service

User = get_user_model()

CONTEXT = {
    "weather": {"region": "서울", "temperature": 28.4, "sky_state": "맑음"},
    "body": {"height": 175, "weight": 70, "shoulder": 48, "hip": 42, "waist": 34},
    "pursuit": {"preferred": {"styles": ["minimal"]}, "avoided": {}},
    "personalized": True,
}


class _FakeCandidate:
    """retriever.OutfitCandidate 계약만 흉내낸다."""

    def __init__(self, golden_id="095", score=88.0):
        self.point_id = f"point-{golden_id}"
        self.golden_id = golden_id
        self.score = score
        self.similarity = 0.88
        self.reasons = ()
        self.payload = {
            "golden_id": golden_id,
            "item_keys": [f"{golden_id}#000"],
            "source_bucket": "skn28-cozy3",
            "source_key": f"goldenset/source/{golden_id}.PNG",
            "exposable": False,
            "items": [
                {
                    "item_key": f"{golden_id}#000",
                    "item_name": "화이트 셔츠",
                    "category_large": "상의",
                    "layer_role": "기본 상의",
                    "color": "화이트",
                    "s3_key": f"goldenset/derived/v1/{golden_id}/item_000.png",
                }
            ],
        }


class EnsureTodayLookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="u1")

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_creates_one_row_and_enqueues(self, _ctx, push):
        look, created = service.ensure_today_look(self.user)
        self.assertTrue(created)
        self.assertEqual(look.status, DailyLook.Status.QUEUED)
        self.assertEqual(push.call_count, 1)
        # 체형 판정 스냅샷이 함께 저장돼야 워커가 컨텍스트를 다시 만들지 않는다
        self.assertEqual(look.body_profile["silhouette"], "inverted")

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_second_call_same_day_is_idempotent(self, _ctx, push):
        first, created_first = service.ensure_today_look(self.user)
        second, created_second = service.ensure_today_look(self.user)
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        # 두 번째 호출은 큐에 다시 넣지 않는다 (워커가 같은 작업을 두 번 돌게 된다)
        self.assertEqual(push.call_count, 1)
        self.assertEqual(DailyLook.objects.filter(user=self.user).count(), 1)

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_previous_day_row_does_not_block_today(self, _ctx, _push):
        DailyLook.objects.create(
            user=self.user,
            look_date=service.today() - timedelta(days=1),
            status=DailyLook.Status.SUCCEEDED,
        )
        _, created = service.ensure_today_look(self.user)
        self.assertTrue(created)
        self.assertEqual(DailyLook.objects.filter(user=self.user).count(), 2)

    @patch("apps.recommend.services.daily_look.queue_service.push", side_effect=RuntimeError("redis down"))
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_queue_failure_still_leaves_a_row(self, _ctx, _push):
        """Redis가 죽어도 행은 남는다. 워커의 --sweep이 나중에 주워간다."""
        look, created = service.ensure_today_look(self.user)
        self.assertTrue(created)
        self.assertEqual(look.status, DailyLook.Status.QUEUED)


class RunTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="u2")
        self.look = DailyLook.objects.create(
            user=self.user,
            look_date=service.today(),
            weather=CONTEXT["weather"],
            body=CONTEXT["body"],
            body_profile={"silhouette": "inverted", "bmi_band": "normal", "ratios": {}},
            pursuit=CONTEXT["pursuit"],
        )

    @patch("apps.recommend.services.daily_look.retrieve_outfits", return_value=[])
    def test_no_candidate_becomes_empty_not_failed(self, _retrieve):
        """폴링해도 결과가 바뀌지 않는 상태다. 실패와 구분해야 안내가 달라진다."""
        service.run(self.look)
        self.look.refresh_from_db()
        self.assertEqual(self.look.status, DailyLook.Status.EMPTY)
        self.assertEqual(self.look.result, {})

    @patch("apps.recommend.services.daily_look.gemini.write_daily_look_copy")
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    def test_success_stores_result_and_candidates(self, retrieve, copy):
        retrieve.return_value = [_FakeCandidate()]
        copy.return_value = type(
            "R", (), {
                "parsed": {"headline": "가볍게", "rationale_ko": "...",
                           "styling_tips": ["팁"], "items": [
                               {"item_key": "095#000", "note": "기본 기장"}]},
                "request": {"x": 1}, "response": {"y": 2},
                "model": "gemini-3.5-flash", "latency_ms": 1200,
            },
        )()
        service.run(self.look)
        self.look.refresh_from_db()
        self.assertEqual(self.look.status, DailyLook.Status.SUCCEEDED)
        self.assertEqual(self.look.result["golden_id"], "095")
        self.assertEqual(self.look.result["generated_by"], "llm")
        self.assertEqual(self.look.result["items"][0]["note"], "기본 기장")
        self.assertEqual(self.look.candidates[0]["golden_id"], "095")
        self.assertEqual(self.look.llm_latency_ms, 1200)

    @patch("apps.recommend.services.daily_look.gemini.write_daily_look_copy")
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    def test_selection_is_deterministic_top_ranked(self, retrieve, copy):
        """코디는 리트리버가 정한다. LLM은 고르지 않는다."""
        retrieve.return_value = [
            _FakeCandidate("095", score=88.0),
            _FakeCandidate("096", score=42.0),
        ]
        copy.return_value = type("R", (), {
            "parsed": {}, "request": {}, "response": {}, "model": "m", "latency_ms": 1})()
        service.run(self.look)
        self.look.refresh_from_db()
        self.assertEqual(self.look.result["golden_id"], "095")
        # LLM에는 확정된 코디 하나만 넘어간다 (후보 목록이 아니다)
        self.assertEqual(copy.call_args.kwargs["outfit"]["golden_id"], "095")

    @patch(
        "apps.recommend.services.daily_look.gemini.write_daily_look_copy",
        side_effect=RuntimeError("gemini down"),
    )
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    def test_llm_failure_keeps_the_recommendation(self, retrieve, _copy):
        """문장이 실패해도 추천은 살아남아야 한다. 예전에는 FAILED가 됐다."""
        retrieve.return_value = [_FakeCandidate()]
        service.run(self.look)
        self.look.refresh_from_db()
        self.assertEqual(self.look.status, DailyLook.Status.SUCCEEDED)
        self.assertEqual(self.look.result["golden_id"], "095")
        self.assertEqual(self.look.result["generated_by"], "template")
        self.assertTrue(self.look.result["rationale_ko"])
        self.assertIn("문장 생성 실패", self.look.error)

    @patch("apps.recommend.services.daily_look.gemini.write_daily_look_copy")
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    def test_result_carries_s3_refs_not_urls(self, retrieve, copy):
        """presigned URL은 만료된다. DB에는 버킷·키만 담고 직렬화가 서명한다."""
        retrieve.return_value = [_FakeCandidate()]
        copy.return_value = type("R", (), {
            "parsed": {}, "request": {}, "response": {}, "model": "m", "latency_ms": 1})()
        service.run(self.look)
        self.look.refresh_from_db()
        item = self.look.result["items"][0]
        self.assertEqual(item["s3_bucket"], "skn28-cozy3")
        self.assertTrue(item["s3_key"].endswith("item_000.png"))
        self.assertNotIn("image_url", item)
        self.assertNotIn("https://", json.dumps(self.look.result))

    @patch("apps.recommend.services.daily_look.gemini.write_daily_look_copy")
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    def test_non_exposable_outfit_has_no_original_image(self, retrieve, copy):
        retrieve.return_value = [_FakeCandidate()]
        copy.return_value = type("R", (), {
            "parsed": {}, "request": {}, "response": {}, "model": "m", "latency_ms": 1})()
        service.run(self.look)
        self.look.refresh_from_db()
        self.assertIsNone(self.look.result["outfit_image"])

    @patch("apps.recommend.services.daily_look.gemini.write_daily_look_copy")
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    def test_llm_receives_tags_not_images(self, retrieve, copy):
        """골든 원본은 대개 노출 불가다. 프롬프트에 이미지가 실리면 안 된다."""
        retrieve.return_value = [_FakeCandidate()]
        copy.return_value = type("R", (), {
            "parsed": {}, "request": {}, "response": {}, "model": "m", "latency_ms": 1})()
        service.run(self.look)
        sent = copy.call_args.kwargs["outfit"]
        self.assertIn("items", sent)
        self.assertNotIn("source_uri", json.dumps(sent, ensure_ascii=False))


class ClaimTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="u3")

    def test_succeeded_row_is_not_reprocessed(self):
        look = DailyLook.objects.create(
            user=self.user, look_date=service.today(),
            status=DailyLook.Status.SUCCEEDED,
        )
        self.assertIsNone(service.claim(str(look.pk)))

    def test_queued_row_moves_to_processing(self):
        look = DailyLook.objects.create(user=self.user, look_date=service.today())
        claimed = service.claim(str(look.pk))
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.status, DailyLook.Status.PROCESSING)

    def test_missing_row(self):
        self.assertIsNone(service.claim("00000000-0000-0000-0000-000000000000"))


class TodayLookApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="u4")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse("recommend:daily-look-today")

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_first_call_returns_pending_with_poll_interval(self, _ctx, _push):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "QUEUED")
        self.assertIsNone(body["result"])
        # 프론트가 폴링 주기를 알아야 한다
        self.assertIsNotNone(body["poll_after_ms"])
        self.assertIn("만들고 있어요", body["detail"])

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_ready_look_has_no_poll_interval(self, _ctx, _push):
        look, _ = service.ensure_today_look(self.user)
        look.status = DailyLook.Status.SUCCEEDED
        look.result = {"headline": "가볍게", "golden_id": "095", "rationale_ko": "..."}
        look.save()
        body = self.client.get(self.url).json()
        self.assertEqual(body["status"], "SUCCEEDED")
        self.assertEqual(body["result"]["golden_id"], "095")
        self.assertIsNone(body["poll_after_ms"])
        self.assertIsNone(body["detail"])

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_empty_look_tells_frontend_to_stop_polling(self, _ctx, _push):
        look, _ = service.ensure_today_look(self.user)
        look.status = DailyLook.Status.EMPTY
        look.save()
        body = self.client.get(self.url).json()
        self.assertEqual(body["status"], "EMPTY")
        self.assertIsNone(body["poll_after_ms"])
        self.assertIn("입력하면", body["detail"])

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(self.url).status_code, 401)

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context", return_value=CONTEXT)
    def test_context_reports_missing_measurements(self, _ctx, _push):
        """프론트가 '어깨너비를 입력하면 더 정확해져요'를 띄울 수 있어야 한다."""
        body = self.client.get(self.url).json()
        self.assertIn("thigh", body["context"]["missing_measurements"])
        self.assertTrue(body["context"]["used_body"])
