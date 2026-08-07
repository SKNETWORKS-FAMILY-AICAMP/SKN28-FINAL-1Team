"""골든 이미지 파일을 안정적인 manifest로 변환한다."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .artifacts import write_json, write_jsonl

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def difference_hash(path: Path, *, size: int = 8) -> str:
    """EXIF 방향을 반영한 64비트 dHash."""
    with Image.open(path) as image:
        gray = ImageOps.exif_transpose(image).convert("L").resize((size + 1, size))
        # Pillow 14에서 getdata()가 제거될 예정이라 새 API를 우선 사용한다.
        flattened = getattr(gray, "get_flattened_data", gray.getdata)
        pixels = list(flattened())
    bits = []
    for y in range(size):
        start = y * (size + 1)
        bits.extend(pixels[start + x] > pixels[start + x + 1] for x in range(size))
    value = sum(int(bit) << index for index, bit in enumerate(bits))
    return f"{value:0{size * size // 4}x}"


def hamming_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _clean_id(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value.strip()).strip("-")
    return cleaned[:64] or "golden"


def _read_metadata(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = (row.get("file_name") or row.get("golden_id") or "").strip()
        if not key:
            raise ValueError("metadata CSV에는 file_name 또는 golden_id가 필요합니다.")
        result[key] = {str(k): str(v or "").strip() for k, v in row.items()}
    return result


def _metadata_for(
    path: Path,
    metadata: dict[str, dict[str, str]],
) -> dict[str, str]:
    return metadata.get(path.name) or metadata.get(path.stem) or {}


def build_manifest(
    *,
    input_dir: Path,
    run_dir: Path,
    dataset_name: str,
    dataset_version: str,
    metadata_csv: Path | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    paths = sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if limit is not None:
        paths = paths[:limit]
    if not paths:
        raise ValueError(f"이미지를 찾을 수 없습니다: {input_dir}")

    metadata = _read_metadata(metadata_csv)
    used_ids: set[str] = set()
    exact_seen: dict[str, str] = {}
    perceptual_seen: list[tuple[str, str]] = []
    rows: list[dict[str, Any]] = []

    for index, path in enumerate(paths, start=1):
        meta = _metadata_for(path, metadata)
        base_id = _clean_id(meta.get("golden_id") or path.stem)
        golden_id = base_id
        suffix = 2
        while golden_id in used_ids:
            golden_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(golden_id)

        image_sha = sha256_file(path)
        perceptual = difference_hash(path)
        duplicate_of = exact_seen.get(image_sha, "")
        duplicate_kind = "exact" if duplicate_of else ""
        if not duplicate_of:
            near = next(
                (
                    prior_id
                    for prior_id, prior_hash in perceptual_seen
                    if hamming_distance(perceptual, prior_hash) <= 4
                ),
                "",
            )
            if near:
                duplicate_of = near
                duplicate_kind = "near"
        exact_seen.setdefault(image_sha, golden_id)
        perceptual_seen.append((golden_id, perceptual))

        source_uri = meta.get("source_uri") or str(path.resolve())
        rows.append(
            {
                "golden_id": golden_id,
                "local_path": str(path.resolve()),
                "source_uri": source_uri,
                "source_name": meta.get("source", ""),
                "usage_scope": meta.get("usage_scope", "UNKNOWN").upper(),
                "original_exposable": meta.get("original_exposable", "").lower()
                in {"1", "true", "yes", "y"},
                "image_sha256": image_sha,
                "perceptual_hash": perceptual,
                "duplicate_of": duplicate_of,
                "duplicate_kind": duplicate_kind,
                "split": meta.get("split", "KNOWLEDGE").upper(),
                "presentation_group": meta.get("presentation_group", ""),
                "metadata": {
                    "style": _split_values(meta.get("style", "")),
                    "season": _split_values(meta.get("season", "")),
                    "occasion": _split_values(meta.get("occasion", "")),
                    "selection_reason": meta.get("selection_reason", ""),
                    "same_shoot_group": meta.get("same_shoot_group", ""),
                },
                "order": index,
            }
        )

    run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "images.jsonl", rows)
    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_dir.name,
            "dataset_name": dataset_name,
            "dataset_version": dataset_version,
            "status": "PREPARED",
            "num_images": len(rows),
            "num_exact_duplicates": sum(
                row["duplicate_kind"] == "exact" for row in rows
            ),
            "num_near_duplicates": sum(row["duplicate_kind"] == "near" for row in rows),
        },
    )
    return rows


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;,|]", value) if item.strip()]
