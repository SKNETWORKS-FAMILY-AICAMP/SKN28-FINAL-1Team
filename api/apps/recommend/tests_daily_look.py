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
from apps.recommend.services import outfit_render

User = get_user_model()

CONTEXT = {
    "weather": {"region": "서울", "temperature": 28.4, "sky_state": "맑음"},
    # 둘레는 cm 실측값이어야 한다. 예전엔 어깨너비와 섞어 놔서 실루엣 판정이
    # 어떤 값이든 삼각형으로 뭉치는 것을 이 픽스처가 가려 주었다.
    "body": {"height": 175, "weight": 70, "chest": 96, "waist": 80, "hip": 94,
             "shoulder": 44, "gender": "male"},
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
        # 체형 판정 스냅샷이 함께 저장돼야 워커가 컨텍스트를 다시 만들지 않는다.
        # 가슴96·허리80·엉덩이94는 상하 균형(±5%)에 허리도 뚜렷하지 않아
        # 직사각형이다 — 어깨너비는 실루엣 판정에서 빠졌다(둘레와 단위가 다르다).
        self.assertEqual(look.body_profile["silhouette"], "rectangle")

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

    @patch("apps.recommend.services.daily_look.gemini.write_daily_look_copy")
    @patch("apps.recommend.services.daily_look.retrieve_outfits")
    def test_recent_golden_ids_are_passed_as_exclusions(self, retrieve, copy):
        """어제 나간 코디는 리트리버에 제외 목록으로 넘어간다.

        골든셋·규칙이 그대로면 순위도 그대로다 — 이 전달이 빠지면 매일 같은
        1위가 뽑혀 "오늘의" 룩이 아니게 된다.
        """
        DailyLook.objects.create(
            user=self.user,
            look_date=service.today() - timedelta(days=1),
            status=DailyLook.Status.SUCCEEDED,
            result={"golden_id": "old-1"},
        )
        retrieve.return_value = [_FakeCandidate()]
        copy.return_value = type("R", (), {
            "parsed": {}, "request": {}, "response": {}, "model": "m", "latency_ms": 1})()
        service.run(self.look)
        request = retrieve.call_args.args[0]
        self.assertEqual(request.exclude_golden_ids, frozenset({"old-1"}))


class RecentGoldenIdsTests(TestCase):
    """_recent_golden_ids — 무엇이 '최근 추천분'으로 세어지는가."""

    def setUp(self):
        self.user = User.objects.create(username="u-recent")
        self.today = service.today()

    def _make(self, days_ago: int, golden_id: str, *, user=None,
              status=DailyLook.Status.SUCCEEDED):
        return DailyLook.objects.create(
            user=user or self.user,
            look_date=self.today - timedelta(days=days_ago),
            status=status,
            result={"golden_id": golden_id} if golden_id else {},
        )

    def test_window_is_five_days_inclusive(self):
        """1~5일 전은 제외 대상, 6일 전은 다시 나올 수 있다."""
        self._make(1, "d1")
        self._make(5, "d5")
        self._make(6, "d6")
        got = service._recent_golden_ids(self.user, self.today)
        self.assertEqual(got, frozenset({"d1", "d5"}))

    def test_only_succeeded_looks_count(self):
        """실패·EMPTY 행은 사용자가 본 추천이 아니다 — 반복으로 치지 않는다."""
        self._make(1, "ok")
        self._make(2, "", status=DailyLook.Status.FAILED)
        self._make(3, "", status=DailyLook.Status.EMPTY)
        got = service._recent_golden_ids(self.user, self.today)
        self.assertEqual(got, frozenset({"ok"}))

    def test_other_users_do_not_leak(self):
        """제외는 계정 단위다. 남이 본 코디가 내 추천 폭을 좁히면 안 된다."""
        other = User.objects.create(username="u-other")
        self._make(1, "mine")
        self._make(1, "theirs", user=other)
        got = service._recent_golden_ids(self.user, self.today)
        self.assertEqual(got, frozenset({"mine"}))

    def test_today_row_is_not_counted(self):
        """FAILED 재시도로 같은 날 run()이 다시 돌 때 자기 자신을 빼면 안 된다."""
        self._make(0, "today-self")
        got = service._recent_golden_ids(self.user, self.today)
        self.assertEqual(got, frozenset())


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
        self.assertIn("thigh_length", body["context"]["missing_measurements"])
        self.assertTrue(body["context"]["used_body"])


RESULT_WITHOUT_RENDER = {
    "headline": "가볍게",
    "golden_id": "095",
    "rationale_ko": "...",
    "render_image": None,
    "items": [
        {"item_key": "095#000", "name": "셔츠", "category": "상의",
         "s3_bucket": "skn28-cozy3",
         "s3_key": "goldenset/derived/v1/095/item_000.png"},
        {"item_key": "095#001", "name": "슬랙스", "category": "하의",
         "s3_bucket": "skn28-cozy3",
         "s3_key": "goldenset/derived/v1/095/item_001.png"},
    ],
}


class RefreshRenderTests(TestCase):
    """조회 시점의 착용 이미지 보정.

    생성이 한 번 실패해도 다음 시행에서 성공하는 일이 잦다(제공자 일시 오류·
    타임아웃). 그런데 결과 JSON은 생성이 끝날 때 한 번만 쓰이므로, 그 뒤에
    이미지가 S3에 생겨도 행은 비어 있는 채로 남고 사용자는 그날 내내 대표
    이미지를 못 본다. 그래서 조회할 때마다 한 번 더 본다.
    """

    def setUp(self):
        self.user = User.objects.create(username="u5")
        self.look = DailyLook.objects.create(
            user=self.user,
            look_date=service.today(),
            status=DailyLook.Status.SUCCEEDED,
            result=dict(RESULT_WITHOUT_RENDER),
            error="착용 이미지 생성 실패(추천은 정상): 400 ...",
        )

    @patch("apps.recommend.services.daily_look._schedule_render_retry")
    @patch("apps.recommend.services.daily_look.outfit_render.existing_render")
    def test_image_created_by_a_later_attempt_gets_attached(self, existing, schedule):
        existing.return_value = outfit_render.RenderRef(
            "skn28-cozy3", "goldenset/derived/v1/095/render_frontal.jpg"
        )
        self.assertTrue(service.refresh_render(self.look))

        self.look.refresh_from_db()
        self.assertEqual(
            self.look.result["render_image"],
            {"s3_bucket": "skn28-cozy3",
             "s3_key": "goldenset/derived/v1/095/render_frontal.jpg"},
        )
        schedule.assert_not_called()

    @patch("apps.recommend.services.daily_look._schedule_render_retry")
    @patch("apps.recommend.services.daily_look.outfit_render.existing_render")
    def test_stale_failure_message_is_cleared(self, existing, _schedule):
        """이미지가 붙었는데 실패 메시지가 남으면 멀쩡한 행을 문제로 읽는다."""
        existing.return_value = outfit_render.RenderRef("b", "k.png")
        service.refresh_render(self.look)
        self.look.refresh_from_db()
        self.assertEqual(self.look.error, "")

    @patch("apps.recommend.services.daily_look._schedule_render_retry")
    @patch("apps.recommend.services.daily_look.outfit_render.existing_render",
           return_value=None)
    def test_missing_image_schedules_a_retry_instead_of_generating(
        self, _existing, schedule
    ):
        """조회는 사용자 요청 스레드다. 수십 초짜리 생성을 여기서 하면 안 된다."""
        self.assertFalse(service.refresh_render(self.look))
        schedule.assert_called_once()
        self.look.refresh_from_db()
        self.assertIsNone(self.look.result["render_image"])

    @patch("apps.recommend.services.daily_look.outfit_render.existing_render")
    def test_already_attached_look_is_not_touched(self, existing):
        """S3 HEAD는 싸지만 공짜는 아니다. 폴링마다 부를 이유가 없다."""
        self.look.result = {**RESULT_WITHOUT_RENDER,
                            "render_image": {"s3_bucket": "b", "s3_key": "k.png"}}
        self.look.save()
        self.assertFalse(service.refresh_render(self.look))
        existing.assert_not_called()

    @patch("apps.recommend.services.daily_look.outfit_render.existing_render")
    def test_unfinished_look_is_skipped(self, existing):
        self.look.status = DailyLook.Status.QUEUED
        self.look.save()
        self.assertFalse(service.refresh_render(self.look))
        existing.assert_not_called()

    @patch("apps.recommend.services.daily_look.outfit_render.existing_render")
    def test_result_without_item_images_is_skipped(self, existing):
        self.look.result = {"headline": "x", "golden_id": "095", "items": []}
        self.look.save()
        self.assertFalse(service.refresh_render(self.look))
        existing.assert_not_called()

    def test_category_is_restored_for_reference_priority(self):
        """_build_result가 category_large를 category로 줄여 담는다.

        되돌리지 않으면 참조를 고를 때 모든 아이템이 '분류 없음'이 되어, 가방이
        남고 바지가 빠지는 조합이 나온다.
        """
        _bucket, items = service._render_source(RESULT_WITHOUT_RENDER)
        self.assertEqual([i["category_large"] for i in items], ["상의", "하의"])


class ScheduleRenderRetryTests(TestCase):
    """재생성 예약은 쿨다운으로 묶는다. 없으면 폴링마다 생성이 쌓인다."""

    def setUp(self):
        self.user = User.objects.create(username="u6")
        self.look = DailyLook.objects.create(
            user=self.user, look_date=service.today(),
            status=DailyLook.Status.SUCCEEDED, result=dict(RESULT_WITHOUT_RENDER),
        )

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.queue_service.get_client")
    def test_lock_is_taken_before_pushing(self, get_client, push):
        client = get_client.return_value
        client.set.return_value = True
        service._schedule_render_retry(self.look, "bucket", "k/item_000.png")

        # 락 키는 사용자가 아니라 코디 단위다 — 같은 코디를 받은 사용자가
        # 여럿이어도 만들 이미지는 하나다.
        lock_key = client.set.call_args.args[0]
        self.assertIn("bucket", lock_key)
        self.assertIn("k/item_000.png", lock_key)
        self.assertNotIn(str(self.user.pk), lock_key)
        self.assertTrue(client.set.call_args.kwargs["nx"])
        push.assert_called_once()
        self.assertEqual(push.call_args.args[0]["job"], service.JOB_RENDER)

    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.queue_service.get_client")
    def test_second_call_within_cooldown_does_not_push(self, get_client, push):
        get_client.return_value.set.return_value = False   # 이미 잡혀 있음
        service._schedule_render_retry(self.look, "bucket", "k/item_000.png")
        push.assert_not_called()

    @patch("apps.recommend.services.daily_look.queue_service.get_client",
           side_effect=RuntimeError("redis down"))
    def test_redis_failure_does_not_break_the_read(self, _client):
        """보정은 부가 기능이다. Redis가 죽어도 조회는 200이어야 한다."""
        service._schedule_render_retry(self.look, "bucket", "k/item_000.png")


class RunRenderOnlyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="u7")
        self.look = DailyLook.objects.create(
            user=self.user, look_date=service.today(),
            status=DailyLook.Status.SUCCEEDED, result=dict(RESULT_WITHOUT_RENDER),
        )

    @patch("apps.recommend.services.daily_look.outfit_render.ensure_render")
    def test_generates_and_attaches_without_changing_status(self, ensure):
        ensure.return_value = outfit_render.RenderRef("b", "k.jpg")
        self.assertTrue(service.run_render_only(str(self.look.pk)))
        self.look.refresh_from_db()
        # 이미지가 없다고 사용자에게 '생성 중'을 다시 보여줄 이유는 없다
        self.assertEqual(self.look.status, DailyLook.Status.SUCCEEDED)
        self.assertEqual(self.look.result["render_image"]["s3_key"], "k.jpg")

    @patch("apps.recommend.services.daily_look.outfit_render.ensure_render",
           side_effect=RuntimeError("again 400"))
    def test_failure_is_recorded_but_recommendation_survives(self, _ensure):
        self.assertFalse(service.run_render_only(str(self.look.pk)))
        self.look.refresh_from_db()
        self.assertEqual(self.look.status, DailyLook.Status.SUCCEEDED)
        self.assertIn("again 400", self.look.error)

    @patch("apps.recommend.services.daily_look.outfit_render.ensure_render")
    def test_already_attached_is_a_no_op(self, ensure):
        self.look.result = {**RESULT_WITHOUT_RENDER,
                            "render_image": {"s3_bucket": "b", "s3_key": "k.png"}}
        self.look.save()
        self.assertFalse(service.run_render_only(str(self.look.pk)))
        ensure.assert_not_called()


class TodayLookApiRefreshTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="u8")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse("recommend:daily-look-today")

    @patch("apps.recommend.services.daily_look._schedule_render_retry")
    @patch("apps.recommend.services.daily_look.outfit_render.existing_render")
    @patch("apps.recommend.serializers._image_url", return_value="https://signed/x")
    @patch("apps.recommend.services.daily_look.queue_service.push")
    @patch("apps.recommend.services.daily_look.build_analysis_context",
           return_value=CONTEXT)
    def test_get_fills_in_an_image_that_appeared_later(
        self, _ctx, _push, _sign, existing, _schedule
    ):
        look, _ = service.ensure_today_look(self.user)
        look.status = DailyLook.Status.SUCCEEDED
        look.result = dict(RESULT_WITHOUT_RENDER)
        look.save()
        existing.return_value = outfit_render.RenderRef("b", "k.jpg")

        body = self.client.get(self.url).json()

        self.assertEqual(body["result"]["render_image_url"], "https://signed/x")
        look.refresh_from_db()
        self.assertEqual(look.result["render_image"]["s3_key"], "k.jpg")
