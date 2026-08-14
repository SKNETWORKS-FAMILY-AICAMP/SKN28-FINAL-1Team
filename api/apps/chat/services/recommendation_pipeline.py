"""오케스트레이터가 기존 Retriever·Composer·Validator를 호출하는 경계."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.chat.models import ChatRun, ChatSession
from apps.chat.services.openai_adapter import TurnAnalysis
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
from apps.recommend.services.retriever import (
    GoldenOutfitRetriever,
    OutfitCandidate,
    RetrievalRequest,
    RetrievalResult,
    normalize_presentation_groups,
)
from apps.recommend.services.text_embedding import TextEmbeddingConfigurationError
from apps.recommend.services.validator import OutfitValidator, ValidationContext
from apps.recommend.services.wardrobe_composer import (
    WardrobeCompositionRequest,
    WardrobeOutfitComposer,
)


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
        existing = RecommendationResult.objects.filter(
            run=run,
            response_mode=RecommendationResult.ResponseMode.DEFAULT,
        ).first()
        if existing is not None:
            transaction.on_commit(lambda: render_jobs.schedule_result(existing.pk))
            return RecommendationPipelineResult(
                result=existing,
                approved_payload=self._approved_payload(existing),
            )

        session = run.session
        user_id = session.identity.user_id
        if session.mode == ChatSession.Mode.WARDROBE_BASED and user_id is None:
            raise OutfitCompositionFailed(
                "옷장 기반 추천은 회원의 확정된 옷장 아이템이 필요합니다."
            )

        pursuit = self._merged_pursuit(context, analysis)
        body = build_profile(context.get("profile", {}).get("body"))
        retrieval = self._retrieve_golden(
            RetrievalRequest(
                body=body,
                pursuit=pursuit,
                weather=context.get("weather"),
                gender=self._gender(context),
                occasion=analysis.conditions.occasion,
                season=analysis.conditions.season,
                query_text=analysis.search_query or context["current_request"],
                presentation_groups=self._presentation_groups(
                    context=context,
                    analysis=analysis,
                ),
                dataset_version=settings.CHAT_GOLDENSET_DATASET_VERSION,
                dataset_statuses=settings.CHAT_GOLDENSET_DATASET_STATUSES,
                limit=5,
                hard_filter=True,
                # 골든 코디는 내부 조합 템플릿이다. 원본 이미지 노출 권한은
                # 결과 표출·렌더링 경계에서 별도로 검사한다.
                exposable_only=False,
            )
        )
        if not retrieval.candidates:
            raise GoldenOutfitNotFound("조건에 맞는 골든 코디를 찾지 못했습니다.")

        for candidate in retrieval.candidates:
            template_ids = self._template_item_ids(candidate)
            if not template_ids:
                continue
            try:
                slot_results = tuple(
                    self.item_retriever.retrieve(
                        ItemRetrievalRequest(
                            template_item_point_id=point_id,
                            sources=self._sources(session.mode, user_id),
                            user_id=user_id,
                            max_price=analysis.conditions.budget,
                            dataset_version=settings.CHAT_GOLDENSET_DATASET_VERSION,
                            dataset_statuses=settings.CHAT_GOLDENSET_DATASET_STATUSES,
                            limit_per_source=10,
                        )
                    )
                    for point_id in template_ids
                )
                batch = self._compose(
                    session.mode,
                    slot_results,
                    budget=analysis.conditions.budget,
                )
            except (ValueError, RuntimeError):
                continue

            validated = []
            for composition in batch.compositions:
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
                    validated.append((composition, validation))
            if validated:
                result = self._persist(
                    run=run,
                    candidate=candidate,
                    validated=validated,
                )
                return RecommendationPipelineResult(
                    result=result,
                    approved_payload=self._approved_payload(result),
                )

        raise OutfitCompositionFailed(
            "검색된 골든 코디로 검증 가능한 최종 조합을 만들지 못했습니다."
        )

    @staticmethod
    def _sources(mode: str, user_id: int | None) -> tuple[ItemSource, ...]:
        if mode == ChatSession.Mode.WARDROBE_BASED:
            return (ItemSource.WARDROBE,)
        if user_id is None:
            return (ItemSource.PRODUCT,)
        return (ItemSource.WARDROBE, ItemSource.PRODUCT)

    def _compose(self, mode: str, slot_results: tuple, *, budget: int | None):
        if mode == ChatSession.Mode.WARDROBE_BASED:
            return self.wardrobe_composer.compose(
                WardrobeCompositionRequest(slot_results=slot_results)
            )
        return self.new_item_composer.compose(
            NewItemCompositionRequest(
                slot_results=slot_results,
                total_budget=budget,
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

    @transaction.atomic
    def _persist(self, *, run: ChatRun, candidate: OutfitCandidate, validated: list):
        result = RecommendationResult.objects.create(
            identity=run.session.identity,
            session=run.session,
            run=run,
            response_mode=RecommendationResult.ResponseMode.DEFAULT,
            mode=run.session.mode,
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
        for rank, (composition, validation) in enumerate(validated[:3], start=1):
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
        result_id = result.pk
        transaction.on_commit(lambda: render_jobs.schedule_result(result_id))
        return result

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
