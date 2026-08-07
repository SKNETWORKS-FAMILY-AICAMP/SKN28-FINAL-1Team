"""골든셋 파일럿 전체 사이클 CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import analyze_run
from .anchors import build_anchor_scores
from .artifacts import read_json, write_json
from .clustering import cluster_embeddings
from .config import GoldenSettings, load_project_env
from .embedding import embed_manifest_images
from .manifest import build_manifest
from .principles import apply_principle_reviews, synthesize_principles
from .qdrant_index import index_run
from .review import collect_accepted_claims, create_review_templates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="골든 이미지 → 판단 원칙(메인) + 점수 앵커(보조) 파일럿"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="manifest·임베딩·클러스터 생성")
    prepare.add_argument("--input-dir", type=Path, required=True)
    prepare.add_argument("--run-dir", type=Path, required=True)
    prepare.add_argument("--dataset-name", required=True)
    prepare.add_argument("--dataset-version", required=True)
    prepare.add_argument("--metadata-csv", type=Path)
    prepare.add_argument("--limit", type=int)
    prepare.add_argument(
        "--embedding-backend",
        choices=["fashion", "deterministic"],
        default="fashion",
    )
    prepare.add_argument("--clusters", type=int)

    analyze = subparsers.add_parser("analyze", help="대표 이미지 통합 분석")
    analyze.add_argument("--run-dir", type=Path, required=True)
    analyze.add_argument(
        "--all", action="store_true", help="대표·경계가 아닌 이미지도 분석"
    )

    templates = subparsers.add_parser("templates", help="사람 검수 CSV 생성")
    templates.add_argument("--run-dir", type=Path, required=True)
    templates.add_argument("--pair-count", type=int, default=12)

    validate_reviews = subparsers.add_parser(
        "validate-reviews",
        help="2인 관찰·claim 검수 범위와 불일치 확인",
    )
    validate_reviews.add_argument("--run-dir", type=Path, required=True)
    validate_reviews.add_argument(
        "--observation-reviews", type=Path, required=True
    )
    validate_reviews.add_argument("--claim-reviews", type=Path, required=True)

    fit_anchors = subparsers.add_parser(
        "fit-anchors",
        help="비교 가능한 2인 쌍대 검수로 보조 Q 앵커 계산",
    )
    fit_anchors.add_argument("--run-dir", type=Path, required=True)
    fit_anchors.add_argument("--pairwise-reviews", type=Path, required=True)
    fit_anchors.add_argument("--observation-reviews", type=Path)

    synthesize = subparsers.add_parser(
        "synthesize-principles",
        help="2인 승인 claim만으로 조건부 원칙 초안 합성",
    )
    synthesize.add_argument("--run-dir", type=Path, required=True)
    synthesize.add_argument("--observation-reviews", type=Path, required=True)
    synthesize.add_argument("--claim-reviews", type=Path, required=True)

    finalize = subparsers.add_parser(
        "finalize",
        help="호환 명령: 검수 후 앵커 계산과 원칙 합성을 순서대로 실행",
    )
    finalize.add_argument("--run-dir", type=Path, required=True)
    finalize.add_argument("--observation-reviews", type=Path, required=True)
    finalize.add_argument("--claim-reviews", type=Path, required=True)
    finalize.add_argument("--pairwise-reviews", type=Path, required=True)

    approve = subparsers.add_parser("approve", help="원칙 2인 검수 결과 반영")
    approve.add_argument("--run-dir", type=Path, required=True)
    approve.add_argument("--principle-reviews", type=Path, required=True)

    index = subparsers.add_parser("index", help="Qdrant 파생 컬렉션 적재")
    index.add_argument("--run-dir", type=Path, required=True)
    index.add_argument(
        "--text-backend",
        choices=["bge", "deterministic"],
        default="bge",
    )
    index.add_argument("--allow-draft", action="store_true")
    index.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    load_project_env()
    settings = GoldenSettings.from_env()

    if args.command == "prepare":
        build_manifest(
            input_dir=args.input_dir,
            run_dir=args.run_dir,
            dataset_name=args.dataset_name,
            dataset_version=args.dataset_version,
            metadata_csv=args.metadata_csv,
            limit=args.limit,
        )
        _, _, model_name = embed_manifest_images(
            run_dir=args.run_dir,
            settings=settings,
            backend_name=args.embedding_backend,
        )
        cluster_embeddings(run_dir=args.run_dir, cluster_count=args.clusters)
        manifest = read_json(args.run_dir / "run_manifest.json")
        manifest.update({"image_embedding_version": model_name, "status": "CLUSTERED"})
        write_json(args.run_dir / "run_manifest.json", manifest)
        print(f"준비 완료: {args.run_dir}")
    elif args.command == "analyze":
        results = analyze_run(
            run_dir=args.run_dir,
            settings=settings,
            analyze_all=args.all,
        )
        print(f"분석 갱신: {len(results)}건")
    elif args.command == "templates":
        paths = create_review_templates(
            run_dir=args.run_dir,
            pair_count=args.pair_count,
        )
        print(f"관찰 검수표: {paths.observation}")
        print(f"claim 검수표: {paths.claim}")
        print(f"최소 수정 검수표: {paths.minimum_edit}")
        print(f"쌍대 비교표: {paths.pairwise}")
        print(f"검수 가이드: {paths.guide}")
    elif args.command == "validate-reviews":
        _, report = collect_accepted_claims(
            observation_reviews_csv=args.observation_reviews,
            claim_reviews_csv=args.claim_reviews,
            run_dir=args.run_dir,
        )
        print(report)
    elif args.command == "fit-anchors":
        anchors = build_anchor_scores(
            pairwise_csv=args.pairwise_reviews,
            observation_reviews_csv=args.observation_reviews,
            run_dir=args.run_dir,
        )
        print(f"점수 앵커: {len(anchors)}건")
    elif args.command == "synthesize-principles":
        principles = synthesize_principles(
            run_dir=args.run_dir,
            observation_reviews_csv=args.observation_reviews,
            claim_reviews_csv=args.claim_reviews,
            settings=settings,
        )
        print(f"원칙 초안: {len(principles)}건")
        print(f"원칙 검수표: {args.run_dir / 'principle_reviews.template.csv'}")
    elif args.command == "finalize":
        anchors = build_anchor_scores(
            pairwise_csv=args.pairwise_reviews,
            observation_reviews_csv=args.observation_reviews,
            run_dir=args.run_dir,
        )
        principles = synthesize_principles(
            run_dir=args.run_dir,
            observation_reviews_csv=args.observation_reviews,
            claim_reviews_csv=args.claim_reviews,
            settings=settings,
        )
        print(f"점수 앵커: {len(anchors)}건")
        print(f"원칙 초안: {len(principles)}건")
        print(f"원칙 검수표: {args.run_dir / 'principle_reviews.template.csv'}")
    elif args.command == "approve":
        principles = apply_principle_reviews(
            run_dir=args.run_dir,
            principle_reviews_csv=args.principle_reviews,
        )
        approved_count = sum(row.get("status") == "APPROVED" for row in principles)
        print(f"원칙 검수 반영: {len(principles)}건, 승인 {approved_count}건")
    elif args.command == "index":
        summary = index_run(
            run_dir=args.run_dir,
            settings=settings,
            text_backend_name=args.text_backend,
            allow_draft=args.allow_draft,
            dry_run=args.dry_run,
        )
        print(summary)


if __name__ == "__main__":
    main()
