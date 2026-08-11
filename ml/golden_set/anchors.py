"""사람 쌍대 비교를 보조 Q 점수 앵커로 환산한다."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import numpy as np

from .artifacts import write_json, write_jsonl
from .review import PAIRWISE_OUTCOMES, aggregate_axis_scores, read_csv_rows


def build_anchor_scores(
    *,
    pairwise_csv: Path,
    run_dir: Path,
    observation_reviews_csv: Path | None = None,
    iterations: int = 200,
    minimum_reviewers_per_pair: int = 2,
) -> list[dict[str, Any]]:
    rows = read_csv_rows(pairwise_csv)
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    seen_reviewer_votes: set[tuple[str, str, str]] = set()
    skipped_rows = 0
    for row in rows:
        winner = row.get("winner", "").strip().lower()
        if not winner:
            continue
        if winner not in PAIRWISE_OUTCOMES and winner not in {
            row.get("left_id", ""),
            row.get("right_id", ""),
        }:
            raise ValueError(f"지원하지 않는 쌍대 비교 결과입니다: {winner}")
        if winner in {"context_dependent", "unassessable"}:
            skipped_rows += 1
            continue
        left, right = row.get("left_id", ""), row.get("right_id", "")
        reviewer = row.get("reviewer_label", "").strip()
        if not left or not right or left == right or not reviewer:
            skipped_rows += 1
            continue
        pair = tuple(sorted((left, right)))
        duplicate_key = (*pair, reviewer)
        if duplicate_key in seen_reviewer_votes:
            raise ValueError(f"동일 검수자의 중복 쌍대 비교가 있습니다: {duplicate_key}")
        seen_reviewer_votes.add(duplicate_key)
        grouped[pair].append(row)

    eligible_pairs = {
        pair: pair_rows
        for pair, pair_rows in grouped.items()
        if len({row["reviewer_label"] for row in pair_rows})
        >= minimum_reviewers_per_pair
    }
    if not eligible_pairs:
        raise ValueError(
            "검수자 2명 이상이 완료한 비교 가능한 쌍대 비교가 없습니다."
        )

    ids = sorted({golden_id for pair in eligible_pairs for golden_id in pair})
    index = {golden_id: position for position, golden_id in enumerate(ids)}
    wins = np.zeros(len(ids), dtype=float)
    comparisons = np.zeros((len(ids), len(ids)), dtype=float)
    reviewer_votes: dict[tuple[str, str], list[str]] = defaultdict(list)
    confidence_values: dict[tuple[str, str], list[float]] = defaultdict(list)

    for pair, pair_rows in eligible_pairs.items():
        for row in pair_rows:
            left, right = row["left_id"], row["right_id"]
            left_index, right_index = index[left], index[right]
            comparisons[left_index, right_index] += 1
            comparisons[right_index, left_index] += 1
            winner = row["winner"].strip()
            if winner in {"left", left}:
                wins[left_index] += 1
                normalized = left
            elif winner in {"right", right}:
                wins[right_index] += 1
                normalized = right
            elif winner.lower() == "tie":
                wins[left_index] += 0.5
                wins[right_index] += 0.5
                normalized = "tie"
            else:
                raise ValueError(f"유효하지 않은 비교 결과입니다: {winner}")
            reviewer_votes[pair].append(normalized)
            if row.get("confidence_1_3", ""):
                confidence_values[pair].append(
                    _bounded_number(row["confidence_1_3"], 1, 3)
                )

    _assert_connected(comparisons, ids)
    abilities = _fit_bradley_terry(
        wins=wins,
        comparisons=comparisons,
        iterations=iterations,
    )
    logits = np.log(np.maximum(abilities, 1e-12))
    if np.ptp(logits) < 1e-12:
        scores = np.full(len(ids), 50.0)
    else:
        scores = 100 * (logits - logits.min()) / np.ptp(logits)
    order = np.argsort(-scores)
    bands: dict[int, str] = {}
    for rank, item_index in enumerate(order):
        fraction = rank / max(1, len(ids))
        bands[int(item_index)] = (
            "high" if fraction < 1 / 3 else ("mid" if fraction < 2 / 3 else "low")
        )

    axis_scores = (
        aggregate_axis_scores(observation_reviews_csv)
        if observation_reviews_csv is not None
        else {}
    )
    comparison_counts = comparisons.sum(axis=1)
    result = []
    for position, golden_id in enumerate(ids):
        related_pairs = [pair for pair in eligible_pairs if golden_id in pair]
        related_agreements = []
        related_confidences = []
        related_reviewers: set[str] = set()
        for pair in related_pairs:
            votes = reviewer_votes[pair]
            if votes:
                top_count = max(votes.count(value) for value in set(votes))
                related_agreements.append(top_count / len(votes))
            related_confidences.extend(confidence_values.get(pair, []))
            related_reviewers.update(
                row["reviewer_label"] for row in eligible_pairs[pair]
            )
        agreement = float(np.mean(related_agreements)) if related_agreements else 0.0
        mean_confidence = (
            float(np.mean(related_confidences)) if related_confidences else 1.0
        )
        coverage = min(1.0, float(comparison_counts[position]) / 8.0)
        score_confidence = coverage * agreement * (mean_confidence / 3.0)
        result.append(
            {
                "golden_id": golden_id,
                "anchor_scope": "Q_OVERALL_STYLE_EXECUTION",
                "human_score": round(float(scores[position]), 3),
                "score_band": bands[position],
                "score_confidence": round(score_confidence, 3),
                "comparison_count": int(comparison_counts[position]),
                "reviewer_count": len(related_reviewers),
                "reviewer_agreement": round(agreement, 3),
                "mean_human_confidence_1_3": round(mean_confidence, 3),
                "human_axis_scores_1_5": axis_scores.get(golden_id, {}).get(
                    "axis_scores_1_5", {}
                ),
                "method": "bradley-terry-mm-pilot-v2",
            }
        )
    result.sort(key=lambda row: str(row["golden_id"]))
    write_jsonl(run_dir / "anchor_scores.jsonl", result)
    write_json(
        run_dir / "anchor_scores.meta.json",
        {
            "method": "bradley-terry-mm-pilot-v2",
            "anchor_scope": "Q_OVERALL_STYLE_EXECUTION",
            "minimum_reviewers_per_pair": minimum_reviewers_per_pair,
            "num_eligible_pairs": len(eligible_pairs),
            "num_completed_votes": sum(len(rows) for rows in eligible_pairs.values()),
            "num_skipped_rows": skipped_rows,
            "warning": (
                "파일럿 상대 Q 점수이며 개인 선호 P나 상황 적합도 C를 포함하지 않는 보조 앵커"
            ),
        },
    )
    return result


def _fit_bradley_terry(
    *,
    wins: np.ndarray,
    comparisons: np.ndarray,
    iterations: int,
) -> np.ndarray:
    # 0승·전승에서 발산하지 않도록 관측된 edge에 약한 Jeffreys prior를 둔다.
    abilities = np.ones(len(wins), dtype=float)
    smoothed_wins = wins + 0.5 * (comparisons > 0).sum(axis=1)
    for _ in range(iterations):
        denominator = np.zeros(len(wins), dtype=float)
        for left in range(len(wins)):
            for right in range(len(wins)):
                if left == right or comparisons[left, right] == 0:
                    continue
                denominator[left] += (comparisons[left, right] + 1.0) / (
                    abilities[left] + abilities[right]
                )
        updated = smoothed_wins / np.maximum(denominator, 1e-12)
        updated /= np.exp(np.mean(np.log(np.maximum(updated, 1e-12))))
        if np.max(np.abs(updated - abilities)) < 1e-8:
            return updated
        abilities = updated
    return abilities


def _assert_connected(comparisons: np.ndarray, ids: list[str]) -> None:
    adjacency = {
        index: set(np.flatnonzero(comparisons[index] > 0).tolist())
        for index in range(len(ids))
    }
    visited = {0}
    queue = deque([0])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    if len(visited) != len(ids):
        missing = [ids[index] for index in range(len(ids)) if index not in visited]
        raise ValueError(
            "비교 가능한 2인 검수 쌍만으로 그래프가 연결되지 않았습니다: "
            f"{missing}"
        )


def _bounded_number(value: str, lower: int, upper: int) -> float:
    number = float(value)
    if not lower <= number <= upper:
        raise ValueError(f"점수 범위는 {lower}~{upper}입니다: {value}")
    return number
