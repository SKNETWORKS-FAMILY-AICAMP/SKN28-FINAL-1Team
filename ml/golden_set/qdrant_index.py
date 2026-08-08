"""골든 코디·의상 아이템·승인 원칙을 Qdrant 파생 저장소에 적재한다.

컬렉션 3개를 쓴다.

- `outfit_goldenset` : 코디 1장 = 포인트 1개 (image/text 벡터).
  payload의 `items`가 소속 아이템 포인트로 가는 다리다.
- `goldenset_items`  : 분리된 의상 아이템 1개 = 포인트 1개.
  태그 축을 products/wardrobe와 같게 맞춰 교체 후보 검색이 같은 필터 언어로
  동작한다. payload의 `outfit_point_id`로 코디를 역참조한다.
- `knowledge`        : 사람이 승인한 조건부 원칙 (텍스트 벡터만).

코디 포인트는 쌍대 비교 앵커가 없어도 만든다. 앵커 점수(`human_score` 등)는
있으면 얹는 선택 정보이지 적재 조건이 아니다 — 코디 검색이 앵커 산출보다
먼저 필요하기 때문이다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from .artifacts import read_json, read_jsonl, write_json
from .config import GoldenSettings
from .embedding import build_text_backend, load_embeddings
from .items import load_item_vectors
from .point_ids import point_id

KNOWLEDGE_COLLECTION = "knowledge"
OUTFIT_COLLECTION = "outfit_goldenset"
ITEM_COLLECTION = "goldenset_items"

#: 아이템 payload로 그대로 넘기는 태그 축 (products/wardrobe와 동일)
ITEM_TAG_FIELDS = (
    "category_large",
    "category_small",
    "layer_role",
    "color",
    "pattern",
    "fit",
    "material",
    "sleeve",
    "length",
    "season",
    "style",
)

#: 코디 payload의 아이템 요약에 담는 필드 (교체 대상 고르기에 필요한 최소치)
ITEM_SUMMARY_FIELDS = (
    "item_key",
    "item_name",
    "category_large",
    "category_small",
    "layer_role",
    "color",
    "s3_key",
)


def outfit_point_id(dataset_version: str, golden_id: str) -> str:
    return point_id(f"outfit:{dataset_version}:{golden_id}")


def item_point_id(dataset_version: str, item_key: str) -> str:
    return point_id(f"item:{dataset_version}:{item_key}")


def principle_point_id(dataset_version: str, principle_key: str) -> str:
    return point_id(f"principle:{dataset_version}:{principle_key}")


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
    version = str(run_manifest["dataset_version"])
    images = {row["golden_id"]: row for row in read_jsonl(run_dir / "images.jsonl")}
    clusters = {row["golden_id"]: row for row in read_jsonl(run_dir / "clusters.jsonl")}
    analyses = {row["golden_id"]: row for row in read_jsonl(run_dir / "analyses.jsonl")}
    approved_claims = {
        row["golden_id"]: row.get("claims", [])
        for row in read_jsonl(run_dir / "approved_claims.jsonl")
    }
    anchors = {
        row["golden_id"]: row
        for row in read_jsonl(run_dir / "anchor_scores.jsonl")
    }
    principles = read_jsonl(run_dir / "principles.jsonl")

    image_ids, image_vectors = load_embeddings(run_dir / "image_embeddings.npz")
    image_vector_map = {
        golden_id: image_vectors[index] for index, golden_id in enumerate(image_ids)
    }
    image_embedding_model = str(
        read_json(run_dir / "image_embeddings.meta.json")["model"]
    )

    item_rows = read_jsonl(run_dir / "items.jsonl")
    item_vector_map, item_text_map = _load_item_vector_maps(run_dir)
    items_by_golden: dict[str, list[dict[str, Any]]] = {}
    for row in item_rows:
        items_by_golden.setdefault(str(row["golden_id"]), []).append(row)

    text_backend = build_text_backend(settings, text_backend_name)

    # ── 코디 포인트 ──────────────────────────────────────────
    outfit_ids = [
        golden_id
        for golden_id in sorted(images)
        if golden_id in image_vector_map
        and images[golden_id].get("duplicate_kind") != "exact"
    ]
    outfit_texts = [
        _outfit_text(
            images[golden_id],
            analyses.get(golden_id, {}),
            approved_claims.get(golden_id, []),
            items_by_golden.get(golden_id, []),
        )
        for golden_id in outfit_ids
    ]
    outfit_text_vectors = text_backend.encode_texts(outfit_texts)

    outfit_points = []
    for index, golden_id in enumerate(outfit_ids):
        image = images[golden_id]
        anchor = anchors.get(golden_id, {})
        analysis = analyses.get(golden_id, {}).get("result", {})
        look_tags = analysis.get("look_tags", {})
        items = items_by_golden.get(golden_id, [])
        payload: dict[str, Any] = {
            "source": "team_golden_set",
            "dataset_version": version,
            # 데이터셋 운영 상태. 승격은 PG(GoldenDataset.status)가 관리하고
            # 여기서는 파일럿 기본값을 박는다.
            "status": str(run_manifest.get("dataset_status", "PILOT")),
            "split": image.get("split", "KNOWLEDGE"),
            "presentation_group": image.get("presentation_group", ""),
            "style": look_tags.get("style")
            or image.get("metadata", {}).get("style", []),
            "season": look_tags.get("season_cues")
            or look_tags.get("season")
            or image.get("metadata", {}).get("season", []),
            "occasion": image.get("metadata", {}).get("occasion", []),
            "rationale_ko": " | ".join(
                str(row.get("statement", ""))
                for row in approved_claims.get(golden_id, [])
            ),
            "golden_id": golden_id,
            "cluster_id": clusters.get(golden_id, {}).get("cluster_id", ""),
            "source_uri": image.get("source_uri", ""),
            "source_bucket": image.get("source_bucket", ""),
            "source_key": image.get("source_key", ""),
            # 노출 여부는 이미지별 사용권과 운영 스위치를 모두 만족해야 참이다.
            "exposable": bool(
                settings.anchor_exposable and image.get("original_exposable", False)
            ),
            "image_embedding_version": image_embedding_model,
            "text_embedding_version": text_backend.name,
            # ── 아이템으로 가는 다리 ──
            "item_count": len(items),
            "item_keys": [str(row["item_key"]) for row in items],
            "item_point_ids": [
                item_point_id(version, str(row["item_key"])) for row in items
            ],
            "item_layer_roles": sorted(
                {str(row.get("layer_role") or "") for row in items} - {""}
            ),
            "item_categories": sorted(
                {str(row.get("category_large") or "") for row in items} - {""}
            ),
            "items": [
                {field: row.get(field) for field in ITEM_SUMMARY_FIELDS}
                | {"point_id": item_point_id(version, str(row["item_key"]))}
                for row in items
            ],
        }
        if anchor:
            payload |= {
                "score_band": anchor.get("score_band", ""),
                "human_score": float(anchor.get("human_score", 0.0)),
                "score_confidence": float(anchor.get("score_confidence", 0.0)),
                "anchor_scope": anchor.get(
                    "anchor_scope", "Q_OVERALL_STYLE_EXECUTION"
                ),
                "human_axis_scores_1_5": anchor.get("human_axis_scores_1_5", {}),
                "reviewer_count": int(anchor.get("reviewer_count", 0)),
                "comparison_count": int(anchor.get("comparison_count", 0)),
                "reviewer_agreement": float(anchor.get("reviewer_agreement", 0.0)),
            }
        outfit_points.append(
            PointStruct(
                id=outfit_point_id(version, golden_id),
                vector={
                    "image": image_vector_map[golden_id].tolist(),
                    "text": outfit_text_vectors[index].tolist(),
                },
                payload=payload,
            )
        )

    # ── 아이템 포인트 ────────────────────────────────────────
    item_points = []
    for row in item_rows:
        key = str(row["item_key"])
        if row.get("status") != "SUCCEEDED":
            continue
        if key not in item_vector_map or key not in item_text_map:
            continue
        golden_id = str(row["golden_id"])
        payload = {
            "source": "team_golden_set",
            "dataset_version": version,
            "item_key": key,
            "item_index": int(row.get("item_index", 0)),
            "item_name": row.get("item_name", ""),
            "label_ko": row.get("label_ko", ""),
            "layer_order": row.get("layer_order"),
            "bbox": row.get("bbox"),
            "s3_bucket": row.get("s3_bucket", ""),
            "s3_key": row.get("s3_key", ""),
            "pipeline_key": row.get("pipeline_key", ""),
            "missing_required": row.get("missing_required", []),
            # ── 코디로 가는 역참조 ──
            "outfit_golden_id": golden_id,
            "outfit_point_id": outfit_point_id(version, golden_id),
            "split": images.get(golden_id, {}).get("split", "KNOWLEDGE"),
            "exposable": bool(
                settings.anchor_exposable
                and images.get(golden_id, {}).get("original_exposable", False)
            ),
            "image_embedding_version": row.get("image_embedding_version", ""),
            "text_embedding_version": row.get("text_embedding_version", ""),
        }
        for field in ITEM_TAG_FIELDS:
            payload[field] = row.get(field) if row.get(field) is not None else ""
        item_points.append(
            PointStruct(
                id=item_point_id(version, key),
                vector={
                    "image": item_vector_map[key].tolist(),
                    "text": item_text_map[key].tolist(),
                },
                payload=payload,
            )
        )

    # ── 원칙 포인트 ──────────────────────────────────────────
    allowed_statuses = {"APPROVED", "DRAFT"} if allow_draft else {"APPROVED"}
    eligible_principles = [
        row for row in principles if row.get("status") in allowed_statuses
    ]
    principle_vectors = text_backend.encode_texts(
        [_principle_text(row) for row in eligible_principles]
    )
    principle_points = [
        PointStruct(
            id=principle_point_id(version, row["principle_key"]),
            vector={"text": principle_vectors[index].tolist()},
            payload={
                "knowledge_type": "golden_principle",
                "dimension": row.get("axis") or row.get("dimension", ""),
                "axis": row.get("axis") or row.get("dimension", ""),
                "status": row.get("status", "DRAFT"),
                "knowledge_role": row.get("knowledge_role", "NEEDS_COUNTEREXAMPLE"),
                "principle_type": row.get("principle_type", "SOFT_PRINCIPLE"),
                "eligible_for_scoring": bool(row.get("eligible_for_scoring", False)),
                "source": "team_golden_set",
                "dataset_version": version,
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

    summary = {
        "dataset_version": version,
        "outfit_points": len(outfit_points),
        "item_points": len(item_points),
        "principle_points": len(principle_points),
        "outfits_with_anchor": sum(1 for gid in outfit_ids if gid in anchors),
        "items_without_vector": len(item_rows) - len(item_points),
        "principle_statuses": sorted(
            {str(row.get("status", "DRAFT")) for row in eligible_principles}
        ),
        "dry_run": dry_run,
        "image_embedding_version": image_embedding_model,
        "text_embedding_version": text_backend.name,
        "exposable": settings.anchor_exposable,
    }
    write_json(run_dir / "qdrant_index_plan.json", summary)
    if dry_run:
        return summary

    if text_backend.name.startswith("deterministic-") or image_embedding_model.startswith(
        "deterministic-"
    ):
        raise RuntimeError(
            "deterministic 테스트 벡터는 실제 Qdrant에 적재할 수 없습니다. "
            "FashionSigLIP·BGE-M3로 prepare/index를 다시 실행하세요."
        )

    qdrant = client or build_client()
    _assert_collections(qdrant)
    for collection, points in (
        (KNOWLEDGE_COLLECTION, principle_points),
        (OUTFIT_COLLECTION, outfit_points),
        (ITEM_COLLECTION, item_points),
    ):
        if points:
            qdrant.upsert(collection_name=collection, points=points, wait=True)
    return summary


def _load_item_vector_maps(
    run_dir: Path,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    path = run_dir / "item_embeddings.npz"
    if not path.exists():
        return {}, {}
    keys, image, text = load_item_vectors(path)
    if not keys:
        return {}, {}
    return (
        {key: image[index] for index, key in enumerate(keys)},
        {key: text[index] for index, key in enumerate(keys)},
    )


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


def _outfit_text(
    image: dict[str, Any],
    analysis: dict[str, Any],
    approved_claims: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> str:
    """코디 텍스트 벡터의 입력.

    승인된 claim이 아직 없어도(검수 전) 아이템 구성만으로 검색이 되도록
    아이템 라벨을 함께 넣는다.
    """
    result = analysis.get("result", {})
    tags = result.get("look_tags", {})
    metadata = image.get("metadata", {})
    item_text = ", ".join(
        " ".join(
            str(row.get(field) or "")
            for field in ("layer_role", "color", "category_small", "item_name")
        ).strip()
        for row in items
    )
    return "\n".join(
        [
            "스타일: "
            + ", ".join(tags.get("style", []) or metadata.get("style", [])),
            "계절 단서: "
            + ", ".join(
                tags.get("season_cues", [])
                or tags.get("season", [])
                or metadata.get("season", [])
            ),
            "상황: " + ", ".join(metadata.get("occasion", [])),
            "색상: " + ", ".join(tags.get("colors", [])),
            f"실루엣: {tags.get('overall_silhouette', '')}",
            "구성 아이템: " + item_text,
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


def build_client() -> QdrantClient:
    """환경변수로 Qdrant 클라이언트를 만든다 (index_run과 preflight 공용)."""
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
        timeout=int(os.getenv("QDRANT_TIMEOUT", "30")),
    )


def preflight(client: QdrantClient | None = None) -> None:
    """적재 전제 조건을 미리 확인한다 — 비싼 단계를 태우기 전에 부른다.

    아이템 분리는 코디 한 장당 Gemini를 여러 번 호출한다. 그 뒤에야 Qdrant를
    처음 만지면, 접속이 막혀 있거나 컬렉션이 없을 때 수십 분과 API 비용을
    전부 버리고 마지막 줄에서 죽는다. 실제로 그렇게 한 번 날렸다.
    """
    qdrant = client or build_client()
    try:
        qdrant.get_collections()
    except Exception as exc:  # noqa: BLE001 — 원인을 사람이 읽을 문장으로 바꾼다
        raise RuntimeError(
            f"Qdrant에 접속할 수 없습니다 (QDRANT_URL={os.getenv('QDRANT_URL', '(미설정)')}). "
            "GPU 호스트에서 그 주소로 실제 경로가 있는지 확인하세요 — "
            f"컨테이너 네트워크 내부 이름(http://qdrant:6333)은 다른 호스트에서 닿지 않습니다: {exc}"
        ) from exc
    _assert_collections(qdrant)


def _assert_collections(client: QdrantClient) -> None:
    missing = [
        name
        for name in (KNOWLEDGE_COLLECTION, OUTFIT_COLLECTION, ITEM_COLLECTION)
        if not client.collection_exists(name)
    ]
    if missing:
        raise RuntimeError(
            "Qdrant 컬렉션이 없습니다. 먼저 Django의 init_qdrant를 실행하세요: "
            + ", ".join(missing)
        )
