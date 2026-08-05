"""Fashion VLM 공통 프롬프트 준비와 결과 평가 도구."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent
TAXONOMY_PATH = REPO_ROOT / "api" / "apps" / "wardrobe" / "taxonomy.py"
CORE_FIELDS = ("category_large", "color", "pattern", "fit")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load_taxonomy():
    """Django를 초기화하지 않고 Wardrobe taxonomy 모듈만 읽는다."""
    spec = importlib.util.spec_from_file_location("wardrobe_taxonomy", TAXONOMY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"taxonomy를 불러올 수 없습니다: {TAXONOMY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TAXONOMY = load_taxonomy()


def load_dataset(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get("samples"), list):
        raise ValueError("dataset은 samples 배열을 가진 JSON 객체여야 합니다.")
    return data


def validate_dataset(
    data: dict[str, Any],
    *,
    image_dir: Path,
    require_images: bool = True,
    expected_count: int | None = 10,
) -> list[str]:
    errors: list[str] = []
    samples = data["samples"]
    if expected_count is not None and len(samples) != expected_count:
        errors.append(f"샘플 수가 {expected_count}장이 아닙니다: {len(samples)}장")

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    allowed = {
        "category_large": set(TAXONOMY.CATEGORY_LARGE),
        "color": set(TAXONOMY.COLORS),
        "pattern": set(TAXONOMY.PATTERNS),
        "fit": set(TAXONOMY.FITS),
    }

    for index, sample in enumerate(samples, start=1):
        prefix = f"samples[{index}]"
        if not isinstance(sample, dict):
            errors.append(f"{prefix}: 객체가 아닙니다.")
            continue
        sample_id = str(sample.get("id", "")).strip()
        file_name = str(sample.get("file_name", "")).strip()
        product_name = str(sample.get("product_name", "")).strip()
        expected = sample.get("expected")

        if not sample_id:
            errors.append(f"{prefix}: id가 비어 있습니다.")
        elif sample_id in seen_ids:
            errors.append(f"{prefix}: 중복 id입니다: {sample_id}")
        seen_ids.add(sample_id)

        if not file_name:
            errors.append(f"{prefix}: file_name이 비어 있습니다.")
        elif Path(file_name).suffix.lower() not in IMAGE_EXTENSIONS:
            errors.append(f"{prefix}: 지원하지 않는 이미지 확장자입니다: {file_name}")
        elif file_name in seen_files:
            errors.append(f"{prefix}: 중복 file_name입니다: {file_name}")
        seen_files.add(file_name)

        if require_images and file_name and not (image_dir / file_name).is_file():
            errors.append(f"{prefix}: 이미지 파일이 없습니다: {image_dir / file_name}")
        if not product_name:
            errors.append(f"{prefix}: product_name이 비어 있습니다.")
        if not isinstance(expected, dict):
            errors.append(f"{prefix}: expected가 객체가 아닙니다.")
            continue

        for field in CORE_FIELDS:
            value = expected.get(field)
            if field == "fit" and value is None:
                continue
            if value not in allowed[field]:
                errors.append(
                    f"{prefix}: expected.{field} 값이 taxonomy에 없습니다: {value!r}"
                )
    return errors


def build_prompt(product_name: str) -> str:
    def choices(values: Iterable[str]) -> str:
        return ", ".join(values)

    return f"""상품명: {product_name}

이미지의 패션 상품 한 개를 분석하세요.
반드시 아래 목록 안의 값만 사용하세요.

category_large:
{choices(TAXONOMY.CATEGORY_LARGE)}

color:
{choices(TAXONOMY.COLORS)}

pattern:
{choices(TAXONOMY.PATTERNS)}

fit:
{choices(TAXONOMY.FITS)}

규칙:
- 신발, 가방, 액세서리처럼 fit이 적용되지 않거나 이미지로 판단할 수 없으면 fit은 null입니다.
- 설명, Markdown 코드 블록, 목록을 덧붙이지 마세요.
- 다음 키를 모두 포함한 JSON 객체 하나만 답하세요.

{{
  "category_large": "",
  "color": "",
  "pattern": "",
  "fit": null
}}"""


def write_prompts(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for sample in data["samples"]:
            record = {
                "sample_id": sample["id"],
                "file_name": sample["file_name"],
                "product_name": sample["product_name"],
                "prompt": build_prompt(sample["product_name"]),
            }
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_json_object(raw_output: str) -> dict[str, Any] | None:
    text = raw_output.strip()
    decoder = json.JSONDecoder()
    for position, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[position:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: 잘못된 JSONL: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: JSON 객체가 아닙니다.")
            records.append(value)
    return records


def taxonomy_errors(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = {
        "category_large": TAXONOMY.CATEGORY_LARGE,
        "color": TAXONOMY.COLORS,
        "pattern": TAXONOMY.PATTERNS,
        "fit": TAXONOMY.FITS,
    }
    for field, choices in allowed.items():
        value = output.get(field)
        if field == "fit" and value is None:
            continue
        if value not in choices:
            errors.append(field)
    return errors


def score_results(
    dataset: dict[str, Any], result_records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected_by_id = {sample["id"]: sample["expected"] for sample in dataset["samples"]}
    rows: list[dict[str, Any]] = []

    for record in result_records:
        sample_id = record.get("sample_id")
        model = str(record.get("model", "")).strip()
        if sample_id not in expected_by_id:
            raise ValueError(f"결과에 알 수 없는 sample_id가 있습니다: {sample_id!r}")
        if not model:
            raise ValueError(f"{sample_id}: model이 비어 있습니다.")

        parsed = record.get("parsed_output")
        if not isinstance(parsed, dict):
            parsed = parse_json_object(str(record.get("raw_output", "")))
        json_valid = parsed is not None
        parsed = parsed or {}
        invalid_fields = taxonomy_errors(parsed) if json_valid else list(CORE_FIELDS)
        expected = expected_by_id[sample_id]
        field_matches = {
            field: json_valid and parsed.get(field) == expected.get(field)
            for field in CORE_FIELDS
        }
        rows.append(
            {
                "model": model,
                "sample_id": sample_id,
                "json_valid": json_valid,
                "taxonomy_valid": json_valid and not invalid_fields,
                "invalid_fields": ",".join(invalid_fields),
                **{f"{field}_match": field_matches[field] for field in CORE_FIELDS},
                "all_fields_match": all(field_matches.values()),
                "latency_seconds": record.get("latency_seconds"),
                "peak_vram_mb": record.get("peak_vram_mb"),
                "error": record.get("error") or "",
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)

    summary: dict[str, Any] = {"models": {}}
    for model, model_rows in sorted(grouped.items()):
        total = len(model_rows)
        latencies = [
            float(row["latency_seconds"])
            for row in model_rows
            if isinstance(row.get("latency_seconds"), (int, float))
        ]
        vrams = [
            float(row["peak_vram_mb"])
            for row in model_rows
            if isinstance(row.get("peak_vram_mb"), (int, float))
        ]
        metrics: dict[str, Any] = {
            "sample_count": total,
            "json_valid_rate": sum(row["json_valid"] for row in model_rows) / total,
            "taxonomy_valid_rate": sum(row["taxonomy_valid"] for row in model_rows) / total,
            "all_fields_accuracy": sum(row["all_fields_match"] for row in model_rows) / total,
            "mean_latency_seconds": statistics.fmean(latencies) if latencies else None,
            "max_peak_vram_mb": max(vrams) if vrams else None,
        }
        for field in CORE_FIELDS:
            metrics[f"{field}_accuracy"] = (
                sum(row[f"{field}_match"] for row in model_rows) / total
            )
        summary["models"][model] = metrics
    return rows, summary


def write_evaluation(
    rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path
) -> None:
    def percent(value: float) -> str:
        return f"{value * 100:.1f}%"

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fieldnames = list(rows[0]) if rows else []
    with (output_dir / "details.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)

    lines = [
        "# Fashion VLM 비교 결과",
        "",
        "| 모델 | JSON 준수 | Taxonomy 준수 | 대분류 | 색상 | 패턴 | 핏 | 완전 일치 | 평균 시간(초) | 최대 VRAM(MB) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, metrics in summary["models"].items():
        latency = metrics["mean_latency_seconds"]
        vram = metrics["max_peak_vram_mb"]
        lines.append(
            "| {model} | {json_rate} | {taxonomy_rate} | {category} | {color} | "
            "{pattern} | {fit} | {all_fields} | {latency} | {vram} |".format(
                model=model,
                json_rate=percent(metrics["json_valid_rate"]),
                taxonomy_rate=percent(metrics["taxonomy_valid_rate"]),
                category=percent(metrics["category_large_accuracy"]),
                color=percent(metrics["color_accuracy"]),
                pattern=percent(metrics["pattern_accuracy"]),
                fit=percent(metrics["fit_accuracy"]),
                all_fields=percent(metrics["all_fields_accuracy"]),
                latency=f"{latency:.3f}" if latency is not None else "-",
                vram=f"{vram:.0f}" if vram is not None else "-",
            )
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def command_validate(args: argparse.Namespace) -> None:
    data = load_dataset(Path(args.dataset))
    errors = validate_dataset(
        data,
        image_dir=Path(args.images),
        require_images=not args.allow_missing_images,
    )
    if errors:
        raise SystemExit("데이터셋 검증 실패:\n- " + "\n- ".join(errors))
    print(f"데이터셋 검증 성공: {len(data['samples'])}장")


def command_prepare(args: argparse.Namespace) -> None:
    data = load_dataset(Path(args.dataset))
    errors = validate_dataset(data, image_dir=Path(args.images))
    if errors:
        raise SystemExit("데이터셋 검증 실패:\n- " + "\n- ".join(errors))
    write_prompts(data, Path(args.output))
    print(f"공통 프롬프트 생성 완료: {args.output}")


def command_evaluate(args: argparse.Namespace) -> None:
    dataset = load_dataset(Path(args.dataset))
    records: list[dict[str, Any]] = []
    for result_path in args.results:
        records.extend(load_jsonl(Path(result_path)))
    rows, summary = score_results(dataset, records)
    write_evaluation(rows, summary, Path(args.output_dir))
    print(f"평가 완료: {len(rows)}건 → {args.output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="이미지와 정답지 검증")
    validate.add_argument("--dataset", default=str(ROOT / "dataset.json"))
    validate.add_argument("--images", default=str(ROOT / "images"))
    validate.add_argument("--allow-missing-images", action="store_true")
    validate.set_defaults(func=command_validate)

    prepare = subparsers.add_parser("prepare", help="모델 공통 prompts.jsonl 생성")
    prepare.add_argument("--dataset", default=str(ROOT / "dataset.json"))
    prepare.add_argument("--images", default=str(ROOT / "images"))
    prepare.add_argument("--output", default=str(ROOT / "prompts.jsonl"))
    prepare.set_defaults(func=command_prepare)

    evaluate = subparsers.add_parser("evaluate", help="모델 결과 비교표 생성")
    evaluate.add_argument("--dataset", default=str(ROOT / "dataset.json"))
    evaluate.add_argument("--results", nargs="+", required=True)
    evaluate.add_argument("--output-dir", default=str(ROOT / "results" / "evaluation"))
    evaluate.set_defaults(func=command_evaluate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
