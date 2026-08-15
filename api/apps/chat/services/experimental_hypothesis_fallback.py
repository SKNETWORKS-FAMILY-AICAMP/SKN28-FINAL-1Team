"""실험형 가설 LLM 실패 시 사용하는 결정적 규칙 fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from apps.chat.services.experimental_hypotheses import (
    ExperimentalHypothesis,
    ExperimentalHypothesisBatch,
    ExperimentAxis,
    ExperimentReasonCode,
)
from apps.chat.services.experimental_hypothesis_generation import (
    build_experimental_hypothesis_payload,
)
from apps.chat.services.openai_adapter import (
    ChatLLMError,
    LLMUsage,
    OpenAIChatAdapter,
)

_SLOT_STYLE_AXES = (
    (("BOTTOM", "PANTS", "SKIRT", "하의"), ExperimentAxis.BOTTOM_STYLE),
    (("TOP", "상의"), ExperimentAxis.TOP_STYLE),
    (("OUTER", "아우터"), ExperimentAxis.OUTER_STYLE),
    (("SHOE", "FOOTWEAR", "신발"), ExperimentAxis.FOOTWEAR_STYLE),
    (("DRESS", "ONEPIECE", "원피스", "세트"), ExperimentAxis.PROPORTION),
)
_SLOT_SILHOUETTE_AXES = (
    (("BOTTOM", "PANTS", "SKIRT", "하의"), ExperimentAxis.BOTTOM_SILHOUETTE),
    (("TOP", "상의"), ExperimentAxis.TOP_SILHOUETTE),
    (("OUTER", "아우터"), ExperimentAxis.OUTER_SILHOUETTE),
)


class ExperimentalHypothesisSource(StrEnum):
    LLM = "LLM"
    RULE_FALLBACK = "RULE_FALLBACK"


@dataclass(frozen=True)
class ResolvedExperimentalHypotheses:
    batch: ExperimentalHypothesisBatch
    source: ExperimentalHypothesisSource
    usage: LLMUsage = field(default_factory=LLMUsage)
    response_id: str = ""
    fallback_error_code: str = ""

    def snapshot(self) -> dict[str, Any]:
        """ChatRunPersona.hypothesis_snapshot에 저장 가능한 ID 없는 결과."""

        return {
            "source": self.source.value,
            "hypotheses": self.batch.model_dump(mode="json")["hypotheses"],
            "fallback_error_code": self.fallback_error_code or None,
        }


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _slot_axis(
    slot: object,
    mappings: tuple[tuple[tuple[str, ...], ExperimentAxis], ...],
) -> ExperimentAxis | None:
    normalized = str(slot or "").strip().upper().replace(" ", "_")
    if not normalized:
        return None
    return next(
        (
            axis
            for tokens, axis in mappings
            if any(token in normalized for token in tokens)
        ),
        None,
    )


def _preserve_axes(
    change_axes: tuple[ExperimentAxis, ...],
) -> tuple[ExperimentAxis, ...]:
    anchors = [ExperimentAxis.TOP_STYLE, ExperimentAxis.COLOR_FAMILY]
    return tuple(axis for axis in anchors if axis not in change_axes)


def _hypothesis(
    *,
    change_axes: tuple[ExperimentAxis, ...],
    reason_code: ExperimentReasonCode,
) -> ExperimentalHypothesis:
    return ExperimentalHypothesis(
        change_axes=change_axes,
        preserve_axes=_preserve_axes(change_axes),
        reason_code=reason_code,
    )


def _has_underused_features(calendar: dict[str, Any]) -> bool:
    features = _mapping(calendar.get("underused_item_features"))
    return any(_rows(value) for value in features.values())


def build_rule_based_experimental_hypotheses(
    context: dict[str, Any],
) -> ExperimentalHypothesisBatch:
    """가용 근거를 우선순위대로 적용해 서로 다른 가설 두 개를 만든다."""

    payload = build_experimental_hypothesis_payload(context)
    behavior = _mapping(payload.get("behavior"))
    recent = _mapping(behavior.get("recent_recommendations"))
    calendar = _mapping(behavior.get("calendar_wear"))
    hypotheses: list[ExperimentalHypothesis] = []

    repeated_slots = sorted(
        _rows(recent.get("repeated_slots")),
        key=lambda row: (-int(row.get("count") or 0), str(row.get("slot") or "")),
    )
    repeated_slot_axis = next(
        (
            axis
            for row in repeated_slots
            if int(row.get("count") or 0) >= 2
            if (axis := _slot_axis(row.get("slot"), _SLOT_STYLE_AXES)) is not None
        ),
        None,
    )
    if repeated_slot_axis is not None:
        hypotheses.append(
            _hypothesis(
                change_axes=(repeated_slot_axis,),
                reason_code=ExperimentReasonCode.RECENT_SLOT_REPETITION,
            )
        )

    repeated_fit = next(
        (
            row
            for row in _rows(recent.get("fit_counts"))
            if int(row.get("count") or 0) >= 2
        ),
        None,
    )
    if repeated_fit is not None:
        silhouette_axis = next(
            (
                axis
                for row in repeated_slots
                if (axis := _slot_axis(row.get("slot"), _SLOT_SILHOUETTE_AXES))
                is not None
            ),
            ExperimentAxis.BOTTOM_SILHOUETTE,
        )
        hypotheses.append(
            _hypothesis(
                change_axes=(silhouette_axis,),
                reason_code=ExperimentReasonCode.RECENT_SILHOUETTE_REPETITION,
            )
        )

    if len(hypotheses) < 2 and _has_underused_features(calendar):
        hypotheses.append(
            _hypothesis(
                change_axes=(ExperimentAxis.UNDERUSED_ITEM_SLOT,),
                reason_code=ExperimentReasonCode.CALENDAR_ITEM_UNDERUSE,
            )
        )

    conservative_rules = (
        _hypothesis(
            change_axes=(ExperimentAxis.MATERIAL_MIX,),
            reason_code=ExperimentReasonCode.SAME_COLOR_MATERIAL_VARIATION,
        ),
        _hypothesis(
            change_axes=(ExperimentAxis.PROPORTION,),
            reason_code=ExperimentReasonCode.SAME_COLOR_MATERIAL_VARIATION,
        ),
    )
    existing_signatures = {(row.change_axes, row.preserve_axes) for row in hypotheses}
    for row in conservative_rules:
        signature = (row.change_axes, row.preserve_axes)
        if len(hypotheses) >= 2:
            break
        if signature not in existing_signatures:
            hypotheses.append(row)
            existing_signatures.add(signature)

    return ExperimentalHypothesisBatch(hypotheses=tuple(hypotheses[:2]))


class ExperimentalHypothesisResolver:
    """LLM 결과를 우선하고 제공자 실패 시 규칙 결과로 안전하게 전환한다."""

    def __init__(self, *, llm: OpenAIChatAdapter | None = None) -> None:
        self.llm = llm or OpenAIChatAdapter()

    def resolve(
        self,
        *,
        identity_id: str,
        context: dict[str, Any],
    ) -> ResolvedExperimentalHypotheses:
        try:
            result = self.llm.generate_experimental_hypotheses(
                identity_id=identity_id,
                context=context,
            )
            if not isinstance(result.value, ExperimentalHypothesisBatch):
                raise ChatLLMError("실험형 가설 구조화 응답 형식이 잘못되었습니다.")
            return ResolvedExperimentalHypotheses(
                batch=result.value,
                source=ExperimentalHypothesisSource.LLM,
                usage=result.usage,
                response_id=result.response_id,
            )
        except (ChatLLMError, ImproperlyConfigured) as exc:
            error_code = getattr(exc, "code", "CHAT_LLM_CONFIGURATION_ERROR")
            return ResolvedExperimentalHypotheses(
                batch=build_rule_based_experimental_hypotheses(context),
                source=ExperimentalHypothesisSource.RULE_FALLBACK,
                fallback_error_code=str(error_code),
            )
