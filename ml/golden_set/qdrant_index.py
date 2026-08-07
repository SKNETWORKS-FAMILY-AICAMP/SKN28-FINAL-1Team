"""승인 원칙과 보조 점수 앵커를 Qdrant 파생 저장소에 적재한다."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from .artifacts import read_json, read_jsonl, write_json
from .config import GoldenSettings
from .embedding import (
    BgeM3Backend,
    DeterministicTextBackend,
    TextEmbeddingBackend,
    load_embeddings,
)

KNOWLEDGE_COLLECTION = "knowledge"
ANCHOR_COLLECTION = "outfit_goldenset"
_POINT_NAMESPACE = uuid.UUID("c989a713-85ee-43aa-8d68-04cecf225e9e")


def index_run(
    *,
    run_dir: Path,
    settings: GoldenSettings,
    text_backend_name: str = "bge",
    allow_draft: bool = False,
    dry_run: bool = False,
    client: QdrantClient | None = None,
) -> dict[str, Any]:
    run_manifest = read_json(run_dir / "run_manifest.json")
    images = {row["golden_id"]: row for row in read_jsonl(run_dir / "images.jsonl")}
    clusters = {row["golden_id"]: row for row in read_jsonl(run_dir / "clusters.jsonl")}
    analyses = {row["golden_id"]: row for row in read_jsonl(run_dir / "analyses.jsonl")}
    approved_claims = {
        row["golden_id"]: row.get("claims", [])
        for row in read_jsonl(run_dir / "approved_claims.jsonl")
    }
    anchors = {
        row["golden_id"]: row for row in read_jsonl(run_dir / "anchor_scores.jsonl")
    }
    principles = read_jsonl(run_dir / "principles.jsonl")
    image_ids, image_vectors = load_embeddings(run_dir / "image_embeddings.npz")
    image_vector_map = {
        golden_id: image_vectors[index] for index, golden_id in enumerate(image_ids)
    }

    if text_backend_name == "deterministic":
        text_backend: TextEmbeddingBackend = DeterministicTextBackend()
    elif text_backend_name == "bge":
        text_backend = BgeM3Backend(settings.text_model_id, settings.device)
    else:
        raise ValueError(f"지원하지 않는 텍스트 임베딩 백엔드: {text_backend_name}")

    allowed_statuses = {"APPROVED", "DRAFT"} if allow_draft else {"APPROVED"}
    eligible_principles = [
        row for row in principles if row.get("status") in allowed_statuses
    ]
    principle_texts = [_principle_text(row) for row in eligible_principles]
    principle_vectors = text_backend.encode_texts(principle_texts)

    anchor_ids = [
        golden_id for golden_id in sorted(anchors) if golden_id in image_vector_map
    ]
    anchor_texts = [
        _anchor_text(
            images[golden_id],
            analyses.get(golden_id, {}),
            approved_claims.get(golden_id, []),
        )
        for golden_id in anchor_ids
    ]
    anchor_text_vectors = text_backend.encode_texts(anchor_texts)

    principle_points = [
        PointStruct(
            id=_point_id(
                f"principle:{run_manifest['dataset_version']}:{row['principle_key']}"
            ),
            vector={"text": principle_vectors[index].tolist()},
            payload={
                "knowledge_type": "golden_principle",
                "dimension": row.get("axis") or row.get("dimension", ""),
                "axis": row.get("axis") or row.get("dimension", ""),
                "status": row.get("status", "DRAFT"),
                "knowledge_role": row.get(
                    "knowledge_role", "NEEDS_COUNTEREXAMPLE"
                ),
                "principle_type": row.get("principle_type", "SOFT_PRINCIPLE"),
                "eligible_for_scoring": bool(row.get("eligible_for_scoring", False)),
                "source": "team_golden_set",
                "dataset_version": run_manifest["dataset_version"],
                "style": _principle_styles(row),
                "principle_key": row["principle_key"],
                "statement": row.get("statement", ""),
                "applies_when": row.get("applies_when", []),
                "exceptions": row.get("exceptions", []),
                "confidence": row.get("confidence", 0.0),
                "support_image_count": int(row.get("support_image_count", 0)),
                "comparison_evidence_count": int(
                    row.get("comparison_evidence_count", 0)
                ),
                "reviewer_count": int(row.get("reviewer_count", 0)),
                "reviewer_agreement": float(row.get("reviewer_agreement", 0.0)),
                "evidence": row.get("evidence", []),
                "embedding_version": text_backend.name,
            },
        )
        for index, row in enumerate(eligible_principles)
    ]

    anchor_points = []
    for index, golden_id in enumerate(anchor_ids):
        image = images[golden_id]
        anchor = anchors[golden_id]
        analysis = analyses.get(golden_id, {}).get("result", {})
        look_tags = analysis.get("look_tags", {})
        anchor_points.append(
            PointStruct(
                id=_point_id(f"anchor:{run_manifest['dataset_version']}:{golden_id}"),
                vector={
                    "image": image_vector_map[golden_id].tolist(),
                    "text": anchor_text_vectors[index].tolist(),
                },
                payload={
                    "source": "team_golden_set",
                    "dataset_version": run_manifest["dataset_version"],
                    "status": "PILOT",
                    "split": image.get("split", "KNOWLEDGE"),
                    "presentation_group": image.get("presentation_group", ""),
                    "style": look_tags.get("style")
                    or image.get("metadata", {}).get("style", []),
                    "season": look_tags.get("season_cues")
                    or look_tags.get("season")
                    or image.get("metadata", {}).get("season", []),
                    "occasion": image.get("metadata", {}).get("occasion", []),
                    "score_band": anchor["score_band"],
                    "human_score": float(anchor["human_score"]),
                    "score_confidence": float(anchor["score_confidence"]),
                    "anchor_scope": anchor.get(
                        "anchor_scope", "Q_OVERALL_STYLE_EXECUTION"
                    ),
                    "human_axis_scores_1_5": anchor.get(
                        "human_axis_scores_1_5", {}
                    ),
                    "reviewer_count": int(anchor.get("reviewer_count", 0)),
                    "comparison_count": int(anchor.get("comparison_count", 0)),
                    "reviewer_agreement": float(
                        anchor.get("reviewer_agreement", 0.0)
                    ),
                    "rationale_ko": " | ".join(
                        str(row.get("statement", ""))
                        for row in approved_claims.get(golden_id, [])
                    ),
                    "golden_id": golden_id,
                    "cluster_id": clusters.get(golden_id, {}).get("cluster_id", ""),
                    "source_uri": image.get("source_uri", ""),
                    "exposable": False,
                    "image_embedding_version": read_json(
                        run_dir / "image_embeddings.meta.json"
                    )["model"],
                    "text_embedding_version": text_backend.name,
                },
            )
        )

    summary = {
        "dataset_version": run_manifest["dataset_version"],
        "principle_points": len(principle_points),
        "anchor_points": len(anchor_points),
        "principle_statuses": sorted(
            {str(row.get("status", "DRAFT")) for row in eligible_principles}
        ),
        "dry_run": dry_run,
        "text_embedding_version": text_backend.name,
    }
    write_json(run_dir / "qdrant_index_plan.json", summary)
    if dry_run:
        return summary

    image_embedding_model = read_json(run_dir / "image_embeddings.meta.json")["model"]
    if text_backend.name.startswith("deterministic-") or str(
        image_embedding_model
    ).startswith("deterministic-"):
        raise RuntimeError(
            "deterministic 테스트 벡터는 실제 Qdrant에 적재할 수 없습니다. "
            "FashionSigLIP·BGE-M3로 prepare/index를 다시 실행하세요."
        )

    qdrant = client or QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
        timeout=int(os.getenv("QDRANT_TIMEOUT", "30")),
    )
    _assert_collections(qdrant)
    if principle_points:
        qdrant.upsert(
            collection_name=KNOWLEDGE_COLLECTION,
            points=principle_points,
            wait=True,
        )
    if anchor_points:
        qdrant.upsert(
            collection_name=ANCHOR_COLLECTION,
            points=anchor_points,
            wait=True,
        )
    return summary


def _point_id(value: str) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, value))


def _principle_text(row: dict[str, Any]) -> str:
    applies_when = row.get("applies_when", {})
    if isinstance(applies_when, dict):
        applies_text = ", ".join(
            f"{key}={','.join(str(item) for item in value)}"
            for key, value in applies_when.items()
            if value
        )
    else:
        applies_text = ", ".join(str(item) for item in applies_when)
    return "\n".join(
        [
            f"판단 축: {row.get('axis') or row.get('dimension', '')}",
            f"원칙: {row.get('statement', '')}",
            "적용 조건: " + applies_text,
            "예외: " + ", ".join(row.get("exceptions", [])),
            f"지식 역할: {row.get('knowledge_role', '')}",
        ]
    )


def _anchor_text(
    image: dict[str, Any],
    analysis: dict[str, Any],
    approved_claims: list[dict[str, Any]],
) -> str:
    result = analysis.get("result", {})
    tags = result.get("look_tags", {})
    return "\n".join(
        [
            "스타일: " + ", ".join(tags.get("style", [])),
            "계절 단서: "
            + ", ".join(tags.get("season_cues", []) or tags.get("season", [])),
            "색상: " + ", ".join(tags.get("colors", [])),
            f"실루엣: {tags.get('overall_silhouette', '')}",
            "사람 승인 근거: "
            + " | ".join(str(row.get("statement", "")) for row in approved_claims),
        ]
    )


def _principle_styles(row: dict[str, Any]) -> list[str]:
    applies_when = row.get("applies_when", {})
    if isinstance(applies_when, dict):
        return [str(value) for value in applies_when.get("style_intents", [])]
    values = []
    for condition in applies_when:
        if isinstance(condition, str) and condition.startswith("style:"):
            values.extend(
                value.strip()
                for value in condition.removeprefix("style:").split(",")
                if value.strip()
            )
    return values


def _assert_collections(client: QdrantClient) -> None:
    missing = [
        name
        for name in (KNOWLEDGE_COLLECTION, ANCHOR_COLLECTION)
        if not client.collection_exists(name)
    ]
    if missing:
        raise RuntimeError(
            "Qdrant 컬렉션이 없습니다. 먼저 Django의 init_qdrant를 실행하세요: "
            + ", ".join(missing)
        )
