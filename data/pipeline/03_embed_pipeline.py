#!/usr/bin/env python3
"""
임베딩 파이프라인 — S3 이미지를 내려받아 Marqo-FashionSigLIP 인덱스에 임베딩 적재.

S3 키 목록을 받아 이미지 확장자(.jpg/.jpeg/.png/.webp)만 다운로드한 뒤,
로컬 Marqo 서버(http://localhost:8888)의 인덱스에 배치로 add_documents 하여
이미지+텍스트 임베딩을 생성·저장한다.

파이프라인에서의 위치:
    n8n 워크플로3(임베딩)의 임베딩 노드에서 호출.
    워크플로1의 스캔 결과로 선별된 신규/변경 이미지 키 목록을 입력으로 받아 벡터화한다.

입력(인자):
    --keys           임베딩할 S3 키 목록(JSON 배열 파일) [필수]
    --collection     Marqo/Qdrant 인덱스(컬렉션) 이름 (기본: fashion_items)
    --batch-size     임베딩 배치 크기 (기본: 32)
    --output-dir     이미지 다운로드 임시 디렉토리 (기본: /tmp/embed_images)
    --download-only  임베딩 없이 다운로드만 수행

출력(stdout):
    - 일반: {"total","success","failed"} 임베딩 결과 JSON
    - --download-only: {"downloaded","total_keys"} JSON
    - 진행 로그는 stderr

실행 예시(컨테이너 안):
    python3 /repo/data/pipeline/scripts/embed_pipeline.py --keys /tmp/img_keys.json \\
        --collection fashion_items

Dependencies:
    pip install marqo torch pillow requests
    # Or: uv pip install marqo torch pillow requests
"""

import argparse
import hashlib
import json
import sys
import subprocess
from pathlib import Path

try:
    import marqo
except ImportError:
    marqo = None


DEFAULT_COLLECTION = "fashion_items"
EMBED_BATCH_SIZE = 32


def generate_record_id(s3_key: str) -> str:
    """S3 키에서 deterministic hash ID 생성"""
    return hashlib.sha256(s3_key.encode()).hexdigest()[:16]


def embed_image(image_path: Path, client, index_name: str) -> dict:
    """단일 이미지 임베딩 (Marqo-FashionSigLIP)"""
    try:
        result = client.index(index_name).add_documents([
            {"image_path": str(image_path), "s3_key": str(image_path)}
        ])
        return {"status": "success", "path": str(image_path)}
    except Exception as e:
        return {"status": "error", "path": str(image_path), "error": str(e)}


def embed_batch(image_paths: list[Path], collection: str) -> dict:
    """배치 임베딩 처리"""
    if marqo is None:
        return {"error": "marqo not installed. Run: uv pip install marqo"}

    client = marqo.Client(url="http://localhost:8888")  # Marqo default port

    results = []
    for i in range(0, len(image_paths), EMBED_BATCH_SIZE):
        batch = image_paths[i:i + EMBED_BATCH_SIZE]
        batch_results = []
        for path in batch:
            r = embed_image(path, client, collection)
            batch_results.append(r)
        results.extend(batch_results)
        print(f"Processed {min(i + EMBED_BATCH_SIZE, len(image_paths))}/{len(image_paths)}", file=sys.stderr)

    return {
        "total": len(results),
        "success": sum(1 for r in results if r.get("status") == "success"),
        "failed": sum(1 for r in results if r.get("status") == "error"),
    }


def download_images_from_s3(keys: list[str], output_dir: Path) -> list[Path]:
    """S3에서 이미지 다운로드"""
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for key in keys:
        if not any(key.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            continue
        local_path = output_dir / Path(key).name
        cmd = ["aws", "s3", "cp", f"s3://skn28-cozy/{key}", str(local_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            downloaded.append(local_path)
        else:
            print(f"Failed to download: {key}", file=sys.stderr)
    return downloaded


def main():
    """S3 이미지 다운로드 → (옵션에 따라) Marqo 인덱스에 배치 임베딩 → 결과 JSON 출력."""
    parser = argparse.ArgumentParser(description="FashionSigLIP 임베딩 파이프라인")
    parser.add_argument("--keys", required=True, help="JSON file with list of S3 keys to embed")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Qdrant collection name")
    parser.add_argument("--batch-size", type=int, default=EMBED_BATCH_SIZE, help="Batch size for embedding")
    parser.add_argument("--output-dir", default="/tmp/embed_images", help="Temp image download directory")
    parser.add_argument("--download-only", action="store_true", help="Download images without embedding")
    args = parser.parse_args()

    keys = json.loads(Path(args.keys).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)

    print(f"Downloading {len(keys)} files from S3...", file=sys.stderr)
    image_paths = download_images_from_s3(keys, output_dir)
    print(f"Downloaded {len(image_paths)} images", file=sys.stderr)

    if args.download_only:
        result = {"downloaded": len(image_paths), "total_keys": len(keys)}
        print(json.dumps(result))
        return

    print(f"Embedding {len(image_paths)} images into collection '{args.collection}'...", file=sys.stderr)
    result = embed_batch(image_paths, args.collection)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
