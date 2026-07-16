#!/usr/bin/env python3
"""
JSON 스키마 검증 — 룰 JSON 파일이 유효한지, 파일별 필수 필드가 있는지 검사.

각 룰 파일은 객체 배열이어야 하며, 파일명에 매칭되는 스키마(RULE_SCHEMA)의
필수 필드 존재·"id" 필드 존재·id 의 snake_case(공백 없음) 여부를 확인한다.

파이프라인에서의 위치:
    n8n 워크플로2(정제/검증)의 검증 노드에서 호출.
    clean_encoding.py(UTF-8 정제) 다음 단계로, 정제된 룰 JSON의 구조를 최종 검증한다.
    stats.failed 로 노드 성공/실패를 판정한다.

입력(인자):
    --input   검증할 단일 JSON 파일
    --batch   검증할 파일 경로 목록(JSON 배열 파일)

출력:
    - stdout: {"stats": {"total","passed","failed"}, "files": [...]} JSON 리포트
    - stderr: 파일별 "PASS/FAIL: <파일명>" 진행 로그
    - stats.failed > 0 이면 종료 코드 1

실행 예시(컨테이너 안):
    python3 /repo/data/pipeline/scripts/validate_json.py --batch /tmp/paths.json
    python3 /repo/data/pipeline/scripts/validate_json.py --input /tmp/style_definitions.json
"""

import argparse
import json
import sys
from pathlib import Path


# 기본 룰 JSON 스키마 검증 규칙
RULE_SCHEMA = {
    "weather_outfit_rules.json": ["id", "temperature_range", "description", "required_items"],
    "tpo_outfit_rules.json": ["id", "tpo", "description", "recommended_tops", "recommended_bottoms"],
    "style_definitions.json": ["id", "style_name", "description", "keywords"],
    "color_matching_rules.json": ["id", "skin_tone_group", "description", "best_colors", "avoid_colors"],
    "item_combination_rules.json": ["id", "combination_type", "description", "compatible_tops", "compatible_bottoms"],
}


def validate_json_file(path: Path, filename: str) -> dict:
    """JSON 파일 검증"""
    result = {"file": str(path), "valid": True, "errors": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["errors"].append(f"JSON parse error: {e}")
        return result

    if not isinstance(data, list):
        result["errors"].append("Root should be an array")
        result["valid"] = False
        return result

    # Check schema based on filename
    required_fields = None
    for schema_name, fields in RULE_SCHEMA.items():
        if schema_name in filename:
            required_fields = fields
            break

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            result["errors"].append(f"[{i}] Item is not an object")
            result["valid"] = False
            continue

        if required_fields:
            for field in required_fields:
                if field not in item:
                    result["errors"].append(f"[{i}] Missing required field: {field}")

        # id field check
        if "id" not in item:
            result["errors"].append(f"[{i}] Missing 'id' field")
            result["valid"] = False

        # snake_case id check
        if "id" in item and " " in item["id"]:
            result["errors"].append(f"[{i}] id contains spaces (should be snake_case): {item['id']}")

    return result


def validate_batch(paths: list[Path]) -> dict:
    """배치 검증"""
    results = []
    for path in paths:
        filename = path.name
        result = validate_json_file(path, filename)
        results.append(result)
        status = "PASS" if result["valid"] else "FAIL"
        print(f"{status}: {filename}", file=sys.stderr)

    stats = {
        "total": len(results),
        "passed": sum(1 for r in results if r["valid"]),
        "failed": sum(1 for r in results if not r["valid"]),
    }
    return {"stats": stats, "files": results}


def main():
    """인자 파싱 → 단일/배치 검증 실행 → JSON 리포트 출력, 실패 있으면 종료 코드 1."""
    parser = argparse.ArgumentParser(description="JSON 스키마 검증")
    parser.add_argument("--input", help="Single JSON file to validate")
    parser.add_argument("--batch", help="JSON file with list of file paths to validate")
    args = parser.parse_args()

    if args.batch:
        paths = [Path(p) for p in json.loads(Path(args.batch).read_text(encoding="utf-8"))]
        result = validate_batch(paths)
    elif args.input:
        result = validate_json_file(Path(args.input), Path(args.input).name)
        result = {"stats": {"total": 1, "passed": 1 if result["valid"] else 0, "failed": 0 if result["valid"] else 1}, "files": [result]}
    else:
        print("ERROR: --input or --batch required", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["stats"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
