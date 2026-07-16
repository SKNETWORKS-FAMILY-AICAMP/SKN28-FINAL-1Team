#!/usr/bin/env python3
"""
S3 인벤토리 스캔 — 버킷(skn28-cozy)의 신규/변경/삭제 파일 감지.

`aws s3 ls --recursive` 출력을 파싱해서 이전 스캔 상태(state-file)와 비교(diff)한다.
파이프라인의 시작점으로, 신규/변경 파일이 있을 때만 이후 정제·임베딩 단계를 트리거한다.

파이프라인에서의 위치:
    n8n 워크플로1(감지)의 스캔 노드에서 호출. stdout 마지막 줄의
    "NEW_OR_MODIFIED:true|false" 로 다음 워크플로 실행 여부를 분기한다.

입력(인자):
    --prefix      스캔할 S3 prefix (기본: 버킷 루트)
    --output      결과 리포트를 쓸 JSON 경로 (기본: /tmp/s3_inventory.json)
    --state-file  직전 스캔 상태 파일 경로 (diff 기준, 기본: /tmp/s3_previous_inventory.json)

출력:
    - --output 경로에 {scanned_at, prefix, total_files, diff, all_files} JSON 저장
    - --state-file 을 이번 스캔 결과로 갱신
    - stdout: 요약 카운트 + "NEW_OR_MODIFIED:true|false" (n8n 분기용)

실행 예시(컨테이너 안):
    python3 /repo/data/pipeline/scripts/s3_scan.py \\
        --prefix rules/ --output /tmp/s3_inventory.json --state-file /tmp/s3_prev.json
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))


def run_aws_ls(prefix: str) -> list[dict]:
    """aws s3 ls --recursive 결과를 파싱"""
    cmd = ["aws", "s3", "ls", f"s3://skn28-cozy/{prefix}", "--recursive"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(f"ERROR: aws s3 ls failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        # Format: "2024-01-15 10:30:45    1234567 path/to/file.jpg"
        parts = line.split(maxsplit=3)
        if len(parts) < 4:
            continue
        date_str, time_str, size, key = parts
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        files.append({
            "key": key,
            "size": int(size),
            "modified": dt.replace(tzinfo=KST).isoformat(),
        })
    return files


def load_previous_scan(path: Path) -> dict:
    """직전 스캔 상태 파일을 읽는다. 없으면 빈 상태 반환."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"files": [], "scanned_at": None}


def diff_files(previous: list[dict], current: list[dict]) -> dict:
    """이전/현재 파일 목록을 비교해 신규/삭제/변경(크기 기준)으로 분류."""
    prev_keys = {f["key"]: f for f in previous}
    curr_keys = {f["key"]: f for f in current}

    new_keys = set(curr_keys) - set(prev_keys)
    removed_keys = set(prev_keys) - set(curr_keys)
    modified_keys = {
        k for k in set(curr_keys) & set(prev_keys)
        if prev_keys[k]["size"] != curr_keys[k]["size"]
    }

    return {
        "new": [curr_keys[k] for k in new_keys],
        "removed": [prev_keys[k] for k in removed_keys],
        "modified": [curr_keys[k] for k in modified_keys],
    }


def main():
    """스캔 실행 → diff 계산 → 리포트/상태 저장 → n8n 분기 플래그 출력."""
    parser = argparse.ArgumentParser(description="S3 인벤토리 스캔 및 diff")
    parser.add_argument("--prefix", default="", help="S3 prefix to scan")
    parser.add_argument("--output", default="/tmp/s3_inventory.json", help="Output JSON path")
    parser.add_argument("--state-file", default="/tmp/s3_previous_inventory.json", help="Previous scan state file")
    args = parser.parse_args()

    state_file = Path(args.state_file)
    previous = load_previous_scan(state_file)
    current = run_aws_ls(args.prefix)

    diff = diff_files(previous.get("files", []), current)

    now = datetime.now(tz=KST).isoformat()
    result = {
        "scanned_at": now,
        "prefix": args.prefix,
        "total_files": len(current),
        "diff": diff,
        "all_files": current,
    }

    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    state_file.write_text(json.dumps({"files": current, "scanned_at": now}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Total files: {len(current)}")
    print(f"New: {len(diff['new'])}, Removed: {len(diff['removed'])}, Modified: {len(diff['modified'])}")

    if diff["new"] or diff["modified"]:
        print("NEW_OR_MODIFIED:true")
        sys.exit(0)
    else:
        print("NEW_OR_MODIFIED:false")
        sys.exit(0)


if __name__ == "__main__":
    main()
