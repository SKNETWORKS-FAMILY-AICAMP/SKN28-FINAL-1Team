"""오케스트레이터가 기존 Retriever·Composer·Validator를 호출하는 경계."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from apps.chat.models import ChatRun, ChatRunPersona, ChatSession
from apps.chat.services.openai_adapter import TurnAnalysis
from apps.chat.services.stylist_strategy import (
    PreferencePolarity,
    StrategyPlan,
)
from apps.recommend.models import (
    GoldenTemplateSnapshot,
    OutfitCompositionItem,
    RecommendationResult,
)
from apps.recommend.models import (
    OutfitComposition as OutfitCompositionModel,
)
from apps.recommend.services import render_jobs
from apps.recommend.services.body_profile import BodyProfile, build_profile
from apps.recommend.services.item_retriever import (
    ItemCandidateRetriever,
    ItemRetrievalRequest,
    ItemSource,
)
from apps.recommend.services.new_item_composer import (
    NewItemCompositionRequest,
    NewItemOutfitComposer,
)
from apps.recommend.services.outfit_types import (
    OutfitComposition as DomainOutfitComposition,
)
from apps.recommend.services.retriever import (
    GoldenOutfitRetriever,
    OutfitCandidate,
    RetrievalRequest,
    RetrievalResult,
    normalize_presentation_groups,
)
from apps.recommend.services.text_embedding import TextEmbeddingConfigurationError
from apps.recommend.services.validator import (
    OutfitValidationResult,
    OutfitValidator,
    ValidationContext,
)
from apps.recommend.services.wardrobe_composer import (
    WardrobeCompositionRequest,
    WardrobeOutfitComposer,
)
from apps.recommend.services.wardrobe_link import accessible_item_ids, owned_closet_item_ids


class ChatRecommendationError(RuntimeError):
    code = "CHAT_RECOMMENDATION_FAILED"


logger = logging.getLogger(__name__)


class GoldenOutfitNotFound(ChatRecommendationError):
    code = "GOLDEN_OUTFIT_NOT_FOUND"


class OutfitCompositionFailed(ChatRecommendationError):
    code = "OUTFIT_COMPOSITION_FAILED"


@dataclass(frozen=True)
class RecommendationPipelineResult:
    result: RecommendationResult
    approved_payload: dict[str, Any]


@dataclass(frozen=True)
class ValidatedRecommendationCandidate:
    """DB에 저장하기 전 Validator를 통과한 코디 한 건."""

    ordinal: int
    template_rank: int
    composition_rank: int
    golden: OutfitCandidate
    composition: DomainOutfitComposition
    validation: OutfitValidationResult


@dataclass(frozen=True)
class GeneratedRecommendationCandidates:
    """한 ChatRun 범위에서 생성된 저장 전 추천 후보 묶음."""

    run_id: str
    session_id: str
    identity_id: str
    response_mode: str
    mode: str
    search_mode: str
    candidates: tuple[ValidatedRecommendationCandidate, ...]


class ChatRecommendationPipeline:
    """LLM 판단 뒤 결정적 추천 컴포넌트만 순서대로 실행한다."""

    def __init__(
        self,
        *,
        golden_retriever: GoldenOutfitRetriever | None = None,
        item_retriever: ItemCandidateRetriever | None = None,
        wardrobe_composer: WardrobeOutfitComposer | None = None,
        new_item_composer: NewItemOutfitComposer | None = None,
        validator: OutfitValidator | None = None,
    ) -> None:
        self.golden_retriever = golden_retriever or GoldenOutfitRetriever()
        self.item_retriever = item_retriever or ItemCandidateRetriever()
        self.wardrobe_composer = wardrobe_composer or WardrobeOutfitComposer()
        self.new_item_composer = new_item_composer or NewItemOutfitComposer()
        self.validator = validator or OutfitValidator()

    def _retrieve_golden(self, request: RetrievalRequest) -> RetrievalResult:
        """골든 코디를 찾는다. 질의 임베딩을 못 쓰면 필터 검색으로 내려간다.

        채팅은 항상 질의문을 넘기므로 리트리버가 텍스트 검색 모드를 고르고, 그러려면 외부
        임베딩 서비스(TEXT_EMBEDDING_API_URL)가 있어야 한다. 그 설정이 비어 있으면
        TextEmbeddingConfigurationError 가 나는데, 이건 RuntimeError 라서 아래 후보 루프의
        `except (ValueError, RuntimeError)` 에도 걸리지 않고 그대로 run 을 죽인다.
        그러면 "채팅 추천 처리 중 내부 오류" 한 줄만 남고, 워커는 해결될 리 없는 요청을
        두 번 더 재시도한다.

        임베딩이 없어도 추천을 아예 못 하는 것은 아니다. query_text 를 비우면 리트리버가
        필터 검색으로 동작하고, 체형·추구미·성별·계절 조건은 그대로 살아 있다. 의미 검색이
        빠져 문장의 뉘앙스 반영은 약해지지만, 핵심 기능이 외부 서비스 하나 때문에 통째로
        멈추는 것보다는 낫다는 판단이다.

        ⚠️ 이건 바닥이지 대체가 아니다. 임베딩 서비스가 설정되면 이 경로는 자동으로 쓰이지
           않는다. 이 경로를 탔는지는 로그와 결과의 search_mode('filter')로 확인한다.
        ⚠️ 설정이 **없는** 경우만 내려간다. 서비스가 있는데 일시적으로 실패한 것이라면
           그대로 올려보내 재시도되게 둔다 — 잠깐의 장애 때문에 추천 품질을 낮추지 않는다.
        """
        try:
            return self.golden_retriever.retrieve(request)
        except TextEmbeddingConfigurationError:
            logger.warning(
                "질의 임베딩 설정이 없어 골든 코디를 필터 검색으로 찾는다 "
                "(TEXT_EMBEDDING_API_URL·TEXT_EMBEDDING_API_TOKEN 미설정)"
            )
            return self.golden_retriever.retrieve(replace(request, query_text=""))

    def execute(
        self,
        *,
        run: ChatRun,
        context: dict[str, Any],
        analysis: TurnAnalysis,
    ) -> RecommendationPipelineResult:
        """기본 응답의 기존 동작을 보존하는 생성·저장 호환 진입점."""

        if run.response_mode != ChatSession.ResponseMode.DEFAULT:
            raise OutfitCompositionFailed(
                "스타일리스트 응답은 후보를 생성한 뒤 개별 실행별로 저장해야 합니다."
            )
        existing = RecommendationResult.objects.filter(
            run=run,
            response_mode=RecommendationResult.ResponseMode.DEFAULT,
        ).first()
        if existing is not None:
            self._schedule_render_on_commit(run=run, result_id=existing.pk)
            return RecommendationPipelineResult(
                result=existing,
                approved_payload=self._approved_payload(existing),
            )

        generated = self.generate_candidates(
            run=run,
            context=context,
            analysis=analysis,
            # 기존 기본 추천은 첫 번째로 성공한 골든 템플릿의 조합만 저장했다.
            max_validated_templates=1,
        )
        return self.persist_candidates(
            run=run,
            generated=generated,
            selected=generated.candidates[:3],
        )

    def generate_candidates(
        self,
        *,
        run: ChatRun,
        context: dict[str, Any],
        analysis: TurnAnalysis,
        max_validated_templates: int | None = None,
        strategy_plan: StrategyPlan | None = None,
    ) -> GeneratedRecommendationCandidates:
        """Retriever·Composer·Validator를 실행하고 DB 저장 전 후보를 반환한다."""

        if max_validated_templates is not None and (
            isinstance(max_validated_templates, bool)
            or not isinstance(max_validated_templates, int)
            or max_validated_templates < 1
        ):
            raise ValueError("max_validated_templates는 1 이상의 정수여야 합니다.")

        session = run.session
        user_id = session.identity.user_id
        if session.mode == ChatSession.Mode.WARDROBE_BASED and user_id is None:
            raise OutfitCompositionFailed(
                "옷장 기반 추천은 회원의 확정된 옷장 아이템이 필요합니다."
            )
        scope_snapshot = run.wardrobe_scope_snapshot or {}
        scoped_item_ids = tuple(scope_snapshot.get("candidate_item_ids") or ())
        allowed_wardrobe_item_ids = (
            tuple(
                owned_closet_item_ids(session.identity.user)
                if scoped_item_ids
                else accessible_item_ids(session.identity.user)
            )
            if user_id is not None
            else None
        )

        pursuit = self._merged_pursuit(context, analysis)
        if strategy_plan is not None:
            pursuit = self._apply_strategy_preferences(pursuit, strategy_plan)
        candidate_limit = strategy_plan.candidate_limit if strategy_plan else 5
        body = build_profile(context.get("profile", {}).get("body"))
        retrieval = self._retrieve_golden(
            RetrievalRequest(
                body=body,
                pursuit=pursuit,
                weather=context.get("weather"),
                gender=self._gender(context),
                occasion=analysis.conditions.occasion,
                season=analysis.conditions.season,
                query_text=(
                    strategy_plan.search_query
                    if strategy_plan is not None
                    else analysis.search_query or context["current_request"]
                ),
                presentation_groups=self._presentation_groups(
                    context=context,
                    analysis=analysis,
                ),
                dataset_version=settings.CHAT_GOLDENSET_DATASET_VERSION,
                dataset_statuses=settings.CHAT_GOLDENSET_DATASET_STATUSES,
                limit=candidate_limit,
                hard_filter=True,
                # 골든 코디는 내부 조합 템플릿이다. 원본 이미지 노출 권한은
                # 결과 표출·렌더링 경계에서 별도로 검사한다.
                exposable_only=False,
            )
        )
        if not retrieval.candidates:
            raise GoldenOutfitNotFound("조건에 맞는 골든 코디를 찾지 못했습니다.")

        generated: list[ValidatedRecommendationCandidate] = []
        validated_template_count = 0
        for template_rank, candidate in enumerate(retrieval.candidates, start=1):
            template_ids = self._template_item_ids(candidate)
            if not template_ids:
                continue
            try:
                category_budgets = context.get("profile", {}).get(
                    "category_budgets", {}
                )
                def retrieve_slot(point_id):
                    request_kwargs = dict(
                            template_item_point_id=point_id,
                            sources=self._sources(session.mode, user_id),
                            user_id=user_id,
                            max_price=analysis.conditions.budget,
                            category_budgets=category_budgets,
                            dataset_version=settings.CHAT_GOLDENSET_DATASET_VERSION,
                            dataset_statuses=settings.CHAT_GOLDENSET_DATASET_STATUSES,
                            limit_per_source=10,
                    )
                    if scoped_item_ids and session.mode == ChatSession.Mode.WARDROBE_BASED:
                        scoped = self.item_retriever.retrieve(
                            ItemRetrievalRequest(
                                **request_kwargs,
                                allowed_wardrobe_item_ids=scoped_item_ids,
                            )
                        )
                        if scoped.candidates:
                            return scoped
                    return self.item_retriever.retrieve(
                        ItemRetrievalRequest(
                            **request_kwargs,
                            allowed_wardrobe_item_ids=allowed_wardrobe_item_ids,
                        )
                    )

                slot_results = tuple(retrieve_slot(point_id) for point_id in template_ids)
                batch = self._compose(
                    session.mode,
                    slot_results,
                    budget=analysis.conditions.budget,
                    category_budgets=category_budgets,
                )
            except (ValueError, RuntimeError):
                continue

            template_candidates: list[ValidatedRecommendationCandidate] = []
            for composition_rank, composition in enumerate(
                batch.compositions,
                start=1,
            ):
                if len(generated) + len(template_candidates) >= candidate_limit:
                    break
                if (
                    scoped_item_ids
                    and scope_snapshot.get("match_mode") == "REQUIRED"
                    and session.mode == ChatSession.Mode.WARDROBE_BASED
                    and not any(item.source_id in scoped_item_ids for item in composition.items)
                ):
                    continue
                validation = self.validator.validate(
                    composition,
                    context=self._validation_context(
                        user_id=user_id,
                        context=context,
                        analysis=analysis,
                        body=body,
                    ),
                )
                if validation.valid:
                    template_candidates.append(
                        ValidatedRecommendationCandidate(
                            ordinal=len(generated) + len(template_candidates) + 1,
                            template_rank=template_rank,
                            composition_rank=composition_rank,
                            golden=candidate,
                            composition=composition,
                            validation=validation,
                        )
                    )
            if template_candidates:
                generated.extend(template_candidates)
                validated_template_count += 1
                if len(generated) >= candidate_limit:
                    break
                if (
                    max_validated_templates is not None
                    and validated_template_count >= max_validated_templates
                ):
                    break

        if not generated:
            raise OutfitCompositionFailed(
                "검색된 골든 코디로 검증 가능한 최종 조합을 만들지 못했습니다."
            )
        return GeneratedRecommendationCandidates(
            run_id=str(run.pk),
            session_id=str(session.pk),
            identity_id=str(session.identity_id),
            response_mode=run.response_mode,
            mode=session.mode,
            search_mode=retrieval.search_mode,
            candidates=tuple(generated),
        )

    @transaction.atomic
    def persist_candidates(
        self,
        *,
        run: ChatRun,
        generated: GeneratedRecommendationCandidates,
        selected: Sequence[ValidatedRecommendationCandidate],
        persona_execution: ChatRunPersona | None = None,
        persona_explanation: str = "",
        validated_reason_codes: Sequence[str] = (),
        strategy_snapshot: dict[str, Any] | None = None,
        result_type: str = RecommendationResult.ResultType.INITIAL,
        replace_current: bool = False,
    ) -> RecommendationPipelineResult:
        """중복 검사·재정렬 뒤 선택된 후보만 최종 추천 결과로 저장한다."""

        selected_candidates = tuple(selected)
        normalized_reason_codes = self._normalize_reason_codes(validated_reason_codes)
        if len(persona_explanation.strip()) > 500:
            raise OutfitCompositionFailed(
                "스타일리스트 추천 설명은 500자 이하여야 합니다."
            )
        if strategy_snapshot is not None and not isinstance(strategy_snapshot, dict):
            raise OutfitCompositionFailed("전략 스냅샷은 JSON 객체여야 합니다.")
        if result_type not in RecommendationResult.ResultType.values:
            raise OutfitCompositionFailed("지원하지 않는 추천 결과 생성 목적입니다.")
        if replace_current != (
            result_type == RecommendationResult.ResultType.ALTERNATIVE
        ):
            raise OutfitCompositionFailed(
                "다른 추천 결과만 현재 스타일리스트 결과를 교체할 수 있습니다."
            )
        self._validate_persistence_scope(
            run=run,
            generated=generated,
            selected=selected_candidates,
            persona_execution=persona_execution,
        )

        locked_run = (
            ChatRun.objects.select_for_update()
            .select_related(
                "session",
                "session__identity",
            )
            .get(pk=run.pk)
        )
        existing = self._existing_result(
            run=locked_run,
            persona_execution=persona_execution,
        )
        if existing is not None and not replace_current:
            self._schedule_render_on_commit(
                run=locked_run,
                result_id=existing.pk,
            )
            return RecommendationPipelineResult(
                result=existing,
                approved_payload=self._approved_payload(existing),
            )
        if replace_current and (persona_execution is None or existing is None):
            raise OutfitCompositionFailed(
                "다른 추천을 생성할 현재 스타일리스트 결과가 없습니다."
            )

        generation = 1
        replaces = None
        if replace_current:
            generation = (
                RecommendationResult.objects.filter(
                    run=locked_run,
                    persona_id=persona_execution.persona_id,
                ).aggregate(value=Max("generation"))["value"]
                or 1
            ) + 1
            replaces = existing
            RecommendationResult.objects.filter(pk=existing.pk).update(is_current=False)

        candidate = selected_candidates[0].golden
        result = RecommendationResult.objects.create(
            identity=locked_run.session.identity,
            session=locked_run.session,
            run=locked_run,
            persona_execution=persona_execution,
            response_mode=locked_run.response_mode,
            persona_id=(persona_execution.persona_id if persona_execution else ""),
            persona_version=(
                persona_execution.persona_version if persona_execution else None
            ),
            persona_explanation=persona_explanation.strip(),
            validated_reason_codes=normalized_reason_codes,
            strategy_snapshot=(
                dict(strategy_snapshot)
                if strategy_snapshot is not None
                else (
                    dict(persona_execution.strategy_snapshot)
                    if persona_execution is not None
                    else {}
                )
            ),
            result_type=result_type,
            generation=generation,
            is_current=True,
            replaces=replaces,
            mode=locked_run.session.mode,
            dataset_version=(
                settings.CHAT_GOLDENSET_DATASET_VERSION
                or str(candidate.payload.get("dataset_version") or "unversioned")
            ),
        )
        GoldenTemplateSnapshot.objects.create(
            result=result,
            golden_id=candidate.golden_id or candidate.point_id,
            point_id=candidate.point_id,
            retrieval_score=candidate.score,
            payload_snapshot=candidate.payload,
            reasons=[
                {"source": reason.source, "delta": reason.delta, "text": reason.text}
                for reason in candidate.reasons
            ],
        )
        for rank, selected_candidate in enumerate(selected_candidates, start=1):
            self._persist_composition(
                result=result,
                rank=rank,
                candidate=selected_candidate,
            )

        result_id = result.pk
        self._schedule_render_on_commit(run=locked_run, result_id=result_id)
        return RecommendationPipelineResult(
            result=result,
            approved_payload=self._approved_payload(result),
        )

    @staticmethod
    def _schedule_render_on_commit(*, run: ChatRun, result_id: Any) -> None:
        """기본 추천만 저장 커밋 후 이미지를 자동 생성한다."""

        if run.response_mode != ChatSession.ResponseMode.DEFAULT:
            return
        transaction.on_commit(lambda: render_jobs.schedule_result(result_id))

    @staticmethod
    def _validate_persistence_scope(
        *,
        run: ChatRun,
        generated: GeneratedRecommendationCandidates,
        selected: tuple[ValidatedRecommendationCandidate, ...],
        persona_execution: ChatRunPersona | None,
    ) -> None:
        expected_scope = (
            str(run.pk),
            str(run.session_id),
            str(run.session.identity_id),
            run.response_mode,
            run.session.mode,
        )
        actual_scope = (
            generated.run_id,
            generated.session_id,
            generated.identity_id,
            generated.response_mode,
            generated.mode,
        )
        if actual_scope != expected_scope:
            raise OutfitCompositionFailed(
                "다른 채팅 실행에서 생성한 추천 후보는 저장할 수 없습니다."
            )
        if not selected:
            raise OutfitCompositionFailed("최종 저장할 추천 후보가 없습니다.")

        available = {candidate.ordinal: candidate for candidate in generated.candidates}
        if len({candidate.ordinal for candidate in selected}) != len(selected) or any(
            available.get(candidate.ordinal) != candidate for candidate in selected
        ):
            raise OutfitCompositionFailed(
                "생성 결과에 속한 서로 다른 추천 후보만 저장할 수 있습니다."
            )

        golden_keys = {
            (candidate.golden.point_id, candidate.golden.golden_id)
            for candidate in selected
        }
        if len(golden_keys) != 1:
            raise OutfitCompositionFailed(
                "하나의 추천 결과에는 같은 골든 템플릿의 후보만 저장할 수 있습니다."
            )

        if run.response_mode == ChatSession.ResponseMode.DEFAULT:
            if persona_execution is not None:
                raise OutfitCompositionFailed(
                    "기본 응답에는 스타일리스트 실행을 연결할 수 없습니다."
                )
            if len(selected) > 3:
                raise OutfitCompositionFailed(
                    "기본 응답은 검증된 코디를 최대 3개까지 저장할 수 있습니다."
                )
            return

        if run.response_mode != ChatSession.ResponseMode.STYLIST:
            raise OutfitCompositionFailed("지원하지 않는 추천 응답 모드입니다.")
        if persona_execution is None or persona_execution.run_id != run.pk:
            raise OutfitCompositionFailed(
                "스타일리스트 응답에는 같은 ChatRun의 개별 실행이 필요합니다."
            )
        if len(selected) != 1:
            raise OutfitCompositionFailed(
                "스타일리스트별 추천 결과는 코디 하나만 저장해야 합니다."
            )

    @staticmethod
    def _existing_result(
        *,
        run: ChatRun,
        persona_execution: ChatRunPersona | None,
    ) -> RecommendationResult | None:
        queryset = RecommendationResult.objects.filter(
            run=run,
            response_mode=run.response_mode,
        )
        if persona_execution is None:
            return queryset.filter(persona_execution__isnull=True).first()
        return queryset.filter(
            persona_execution=persona_execution,
            is_current=True,
        ).first()

    @staticmethod
    def _normalize_reason_codes(codes: Sequence[str]) -> list[str]:
        normalized: list[str] = []
        for code in codes:
            if not isinstance(code, str) or not code.strip():
                raise OutfitCompositionFailed(
                    "검증 근거 코드는 비어 있지 않은 문자열이어야 합니다."
                )
            value = code.strip()
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def _sources(mode: str, user_id: int | None) -> tuple[ItemSource, ...]:
        if mode == ChatSession.Mode.WARDROBE_BASED:
            return (ItemSource.WARDROBE,)
        if user_id is None:
            return (ItemSource.PRODUCT,)
        return (ItemSource.WARDROBE, ItemSource.PRODUCT)

    def _compose(
        self,
        mode: str,
        slot_results: tuple,
        *,
        budget: int | None,
        category_budgets: dict[str, int],
    ):
        if mode == ChatSession.Mode.WARDROBE_BASED:
            return self.wardrobe_composer.compose(
                WardrobeCompositionRequest(slot_results=slot_results)
            )
        return self.new_item_composer.compose(
            NewItemCompositionRequest(
                slot_results=slot_results,
                total_budget=budget,
                category_budgets=category_budgets,
            )
        )

    @staticmethod
    def _template_item_ids(candidate: OutfitCandidate) -> tuple[str, ...]:
        values: list[str] = []
        raw_ids = candidate.payload.get("item_point_ids")
        if isinstance(raw_ids, (list, tuple)):
            values.extend(str(value) for value in raw_ids if value not in (None, ""))
        for item in candidate.items:
            if not isinstance(item, dict):
                continue
            value = item.get("item_point_id") or item.get("point_id")
            if value not in (None, ""):
                values.append(str(value))
        return tuple(dict.fromkeys(values))

    @staticmethod
    def _merged_pursuit(context: dict, analysis: TurnAnalysis) -> dict:
        source = context.get("profile", {}).get("pursuit") or {}
        preferred = {
            key: list(values) for key, values in (source.get("preferred") or {}).items()
        }
        avoided = {
            key: list(values) for key, values in (source.get("avoided") or {}).items()
        }
        preferred["styles"] = list(
            dict.fromkeys([*preferred.get("styles", []), *analysis.conditions.styles])
        )
        preferred["colors"] = list(
            dict.fromkeys([*preferred.get("colors", []), *analysis.conditions.colors])
        )
        preferred["fits"] = list(
            dict.fromkeys([*preferred.get("fits", []), *analysis.conditions.fits])
        )
        avoided["styles"] = list(
            dict.fromkeys(
                [*avoided.get("styles", []), *analysis.conditions.avoided_styles]
            )
        )
        avoided["colors"] = list(
            dict.fromkeys(
                [*avoided.get("colors", []), *analysis.conditions.avoided_colors]
            )
        )
        return {"preferred": preferred, "avoided": avoided}

    @staticmethod
    def _apply_strategy_preferences(
        pursuit: dict[str, dict[str, list[str]]],
        plan: StrategyPlan,
    ) -> dict[str, dict[str, list[str]]]:
        """전략의 소프트 보정을 원본 사용자 조건을 보존한 검색 입력으로 변환한다."""

        adjusted = {
            polarity: {
                axis: list(values)
                for axis, values in (pursuit.get(polarity) or {}).items()
            }
            for polarity in ("preferred", "avoided")
        }
        axis_names = {"style": "styles", "color": "colors", "fit": "fits"}
        for row in plan.preference_adjustments:
            polarity = (
                "preferred" if row.polarity is PreferencePolarity.PREFER else "avoided"
            )
            axis = axis_names[row.axis]
            adjusted[polarity][axis] = list(
                dict.fromkeys([*adjusted[polarity].get(axis, []), *row.values])
            )
        return adjusted

    @staticmethod
    def _presentation_groups(
        *,
        context: dict[str, Any],
        analysis: TurnAnalysis,
    ) -> tuple[str, ...]:
        explicit = analysis.conditions.presentation_groups
        if explicit:
            return normalize_presentation_groups(explicit)
        return ()

    @staticmethod
    def _gender(context: dict[str, Any]) -> str:
        body = context.get("profile", {}).get("body") or {}
        return str(body.get("gender") or "") if isinstance(body, dict) else ""

    @staticmethod
    def _validation_context(
        *,
        user_id: int | None,
        context: dict,
        analysis: TurnAnalysis,
        body: BodyProfile,
    ) -> ValidationContext:
        return ValidationContext(
            user_id=user_id,
            body=body,
            season=analysis.conditions.season,
            weather=context.get("weather"),
            occasion=analysis.conditions.occasion,
            total_budget=analysis.conditions.budget,
            category_budgets=context.get("profile", {}).get("category_budgets", {}),
            excluded_source_ids=tuple(analysis.conditions.excluded_source_ids),
            preferred_tags={
                "style": tuple(analysis.conditions.styles),
                "color": tuple(analysis.conditions.colors),
                "fit": tuple(analysis.conditions.fits),
            },
            avoided_tags={
                "style": tuple(analysis.conditions.avoided_styles),
                "color": tuple(analysis.conditions.avoided_colors),
            },
            require_image=True,
        )

    @staticmethod
    def _composition_fingerprint(composition) -> str:
        value = [
            {
                "position": position,
                "slot": item.slot_id,
                "source_type": item.source_type.value,
                "source_id": item.source_id,
                "image_ref": item.image_ref,
            }
            for position, item in enumerate(composition.items, start=1)
        ]
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _persist_composition(
        self,
        *,
        result: RecommendationResult,
        rank: int,
        candidate: ValidatedRecommendationCandidate,
    ) -> None:
        composition = candidate.composition
        validation = candidate.validation
        row = OutfitCompositionModel.objects.create(
            result=result,
            rank=rank,
            status=OutfitCompositionModel.Status.VALIDATED,
            composition_fingerprint=self._composition_fingerprint(composition),
            total_product_price=validation.effective_total_product_price,
            validation_reasons=[
                {
                    "severity": issue.severity.value,
                    "code": issue.code,
                    "message": issue.message,
                    "slot": issue.slot_id,
                }
                for issue in validation.issues
            ],
            warnings=list(composition.warnings),
        )
        for position, item in enumerate(composition.items, start=1):
            OutfitCompositionItem.objects.create(
                composition=row,
                position=position,
                slot=item.slot_id,
                source_type=item.source_type.value,
                source_id=item.source_id,
                source_collection=item.source_collection,
                source_point_id=item.point_id,
                template_item_point_id=item.template_point_id,
                replacement_score=item.score,
                image_ref=item.image_ref,
                price_snapshot=item.price,
                reasons=list(item.reasons),
                item_snapshot=item.payload,
            )

    @staticmethod
    def _approved_payload(result: RecommendationResult) -> dict[str, Any]:
        compositions = []
        for composition in result.compositions.prefetch_related("items").all():
            compositions.append(
                {
                    "rank": composition.rank,
                    "total_product_price": composition.total_product_price,
                    "warnings": composition.warnings,
                    "items": [
                        {
                            "slot": item.slot,
                            "source_type": item.source_type,
                            "name": (
                                item.item_snapshot.get("item_name")
                                or item.item_snapshot.get("name")
                                or item.item_snapshot.get("title")
                                or item.slot
                            ),
                            "price": item.price_snapshot,
                            "reasons": item.reasons,
                        }
                        for item in composition.items.all()
                    ],
                }
            )
        return {
            "result_id": str(result.id),
            "mode": result.mode,
            "compositions": compositions,
        }
