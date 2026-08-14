"""OpenAI 판단과 결정적 추천 파이프라인을 연결하는 채팅 오케스트레이터."""

from __future__ import annotations

import logging
import time
from copy import deepcopy
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.chat.models import (
    ChatAttachment,
    ChatIdentity,
    ChatMessage,
    ChatRun,
    ChatRunPersona,
    ChatSession,
)
from apps.chat.services import mood_analysis
from apps.chat.services.context import ChatContextService, fingerprint
from apps.chat.services.openai_adapter import (
    ChatLLMError,
    LLMUsage,
    OpenAIChatAdapter,
    TurnAnalysis,
)
from apps.chat.services.recommendation_pipeline import (
    ChatRecommendationError,
    ChatRecommendationPipeline,
)
from apps.chat.services.sessions import ChatSessionForbidden, append_message
from apps.chat.services.stylist_personas import load_stylist_personas

logger = logging.getLogger(__name__)


class ChatOrchestrationError(RuntimeError):
    code = "CHAT_RECOMMENDATION_FAILED"


class ChatRunAlreadyProcessing(ChatOrchestrationError):
    code = "CHAT_RUN_ALREADY_PROCESSING"


class ChatRunInvalid(ChatOrchestrationError):
    code = "CHAT_RUN_INVALID"


class ChatQueueUnavailable(ChatOrchestrationError):
    code = "CHAT_QUEUE_UNAVAILABLE"


@dataclass(frozen=True)
class OrchestrationResult:
    run: ChatRun
    response_message: ChatMessage
    recommendation_result_id: str | None = None


def _session_run_snapshot(session: ChatSession) -> dict[str, object]:
    persona_ids = list(session.selected_persona_ids)
    catalog = load_stylist_personas()
    try:
        session.full_clean()
        persona_versions = catalog.versions(persona_ids)
    except (ValidationError, ValueError) as exc:
        raise ChatRunInvalid("세션의 스타일리스트 선택 상태가 올바르지 않습니다.") from exc
    return {
        "response_mode": session.response_mode,
        "persona_ids": persona_ids,
        "persona_versions": persona_versions,
        "persona_prompt_versions": {
            persona_id: catalog.get(persona_id).prompt_version
            for persona_id in persona_ids
        },
        "stylist_config_version": catalog.schema_version,
    }


def _strategy_snapshot(persona) -> dict[str, object]:
    profile = persona.strategy_profile
    return {
        "objectives": list(profile.objectives),
        "search_directives": list(profile.search_directives),
        "score_weights": [
            {"metric": row.metric, "weight": row.weight}
            for row in profile.score_weights
        ],
        "hypothesis_count": profile.hypothesis_count,
    }


def _create_persona_executions(run: ChatRun) -> None:
    if run.response_mode != ChatSession.ResponseMode.STYLIST:
        return

    catalog = load_stylist_personas()
    rows = []
    for persona_id in run.persona_ids:
        persona = catalog.get(persona_id)
        rows.append(
            ChatRunPersona(
                run=run,
                persona_id=persona_id,
                persona_version=run.persona_versions[persona_id],
                prompt_version=run.persona_prompt_versions[persona_id],
                display_order=persona.display_order,
                strategy_snapshot=_strategy_snapshot(persona),
            )
        )
    ChatRunPersona.objects.bulk_create(rows)


@transaction.atomic
def submit_message_and_create_run(
    *,
    identity: ChatIdentity,
    session_id,
    content: str,
    client_message_id: str,
    metadata: dict | None = None,
) -> tuple[ChatMessage, bool, ChatRun, bool]:
    """메시지와 실행 스냅샷을 한 트랜잭션에서 멱등 생성한다."""

    message, message_created = append_message(
        identity=identity,
        session_id=session_id,
        role=ChatMessage.Role.USER,
        content=content,
        status=ChatMessage.Status.PENDING,
        client_message_id=client_message_id,
        metadata=metadata,
    )
    run, run_created = create_run(
        identity=identity,
        session_id=session_id,
        request_message_id=message.id,
    )
    return message, message_created, run, run_created


@transaction.atomic
def create_run(
    *,
    identity: ChatIdentity,
    session_id,
    request_message_id,
) -> tuple[ChatRun, bool]:
    """사용자 메시지당 실행을 하나만 만들고 큐 재전송을 멱등 처리한다."""
    session = (
        ChatSession.objects.select_for_update()
        .filter(
            pk=session_id,
            identity=identity,
            deleted_at__isnull=True,
        )
        .first()
    )
    if session is None:
        raise ChatSessionForbidden("채팅 세션에 접근할 수 없습니다.")
    message = (
        ChatMessage.objects.select_for_update()
        .filter(
            pk=request_message_id,
            session=session,
        )
        .first()
    )
    if message is None:
        raise ChatSessionForbidden("채팅 메시지에 접근할 수 없습니다.")
    if message.role != ChatMessage.Role.USER:
        raise ChatRunInvalid("사용자 메시지만 채팅 실행을 시작할 수 있습니다.")

    existing = ChatRun.objects.filter(request_message=message).first()
    if existing is not None:
        return existing, False

    snapshot = _session_run_snapshot(session)

    try:
        run, created = ChatRun.objects.get_or_create(
            request_message=message,
            defaults={
                "session": session,
                "status": ChatRun.Status.PENDING,
                "provider": OpenAIChatAdapter.provider,
                "model": settings.CHAT_OPENAI_MODEL,
                "prompt_version": settings.CHAT_PROMPT_VERSION,
                **snapshot,
            },
        )
    except IntegrityError:
        run = ChatRun.objects.get(request_message=message)
        created = False
    if created:
        _create_persona_executions(run)
    if created and message.status != ChatMessage.Status.PENDING:
        message.status = ChatMessage.Status.PENDING
        message.save(update_fields=["status", "updated_at"])
    return run, created


@transaction.atomic
def mark_enqueue_failed(run_id) -> ChatRun | None:
    """DB 접수 후 Redis 적재에 실패한 실행을 무한 대기 대신 실패로 종료한다."""
    run = ChatRun.objects.select_for_update().filter(pk=run_id).first()
    if run is None or run.status != ChatRun.Status.PENDING:
        return run
    now = timezone.now()
    run.status = ChatRun.Status.FAILED
    run.error_code = ChatQueueUnavailable.code
    run.error_message = "채팅 실행 큐에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
    run.completed_at = now
    run.save(
        update_fields=[
            "status",
            "error_code",
            "error_message",
            "completed_at",
            "updated_at",
        ]
    )
    ChatMessage.objects.filter(pk=run.request_message_id).update(
        status=ChatMessage.Status.FAILED,
        updated_at=now,
    )
    ChatAttachment.objects.filter(message_id=run.request_message_id).exclude(
        analysis_status=ChatAttachment.AnalysisStatus.SUCCEEDED
    ).update(analysis_status=ChatAttachment.AnalysisStatus.FAILED)
    return run


@transaction.atomic
def reset_run_for_retry(run_id) -> bool:
    """단일 워커가 실패·중단된 실행을 같은 ID로 안전하게 재시도하게 만든다."""
    run = ChatRun.objects.select_for_update().filter(pk=run_id).first()
    if run is None or run.status not in {ChatRun.Status.RUNNING, ChatRun.Status.FAILED}:
        return False
    if run.response_message_id is not None:
        return False
    now = timezone.now()
    run.status = ChatRun.Status.PENDING
    run.context_fingerprint = ""
    run.context_cache_hit = False
    run.provider_response_id = ""
    run.input_tokens = 0
    run.cached_input_tokens = 0
    run.output_tokens = 0
    run.latency_ms = 0
    run.error_code = ""
    run.error_message = ""
    run.started_at = None
    run.completed_at = None
    run.save(
        update_fields=[
            "status",
            "context_fingerprint",
            "context_cache_hit",
            "provider_response_id",
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "latency_ms",
            "error_code",
            "error_message",
            "started_at",
            "completed_at",
            "updated_at",
        ]
    )
    ChatMessage.objects.filter(pk=run.request_message_id).update(
        status=ChatMessage.Status.PENDING,
        updated_at=now,
    )
    ChatAttachment.objects.filter(
        message_id=run.request_message_id,
        analysis_status__in={
            ChatAttachment.AnalysisStatus.PROCESSING,
            ChatAttachment.AnalysisStatus.FAILED,
        },
    ).update(analysis_status=ChatAttachment.AnalysisStatus.QUEUED)
    return True


class ChatOrchestrator:
    """Redis 큐 워커가 실행 ID로 호출하는 동기 오케스트레이션 코어."""

    def __init__(
        self,
        *,
        context_service: ChatContextService | None = None,
        llm: OpenAIChatAdapter | None = None,
        recommendation_pipeline: ChatRecommendationPipeline | None = None,
    ) -> None:
        self.context_service = context_service or ChatContextService()
        self.llm = llm or OpenAIChatAdapter()
        self.recommendation_pipeline = (
            recommendation_pipeline or ChatRecommendationPipeline()
        )

    def process(self, run_id) -> OrchestrationResult:
        started = time.monotonic()
        run = self._start(run_id)
        usage = LLMUsage()
        provider_response_id = ""
        context_fingerprint = ""
        context_cache_hit = False
        attachment = run.request_message.attachments.first()
        try:
            if attachment is not None:
                return self._process_photo_mood(
                    run=run,
                    attachment=attachment,
                    started=started,
                )
            context = self.context_service.build(
                session=run.session,
                request_message=run.request_message,
            )
            context_fingerprint = context.fingerprint
            context_cache_hit = context.cache_hit
            analyzed = self.llm.analyze_turn(
                identity_id=str(run.session.identity_id),
                context=context.payload,
            )
            usage += analyzed.usage
            provider_response_id = analyzed.response_id
            analysis = self._effective_analysis(run.session, analyzed.value)
            self._update_session_conditions(run.session, analysis)
            context_fingerprint = fingerprint(
                {
                    "initial": context.fingerprint,
                    "extracted_conditions": analysis.conditions.model_dump(),
                    "action": analysis.action,
                    "target_mode": analysis.target_mode,
                }
            )

            recommendation_result_id = None
            final_status = ChatRun.Status.SUCCEEDED
            response_text: str
            response_metadata: dict = {"run_id": str(run.id)}

            if self._requests_mode_change(run.session.mode, analysis):
                final_status = ChatRun.Status.NEEDS_CLARIFICATION
                response_text = (
                    analysis.response_text.strip()
                    or "추천 모드를 바꾸려면 현재 조건을 이어받은 새 채팅을 만들어 주세요."
                )
                response_metadata["target_mode"] = analysis.target_mode
            elif analysis.action == "CLARIFY":
                final_status = ChatRun.Status.NEEDS_CLARIFICATION
                response_text = (
                    analysis.clarification_question.strip()
                    or "추천에 필요한 상황이나 조건을 조금 더 알려주세요."
                )
            elif analysis.action == "RESPOND":
                response_text = (
                    analysis.response_text.strip()
                    or "패션 추천과 관련해 궁금한 조건을 알려주세요."
                )
            else:
                pipeline_result = self.recommendation_pipeline.execute(
                    run=run,
                    context=context.payload,
                    analysis=analysis,
                )
                explained = self.llm.explain_recommendation(
                    identity_id=str(run.session.identity_id),
                    persona=context.payload["persona"],
                    mode=run.session.mode,
                    approved_recommendation=pipeline_result.approved_payload,
                )
                usage += explained.usage
                provider_response_id = explained.response_id
                response_text = explained.value.message.strip()
                recommendation_result_id = str(pipeline_result.result.id)
                response_metadata["recommendation_result_id"] = recommendation_result_id

            response_message, _ = append_message(
                identity=run.session.identity,
                session_id=run.session_id,
                role=ChatMessage.Role.ASSISTANT,
                content=response_text,
                status=ChatMessage.Status.COMPLETED,
                client_message_id=f"run:{run.pk}:response",
                metadata=response_metadata,
            )
            summary_usage = self._maybe_refresh_summary(run.session)
            usage += summary_usage
            duration_ms = int((time.monotonic() - started) * 1000)
            self._finish(
                run=run,
                status=final_status,
                response_message=response_message,
                context_fingerprint=context_fingerprint,
                context_cache_hit=context_cache_hit,
                usage=usage,
                provider_response_id=provider_response_id,
                latency_ms=duration_ms,
            )
            run.refresh_from_db()
            logger.info(
                "채팅 실행 완료: run=%s status=%s latency=%sms cache_hit=%s",
                run.pk,
                run.status,
                duration_ms,
                context_cache_hit,
                extra={
                    "run_id": str(run.pk),
                    "session_id": str(run.session_id),
                    "result_id": recommendation_result_id,
                    "status": run.status,
                    "duration_ms": duration_ms,
                    "cache_hit": context_cache_hit,
                },
            )
            return OrchestrationResult(
                run=run,
                response_message=response_message,
                recommendation_result_id=recommendation_result_id,
            )
        except Exception as exc:
            if attachment is not None:
                mood_analysis.mark_analysis_failed(attachment.pk)
            duration_ms = int((time.monotonic() - started) * 1000)
            self._fail(
                run=run,
                exc=exc,
                usage=usage,
                provider_response_id=provider_response_id,
                latency_ms=duration_ms,
                context_fingerprint=context_fingerprint,
                context_cache_hit=context_cache_hit,
            )
            logger.error(
                "채팅 실행 종료 실패: run=%s code=%s latency=%sms",
                run.pk,
                getattr(exc, "code", type(exc).__name__),
                duration_ms,
                extra={
                    "run_id": str(run.pk),
                    "session_id": str(run.session_id),
                    "status": ChatRun.Status.FAILED,
                    "duration_ms": duration_ms,
                    "error_code": getattr(exc, "code", type(exc).__name__),
                },
            )
            raise

    def _process_photo_mood(
        self,
        *,
        run: ChatRun,
        attachment: ChatAttachment,
        started: float,
    ) -> OrchestrationResult:
        processed = mood_analysis.process_attachment(
            attachment=attachment,
            identity_id=str(run.session.identity_id),
            llm=self.llm,
        )
        tags = processed.analysis_result["tags"]
        response_text = (
            f"사진에서 {', '.join(tags)} 무드가 보여요. "
            "이 분위기를 추천 조건에 반영할까요?"
        )
        response_message, _ = append_message(
            identity=run.session.identity,
            session_id=run.session_id,
            role=ChatMessage.Role.ASSISTANT,
            content=response_text,
            status=ChatMessage.Status.COMPLETED,
            client_message_id=f"run:{run.pk}:response",
            metadata={
                "run_id": str(run.pk),
                "message_kind": "mood",
                "attachment_id": str(attachment.pk),
                "mood_analysis": processed.analysis_result,
            },
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        self._finish(
            run=run,
            status=ChatRun.Status.SUCCEEDED,
            response_message=response_message,
            context_fingerprint=fingerprint(
                {
                    "attachment_id": str(attachment.pk),
                    "sha256": attachment.sha256,
                    "analysis_result": processed.analysis_result,
                }
            ),
            context_cache_hit=False,
            usage=processed.usage,
            provider_response_id=processed.response_id,
            latency_ms=duration_ms,
        )
        run.refresh_from_db()
        logger.info(
            "채팅 사진 무드 분석 완료: run=%s attachment=%s latency=%sms",
            run.pk,
            attachment.pk,
            duration_ms,
        )
        return OrchestrationResult(
            run=run,
            response_message=response_message,
        )

    @staticmethod
    def _start(run_id) -> ChatRun:
        now = timezone.now()
        updated = ChatRun.objects.filter(
            pk=run_id,
            status=ChatRun.Status.PENDING,
        ).update(
            status=ChatRun.Status.RUNNING,
            started_at=now,
            completed_at=None,
            error_code="",
            error_message="",
            updated_at=now,
        )
        run = (
            ChatRun.objects.select_related(
                "session",
                "session__identity",
                "session__identity__user",
                "request_message",
            )
            .filter(pk=run_id)
            .first()
        )
        if run is None:
            raise ChatRunInvalid("채팅 실행을 찾을 수 없습니다.")
        if not updated:
            raise ChatRunAlreadyProcessing(
                f"현재 상태({run.status})에서는 실행을 시작할 수 없습니다."
            )
        ChatMessage.objects.filter(pk=run.request_message_id).update(
            status=ChatMessage.Status.PROCESSING,
            updated_at=now,
        )
        run.request_message.status = ChatMessage.Status.PROCESSING
        return run

    @staticmethod
    def _requests_mode_change(current_mode: str, analysis: TurnAnalysis) -> bool:
        return analysis.action == "MODE_CHANGE" or analysis.target_mode not in {
            "CURRENT",
            current_mode,
        }

    @staticmethod
    def _effective_analysis(
        session: ChatSession,
        analysis: TurnAnalysis,
    ) -> TurnAnalysis:
        """현재 발화에 없는 조건은 승인된 사진을 포함한 세션 조건에서 보충한다."""
        saved = dict(
            (session.context_state or {}).get("recommendation_conditions") or {}
        )
        conditions = analysis.conditions.model_dump()
        for key, value in conditions.items():
            if value in (None, "", []) and saved.get(key) not in (None, "", []):
                conditions[key] = saved[key]
        return analysis.model_copy(
            update={"conditions": analysis.conditions.model_copy(update=conditions)}
        )

    @staticmethod
    def _update_session_conditions(
        session: ChatSession,
        analysis: TurnAnalysis,
    ) -> None:
        state = deepcopy(session.context_state or {})
        current = dict(state.get("recommendation_conditions") or {})
        extracted = analysis.conditions.model_dump()
        for key, value in extracted.items():
            if value not in (None, "", []):
                current[key] = value
        state["recommendation_conditions"] = current
        session.context_state = state
        session.save(update_fields=["context_state", "updated_at"])

    def _maybe_refresh_summary(self, session: ChatSession) -> LLMUsage:
        session.refresh_from_db()
        last_sequence = (
            session.messages.order_by("-sequence")
            .values_list("sequence", flat=True)
            .first()
        )
        if not last_sequence or last_sequence < settings.CHAT_SUMMARY_TRIGGER_MESSAGES:
            return LLMUsage()
        through_sequence = max(
            0,
            last_sequence - settings.CHAT_CONTEXT_RECENT_MESSAGES,
        )
        if through_sequence <= session.summary_through_sequence:
            return LLMUsage()
        messages = list(
            session.messages.filter(
                sequence__gt=session.summary_through_sequence,
                sequence__lte=through_sequence,
            ).values("sequence", "role", "content")
        )
        if not messages:
            return LLMUsage()
        try:
            persona = session.persona_profile
            persona_payload = (
                {
                    "name": persona.name,
                    "version": persona.version,
                    "prompt_config": persona.prompt_config,
                }
                if persona is not None
                else {}
            )
            summarized = self.llm.summarize_conversation(
                identity_id=str(session.identity_id),
                persona=persona_payload,
                previous_summary=session.conversation_summary,
                messages=messages,
            )
        except ChatLLMError as exc:
            logger.warning("대화 요약 갱신 생략: %s", exc.code)
            return LLMUsage()
        session.conversation_summary = summarized.value.summary.strip()
        session.summary_through_sequence = through_sequence
        session.save(
            update_fields=[
                "conversation_summary",
                "summary_through_sequence",
                "updated_at",
            ]
        )
        return summarized.usage

    @staticmethod
    def _finish(
        *,
        run: ChatRun,
        status: str,
        response_message: ChatMessage,
        context_fingerprint: str,
        context_cache_hit: bool,
        usage: LLMUsage,
        provider_response_id: str,
        latency_ms: int,
    ) -> None:
        now = timezone.now()
        ChatRun.objects.filter(pk=run.pk).update(
            status=status,
            response_message=response_message,
            context_fingerprint=context_fingerprint,
            context_cache_hit=context_cache_hit,
            provider=OpenAIChatAdapter.provider,
            model=settings.CHAT_OPENAI_MODEL,
            prompt_version=settings.CHAT_PROMPT_VERSION,
            provider_response_id=provider_response_id,
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=max(latency_ms, 0),
            error_code="",
            error_message="",
            completed_at=now,
            updated_at=now,
        )
        ChatMessage.objects.filter(pk=run.request_message_id).update(
            status=ChatMessage.Status.COMPLETED,
            updated_at=now,
        )

    @staticmethod
    def _fail(
        *,
        run: ChatRun,
        exc: Exception,
        usage: LLMUsage,
        provider_response_id: str,
        latency_ms: int,
        context_fingerprint: str,
        context_cache_hit: bool,
    ) -> None:
        now = timezone.now()
        error_code = getattr(exc, "code", ChatOrchestrationError.code)
        if isinstance(
            exc,
            (
                ChatLLMError,
                ChatRecommendationError,
                ChatOrchestrationError,
                mood_analysis.ChatMoodError,
            ),
        ):
            safe_message = str(exc)[:500]
        else:
            safe_message = "채팅 추천 처리 중 내부 오류가 발생했습니다."
        ChatRun.objects.filter(pk=run.pk).update(
            status=ChatRun.Status.FAILED,
            context_fingerprint=context_fingerprint,
            context_cache_hit=context_cache_hit,
            provider_response_id=provider_response_id,
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=max(latency_ms, 0),
            error_code=error_code,
            error_message=safe_message,
            completed_at=now,
            updated_at=now,
        )
        ChatMessage.objects.filter(pk=run.request_message_id).update(
            status=ChatMessage.Status.FAILED,
            updated_at=now,
        )
        logger.warning(
            "채팅 실행 실패: code=%s type=%s", error_code, type(exc).__name__
        )
