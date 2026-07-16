#!/usr/bin/env python3
"""
인코딩 정제 — EUC-KR/CP949 등으로 저장된 텍스트/JSON 파일을 UTF-8(BOM 제거)로 변환.

S3 다운로드/정제/재업로드까지 담당한다(설계 문서 기준).
배치 입력은 S3 키 목록(JSON 배열) 또는 로컬 파일 경로 목록을 받는다.
로컬에 없는 경로는 S3 키로 간주해 `aws s3 cp` 로 내려받아 처리하고,
--upload 지정 시 정제 결과를 같은 키로 다시 올린다.

파이프라인에서의 위치:
    n8n 워크플로2(정제/검증)의 인코딩 정제 노드에서 호출.
    같은 워크플로의 validate_json.py(검증) 앞 단계로, 여기서 UTF-8 정규화를 끝낸 뒤
    검증으로 넘어간다. stats.error 로 노드 성공/실패를 판정한다.

입력(인자):
    --batch     정제할 S3 키 또는 로컬 경로 목록(JSON 배열 파일)
    --input     정제할 단일 로컬 파일
    --s3-key    --input 파일을 재업로드할 S3 키 (--upload 와 함께)
    --work-dir  S3 다운로드 임시 디렉토리 (기본: /tmp/clean_work)
    --upload    정제 결과를 S3에 재업로드

출력(stdout): {"stats": {"total","success","error","skipped"}, "files": [...]} 형태의 JSON 리포트.
    stats.error > 0 이면 종료 코드 1로 실패를 알린다.

실행 예시(컨테이너 안):
    python3 /repo/data/pipeline/scripts/clean_encoding.py --batch /tmp/keys.json --upload
    python3 /repo/data/pipeline/scripts/clean_encoding.py --input /tmp/rules.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 텍스트로 취급해 인코딩을 변환할 확장자
TEXT_EXTS = {".json", ".txt", ".csv", ".md", ".tsv"}

# UTF-8 실패 시 시도할 후보 인코딩(한국어 데이터 우선순위)
FALLBACK_ENCODINGS = ["utf-8-sig", "cp949", "euc-kr", "latin-1"]

BUCKET = "skn28-cozy"


def s3_download(key: str, dest: Path) -> bool:
    """S3에서 로컬로 다운로드. 성공 시 True."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["aws", "s3", "cp", f"s3://{BUCKET}/{key}", str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: s3 download failed for {key}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def s3_upload(src: Path, key: str) -> bool:
    """정제된 파일을 S3에 재업로드. 성공 시 True."""
    cmd = ["aws", "s3", "cp", str(src), f"s3://{BUCKET}/{key}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: s3 upload failed for {key}: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def detect_and_read(path: Path) -> tuple[str, str]:
    """파일을 여러 인코딩으로 시도해 읽는다. (text, detected_encoding) 반환."""
    raw = path.read_bytes()
    # 우선 순수 UTF-8 시도
    for enc in ["utf-8", *FALLBACK_ENCODINGS]:
        try:
            text = raw.decode(enc)
            return text, enc
        except (UnicodeDecodeError, LookupError):
            continue
    # 마지막 안전망: 대체 문자 허용 디코드
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def clean_file(path: Path) -> dict:
    """단일 로컬 파일을 UTF-8(BOM 없음)로 정규화. 변환 여부 리포트 반환."""
    if path.suffix.lower() not in TEXT_EXTS:
        return {"file": str(path), "status": "skipped", "reason": "non-text extension"}

    try:
        text, enc = detect_and_read(path)
    except Exception as e:  # noqa: BLE001 - 어떤 IO 오류든 error 로 집계
        return {"file": str(path), "status": "error", "error": str(e)}

    # BOM 제거 및 UTF-8 재작성
    if text.startswith("﻿"):
        text = text.lstrip("﻿")

    # JSON 이면 파싱 가능한지까지 확인(깨진 인코딩 조기 발견)
    if path.suffix.lower() == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            return {
                "file": str(path),
                "status": "error",
                "error": f"JSON invalid after decode ({enc}): {e}",
            }

    try:
        path.write_text(text, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"file": str(path), "status": "error", "error": str(e)}

    return {
        "file": str(path),
        "status": "success",
        "source_encoding": enc,
        "converted": enc not in ("utf-8",),
    }


def process_key(entry: str, work_dir: Path, upload: bool) -> dict:
    """배치 항목 하나 처리: 로컬 경로면 그대로, 아니면 S3 키로 다운로드."""
    local = Path(entry)
    is_s3 = not local.exists()

    if is_s3:
        dest = work_dir / entry.lstrip("/")
        if not s3_download(entry, dest):
            return {"file": entry, "status": "error", "error": "s3 download failed"}
        target = dest
    else:
        target = local

    report = clean_file(target)
    report["s3_key"] = entry if is_s3 else None

    if upload and is_s3 and report.get("status") == "success":
        if not s3_upload(target, entry):
            report["status"] = "error"
            report["error"] = "s3 upload failed"

    return report


def build_stats(reports: list[dict]) -> dict:
    """리포트 목록을 total/success/error/skipped 카운트로 집계."""
    return {
        "total": len(reports),
        "success": sum(1 for r in reports if r.get("status") == "success"),
        "error": sum(1 for r in reports if r.get("status") == "error"),
        "skipped": sum(1 for r in reports if r.get("status") == "skipped"),
    }


def main():
    """인자 파싱 → 배치/단일 정제 실행 → JSON 리포트 출력, 에러 있으면 종료 코드 1."""
    parser = argparse.ArgumentParser(description="인코딩 정제 (EUC-KR/CP949 → UTF-8)")
    parser.add_argument("--batch", help="정제할 S3 키 또는 로컬 경로 목록(JSON 배열 파일)")
    parser.add_argument("--input", help="정제할 단일 로컬 파일")
    parser.add_argument("--s3-key", help="--input 파일을 재업로드할 S3 키(--upload 와 함께)")
    parser.add_argument("--work-dir", default="/tmp/clean_work", help="S3 다운로드 임시 디렉토리")
    parser.add_argument("--upload", action="store_true", help="정제 결과를 S3에 재업로드")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)

    if args.batch:
        entries = json.loads(Path(args.batch).read_text(encoding="utf-8"))
        reports = [process_key(str(e), work_dir, args.upload) for e in entries]
    elif args.input:
        report = clean_file(Path(args.input))
        if args.upload and args.s3_key and report.get("status") == "success":
            if not s3_upload(Path(args.input), args.s3_key):
                report["status"] = "error"
                report["error"] = "s3 upload failed"
        reports = [report]
    else:
        print("ERROR: --input 또는 --batch 필요", file=sys.stderr)
        sys.exit(1)

    result = {"stats": build_stats(reports), "files": reports}
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["stats"]["error"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
