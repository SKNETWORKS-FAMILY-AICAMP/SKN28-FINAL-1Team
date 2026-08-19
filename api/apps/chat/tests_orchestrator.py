from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.chat.models import (
    ChatIdentity,
    ChatMessage,
    ChatRun,
    ChatSession,
    PersonaProfile,
)
from apps.chat.services.context import ChatContext, ChatContextService
from apps.chat.services.openai_adapter import (
    ChatLLMError,
    LLMResult,
    LLMUsage,
    OpenAIChatAdapter,
    RecommendationConditions,
    RecommendationExplanation,
    TurnAnalysis,
)
from apps.chat.services.orchestrator import (
    ChatOrchestrator,
    ChatRunAlreadyProcessing,
    create_run,
)
from apps.chat.services.recommendation_pipeline import (
    ChatRecommendationPipeline,
    OutfitCompositionFailed,
    RecommendationPipelineResult,
)
from apps.recommend.models import (
    OutfitComposition as OutfitCompositionModel,
)
from apps.recommend.models import (
    RecommendationFeedback,
    RecommendationResult,
)
from apps.recommend.services.item_retriever import ItemSource
from apps.recommend.services.outfit_types import (
    CompositionBatch,
    OutfitComposition,
    OutfitItem,
    RecommendationMode,
)
from apps.recommend.services.retriever import (
    OutfitCandidate,
    Reason,
    RetrievalResult,
)
from apps.recommend.services.validator import OutfitValidationResult
from apps.style_calendar.contracts import CalendarSourceType, CalendarStatus
from apps.style_calendar.models import CalendarEntry, CalendarWardrobeItem
from apps.users.models import Pursuit
from apps.wardrobe.models import WardrobeItem

User = get_user_model()


class MemoryJsonCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl_seconds):
        self.values[key] = value
        return True


def analysis(
    *,
    action="CLARIFY",
    target_mode="CURRENT",
    response_text="",
    clarification_question="어떤 상황에서 입을 옷인가요?",
    presentation_groups=None,
):
    return TurnAnalysis(
        action=action,
        target_mode=target_mode,
        search_query="가을 출근 미니멀 코디",
        conditions=RecommendationConditions(
            occasion="출근",
            season="가을",
            presentation_groups=list(presentation_groups or []),
            styles=["미니멀"],
            colors=[],
            fits=[],
            avoided_styles=[],
            avoided_colors=["빨강"],
            excluded_source_ids=[],
            budget=None,
        ),
        clarification_question=clarification_question,
        response_text=response_text,
    )


class ChatContextServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="context-user")
        self.identity = ChatIdentity.objects.create(
            user=self.user,
            identity_type=ChatIdentity.IdentityType.MEMBER,
        )
        self.session = ChatSession.objects.create(
            identity=self.identity,
            mode=ChatSession.Mode.NEW_ITEM,
        )
        self.message = ChatMessage.objects.create(
            session=self.session,
            sequence=1,
            role=ChatMessage.Role.USER,
            content="  가을   출근룩 추천해줘 ",
            metadata={"location": {"lat": 37.5665, "lon": 126.978}},
        )
        self.run = ChatRun.objects.create(
            session=self.session,
            request_message=self.message,
        )
        Pursuit.objects.create(
            user=self.user,
            payload={"preferred": {"styles": ["minimal"]}, "avoided": {}},
        )

    @patch("apps.chat.services.context.get_current_weather")
    def test_same_versions_reuse_base_context_and_request_is_normalized(
        self, mock_weather
    ):
        mock_weather.return_value = {
            "region": "서울",
            "temperature": 20,
            "sky_state": "맑음",
            "is_stale": False,
            "observed_at": "2026-08-11T09:00:00+09:00",
        }
        service = ChatContextService(cache=MemoryJsonCache())

        first = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )
        second = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )

        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(first.base_fingerprint, second.base_fingerprint)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.payload["profile"], second.payload["profile"])
        self.assertEqual(
            first.payload["profile"]["category_budgets"]["상의"],
            50_000,
        )

    @patch("apps.chat.services.context.get_current_weather")
    def test_profile_update_changes_base_fingerprint(self, mock_weather):
        mock_weather.return_value = {
            "region": "서울",
            "temperature": 20,
            "sky_state": "맑음",
            "is_stale": False,
            "observed_at": "2026-08-11T09:00:00+09:00",
        }
        service = ChatContextService(cache=MemoryJsonCache())
        first = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )
        pursuit = Pursuit.objects.get(user=self.user)
        pursuit.payload = {
            "preferred": {"styles": ["casual"]},
            "avoided": {},
        }
        pursuit.save()

        second = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )

        self.assertFalse(second.cache_hit)
        self.assertNotEqual(first.base_fingerprint, second.base_fingerprint)

    @patch("apps.chat.services.context.load_user_behavior_signals")
    @patch("apps.chat.services.context.get_current_weather")
    def test_member_behavior_signals_are_loaded_once_into_common_context(
        self,
        mock_weather,
        mock_behavior_signals,
    ):
        mock_weather.return_value = {
            "region": "서울",
            "observed_at": "2026-08-15T09:00:00+09:00",
            "is_stale": False,
        }
        behavior_payload = {
            "schema_version": "1.0",
            "signals": {"strong_preferences": {"worn_items": []}},
        }
        mock_behavior_signals.return_value = behavior_payload

        context = ChatContextService(cache=MemoryJsonCache()).build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )

        mock_behavior_signals.assert_called_once_with(
            identity=self.identity,
            current_run=self.run,
            as_of=timezone.localdate(),
        )
        self.assertEqual(context.payload["behavior_signals"], behavior_payload)

    @patch("apps.chat.services.context.load_user_behavior_signals")
    @patch("apps.chat.services.context.get_current_weather")
    def test_guest_context_skips_member_behavior_loaders(
        self,
        mock_weather,
        mock_behavior_signals,
    ):
        mock_weather.return_value = {
            "region": "서울",
            "observed_at": "2026-08-15T09:00:00+09:00",
            "is_stale": False,
        }
        guest_identity = ChatIdentity.objects.create(
            identity_type=ChatIdentity.IdentityType.GUEST,
            guest_token_hash="c" * 64,
            expires_at="2099-01-01T00:00:00Z",
        )
        guest_session = ChatSession.objects.create(
            identity=guest_identity,
            mode=ChatSession.Mode.NEW_ITEM,
        )
        guest_message = ChatMessage.objects.create(
            session=guest_session,
            sequence=1,
            role=ChatMessage.Role.USER,
            content="추천해줘",
        )
        guest_run = ChatRun.objects.create(
            session=guest_session,
            request_message=guest_message,
        )

        context = ChatContextService(cache=MemoryJsonCache()).build(
            session=guest_session,
            request_message=guest_message,
            current_run=guest_run,
        )

        mock_behavior_signals.assert_not_called()
        self.assertIsNone(context.payload["behavior_signals"])

    @patch("apps.chat.services.context.load_user_behavior_signals")
    @patch("apps.chat.services.context.get_current_weather")
    def test_personalization_updates_invalidate_base_context_cache(
        self,
        mock_weather,
        mock_behavior_signals,
    ):
        mock_weather.return_value = {
            "region": "서울",
            "observed_at": "2026-08-15T09:00:00+09:00",
            "is_stale": False,
        }
        mock_behavior_signals.return_value = {
            "schema_version": "1.0",
            "signals": {},
        }
        service = ChatContextService(cache=MemoryJsonCache())

        initial = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )
        wardrobe_item = WardrobeItem.objects.create(
            user=self.user,
            job=None,
            s3_key="wardrobe/context/top.png",
            item_name="컨텍스트 상의",
            category_large="상의",
            confirmed=True,
            added_to_closet_at=timezone.now(),
        )
        after_wardrobe = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )

        calendar = CalendarEntry.objects.create(
            user=self.user,
            date=timezone.localdate(),
            source_type=CalendarSourceType.WARDROBE_SELECTED.value,
            image_s3_key="calendar/context/today.jpg",
            status=CalendarStatus.COMPLETED.value,
        )
        CalendarWardrobeItem.objects.create(
            calendar=calendar,
            wardrobe_item=wardrobe_item,
        )
        after_calendar = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )

        previous_session = ChatSession.objects.create(
            identity=self.identity,
            mode=ChatSession.Mode.NEW_ITEM,
        )
        previous_message = ChatMessage.objects.create(
            session=previous_session,
            sequence=1,
            role=ChatMessage.Role.USER,
            content="이전 추천",
        )
        previous_run = ChatRun.objects.create(
            session=previous_session,
            request_message=previous_message,
            status=ChatRun.Status.SUCCEEDED,
        )
        previous_result = RecommendationResult.objects.create(
            identity=self.identity,
            session=previous_session,
            run=previous_run,
            mode=RecommendationResult.Mode.NEW_ITEM,
            dataset_version="context-test-v1",
        )
        previous_card = OutfitCompositionModel.objects.create(
            result=previous_result,
            rank=1,
            status=OutfitCompositionModel.Status.VALIDATED,
            composition_fingerprint="d" * 64,
            validation_reasons=[],
            warnings=[],
        )
        after_recommendation = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )

        RecommendationFeedback.objects.create(
            composition=previous_card,
            reaction=RecommendationFeedback.Reaction.LIKE,
            reason_codes=["STYLE"],
        )
        after_feedback = service.build(
            session=self.session,
            request_message=self.message,
            current_run=self.run,
        )

        fingerprints = [
            initial.base_fingerprint,
            after_wardrobe.base_fingerprint,
            after_calendar.base_fingerprint,
            after_recommendation.base_fingerprint,
            after_feedback.base_fingerprint,
        ]
        self.assertEqual(len(set(fingerprints)), len(fingerprints))
        self.assertTrue(
            all(
                not context.cache_hit
                for context in (
                    after_wardrobe,
                    after_calendar,
                    after_recommendation,
                    after_feedback,
                )
            )
        )


@override_settings(
    CHAT_OPENAI_MODEL="gpt-4o-mini",
    CHAT_PROMPT_VERSION="test-prompt-v1",
    CHAT_OPENAI_MAX_OUTPUT_TOKENS=500,
)
class OpenAIChatAdapterTests(SimpleTestCase):
    def test_responses_parse_uses_structured_output_without_remote_storage(self):
        parsed = analysis(action="RESPOND", response_text="조건을 알려주세요.")
        response = SimpleNamespace(
            id="resp-test",
            output_parsed=parsed,
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=30,
                input_tokens_details=SimpleNamespace(cached_tokens=80),
            ),
        )
        client = Mock()
        client.responses.parse.return_value = response
        adapter = OpenAIChatAdapter(client=client)

        result = adapter.analyze_turn(
            identity_id="internal-identity-id",
            context={
                "session": {
                    "mode": "NEW_ITEM",
                    "conversation_summary": "",
                    "conditions": {},
                },
                "persona": {},
                "profile": {},
                "weather": {},
                "recent_messages": [],
                "current_request": "추천해줘",
            },
        )

        kwargs = client.responses.parse.call_args.kwargs
        self.assertIs(kwargs["text_format"], TurnAnalysis)
        self.assertFalse(kwargs["store"])
        self.assertNotEqual(kwargs["safety_identifier"], "internal-identity-id")
        self.assertIn("test-prompt-v1", kwargs["prompt_cache_key"])
        self.assertEqual(result.usage.cached_input_tokens, 80)


@override_settings(CHAT_SUMMARY_TRIGGER_MESSAGES=100)
class ChatOrchestratorTests(TestCase):
    def setUp(self):
        self.identity = ChatIdentity.objects.create(
            identity_type=ChatIdentity.IdentityType.GUEST,
            guest_token_hash="f" * 64,
            expires_at="2099-01-01T00:00:00Z",
        )
        self.session = ChatSession.objects.create(
            identity=self.identity,
            mode=ChatSession.Mode.NEW_ITEM,
        )
        self.message = ChatMessage.objects.create(
            session=self.session,
            sequence=1,
            role=ChatMessage.Role.USER,
            content="출근룩 추천해줘",
        )
        self.run, _ = create_run(
            identity=self.identity,
            session_id=self.session.id,
            request_message_id=self.message.id,
        )
        self.context_service = Mock()
        self.context_service.build.return_value = ChatContext(
            payload={
                "session": {
                    "mode": self.session.mode,
                    "conditions": {},
                    "conversation_summary": "",
                },
                "persona": {},
                "profile": {},
                "weather": {},
                "recent_messages": [],
                "current_request": self.message.content,
            },
            fingerprint="a" * 64,
            base_fingerprint="b" * 64,
            cache_hit=True,
        )
        self.llm = Mock()
        self.pipeline = Mock()

    def test_create_run_is_idempotent(self):
        duplicate, created = create_run(
            identity=self.identity,
            session_id=self.session.id,
            request_message_id=self.message.id,
        )

        self.assertFalse(created)
        self.assertEqual(duplicate.id, self.run.id)

    def test_clarification_finishes_run_without_recommendation(self):
        self.llm.analyze_turn.return_value = LLMResult(
            value=analysis(),
            response_id="resp-analysis",
            usage=LLMUsage(input_tokens=100, cached_input_tokens=50, output_tokens=20),
        )
        orchestrator = ChatOrchestrator(
            context_service=self.context_service,
            llm=self.llm,
            recommendation_pipeline=self.pipeline,
        )

        result = orchestrator.process(self.run.id)

        self.assertEqual(result.run.status, ChatRun.Status.NEEDS_CLARIFICATION)
        self.assertEqual(result.response_message.role, ChatMessage.Role.ASSISTANT)
        self.assertIn("어떤 상황", result.response_message.content)
        self.assertTrue(result.run.context_cache_hit)
        self.assertEqual(result.run.cached_input_tokens, 50)
        self.assertEqual(
            self.context_service.build.call_args.kwargs["current_run"].id,
            self.run.id,
        )
        self.pipeline.execute.assert_not_called()
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, ChatMessage.Status.COMPLETED)

        with self.assertRaises(ChatRunAlreadyProcessing):
            orchestrator.process(self.run.id)

    def test_recommendation_uses_only_pipeline_approved_payload_for_explanation(self):
        self.llm.analyze_turn.return_value = LLMResult(
            value=analysis(action="RECOMMEND"),
            response_id="resp-analysis",
            usage=LLMUsage(input_tokens=100, output_tokens=20),
        )
        recommendation = RecommendationResult.objects.create(
            identity=self.identity,
            session=self.session,
            run=self.run,
            mode=self.session.mode,
            dataset_version="v1",
        )
        approved = {
            "result_id": str(recommendation.id),
            "mode": self.session.mode,
            "compositions": [],
        }
        self.pipeline.execute.return_value = RecommendationPipelineResult(
            result=recommendation,
            approved_payload=approved,
        )
        self.llm.explain_recommendation.return_value = LLMResult(
            value=RecommendationExplanation(
                message="### 추천 룩\n- **검증된 출근 코디**예요."
            ),
            response_id="resp-explanation",
            usage=LLMUsage(input_tokens=80, output_tokens=15),
        )
        orchestrator = ChatOrchestrator(
            context_service=self.context_service,
            llm=self.llm,
            recommendation_pipeline=self.pipeline,
        )

        result = orchestrator.process(self.run.id)

        self.assertEqual(result.run.status, ChatRun.Status.SUCCEEDED)
        self.assertEqual(result.recommendation_result_id, str(recommendation.id))
        self.assertEqual(result.run.input_tokens, 180)
        self.assertEqual(result.run.output_tokens, 35)
        self.assertEqual(
            result.response_message.content,
            "추천 룩\n검증된 출근 코디예요.",
        )
        self.assertEqual(
            self.llm.explain_recommendation.call_args.kwargs["approved_recommendation"],
            approved,
        )

    def test_llm_failure_marks_run_and_request_message_failed(self):
        self.llm.analyze_turn.side_effect = ChatLLMError("provider unavailable")
        orchestrator = ChatOrchestrator(
            context_service=self.context_service,
            llm=self.llm,
            recommendation_pipeline=self.pipeline,
        )

        with self.assertRaises(ChatLLMError):
            orchestrator.process(self.run.id)

        self.run.refresh_from_db()
        self.message.refresh_from_db()
        self.assertEqual(self.run.status, ChatRun.Status.FAILED)
        self.assertEqual(self.run.error_code, "CHAT_LLM_UNAVAILABLE")
        self.assertEqual(self.message.status, ChatMessage.Status.FAILED)


class PersonaProfileConstraintTests(TestCase):
    def test_only_one_default_persona_can_be_active(self):
        PersonaProfile.objects.filter(is_active=True).update(is_active=False)
        PersonaProfile.objects.create(
            code="minimal",
            name="미니멀",
            is_active=True,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PersonaProfile.objects.create(
                code="practical",
                name="실용",
                is_active=True,
            )


class ChatRecommendationPipelineTests(TestCase):
    def _run(self, *, member: bool, mode: str):
        if member:
            user = User.objects.create_user(username=f"pipeline-{mode}")
            identity = ChatIdentity.objects.create(
                user=user,
                identity_type=ChatIdentity.IdentityType.MEMBER,
            )
        else:
            identity = ChatIdentity.objects.create(
                identity_type=ChatIdentity.IdentityType.GUEST,
                guest_token_hash="e" * 64,
                expires_at="2099-01-01T00:00:00Z",
            )
        session = ChatSession.objects.create(identity=identity, mode=mode)
        message = ChatMessage.objects.create(
            session=session,
            sequence=1,
            role=ChatMessage.Role.USER,
            content="추천해줘",
        )
        return ChatRun.objects.create(session=session, request_message=message)

    @staticmethod
    def _context():
        return {
            "profile": {"pursuit": None},
            "weather": {"temperature": 20},
            "current_request": "가을 출근룩 추천해줘",
        }

    def test_guest_new_item_mode_searches_products_and_persists_validated_result(self):
        run = self._run(member=False, mode=ChatSession.Mode.NEW_ITEM)
        candidate = OutfitCandidate(
            point_id="outfit-1",
            golden_id="golden-1",
            score=91.0,
            similarity=0.91,
            reasons=(Reason("preference", 8.0, "미니멀 일치"),),
            payload={
                "item_point_ids": ["template-top"],
                "dataset_version": "v1",
            },
        )
        golden = Mock()
        golden.retrieve.return_value = RetrievalResult(
            candidates=(candidate,),
            search_mode="text",
        )
        item_retriever = Mock()
        item_retriever.retrieve.return_value = object()
        product = OutfitItem(
            slot_id="TOP",
            template_point_id="template-top",
            category_large="상의",
            layer_role="top",
            source_type=ItemSource.PRODUCT,
            source_id="product-1",
            source_collection="products_naver_v1",
            point_id="product-point-1",
            image_ref="https://example.com/top.jpg",
            price=49_000,
            score=0.9,
            reasons=("골든 아이템과 유사",),
            payload={"title": "미니멀 셔츠", "price": 49_000},
        )
        composition = OutfitComposition(
            mode=RecommendationMode.NEW_ITEM,
            items=(product,),
            missing_slot_ids=(),
            total_product_price=49_000,
        )
        new_item_composer = Mock()
        new_item_composer.compose.return_value = CompositionBatch(
            mode=RecommendationMode.NEW_ITEM,
            compositions=(composition,),
        )
        validator = Mock()
        validator.validate.return_value = OutfitValidationResult(
            issues=(),
            effective_total_product_price=49_000,
        )
        pipeline = ChatRecommendationPipeline(
            golden_retriever=golden,
            item_retriever=item_retriever,
            wardrobe_composer=Mock(),
            new_item_composer=new_item_composer,
            validator=validator,
        )

        output = pipeline.execute(
            run=run,
            context=self._context(),
            analysis=analysis(action="RECOMMEND"),
        )

        request = item_retriever.retrieve.call_args.args[0]
        self.assertEqual(request.sources, (ItemSource.PRODUCT,))
        golden_request = golden.retrieve.call_args.args[0]
        self.assertEqual(golden_request.season, "가을")
        self.assertFalse(golden_request.exposable_only)
        self.assertEqual(output.result.run, run)
        saved_item = output.result.compositions.get().items.get()
        self.assertEqual(saved_item.source_type, "PRODUCT")
        self.assertEqual(saved_item.price_snapshot, 49_000)
        self.assertEqual(
            output.approved_payload["compositions"][0]["items"][0]["name"],
            "미니멀 셔츠",
        )

    def test_explicit_presentation_group_is_separate_from_profile_gender(self):
        context = self._context()
        context["profile"]["body"] = {"gender": "female"}

        explicit = ChatRecommendationPipeline._presentation_groups(
            context=context,
            analysis=analysis(presentation_groups=["man"]),
        )
        profile_default = ChatRecommendationPipeline._presentation_groups(
            context=context,
            analysis=analysis(),
        )

        self.assertEqual(explicit, ("men",))
        self.assertEqual(profile_default, ())
        self.assertEqual(ChatRecommendationPipeline._gender(context), "female")

    def test_turn_fit_condition_is_merged_into_retriever_preferences(self):
        turn = analysis()
        turn.conditions.fits = ["레귤러핏"]

        pursuit = ChatRecommendationPipeline._merged_pursuit(self._context(), turn)

        self.assertEqual(pursuit["preferred"]["fits"], ["레귤러핏"])

    def test_guest_cannot_run_wardrobe_mode_without_member_wardrobe(self):
        run = self._run(member=False, mode=ChatSession.Mode.WARDROBE_BASED)
        pipeline = ChatRecommendationPipeline(
            golden_retriever=Mock(),
            item_retriever=Mock(),
            wardrobe_composer=Mock(),
            new_item_composer=Mock(),
            validator=Mock(),
        )

        with self.assertRaises(OutfitCompositionFailed):
            pipeline.execute(
                run=run,
                context=self._context(),
                analysis=analysis(action="RECOMMEND"),
            )
