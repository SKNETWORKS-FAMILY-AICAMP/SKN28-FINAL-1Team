#!/usr/bin/env python3
"""
날씨별 코디 룰 검증/보강 — data/weather/weather_outfit_rules.json 데이터 기반 정제.

기존 11개 손작성 룰을 보존하면서 (a) 누락된 기온 구간 보강, (b) KMA 코드 매핑 정합성 검증,
(c) 비어있는 배열 필드 채우기, (d) kma_fields 키 일관성 보강을 수행한다.

파이프라인에서의 위치:
    n8n 워크플로4(weather_rules_build)의 Execute Command 노드에서 호출.
    기존 룰(JSON) → 검증 + 보강 → 덮어쓰기 또는 dry-run 으로 검증 리포트만 출력.
    stats.error > 0 이면 종료 코드 1로 실패를 알린다.

입력(인자):
    --input   원본 룰 JSON 경로 (기본: /repo/data/weather/weather_outfit_rules.json)
    --output  결과 룰 JSON 경로 (기본: --input 과 동일)
    --apply   실제 파일 쓰기 (기본: dry-run, stdout 으로만 출력)
    --backup  --apply 시 .bak 단일 백업 생성 (기본: true)

출력(stdout): {"stats": {...}, "rules": [...] } 형태의 JSON 리포트.
    --apply 면 동시에 output 파일에 덮어쓰기 + .bak 백업.

실행 예시(컨테이너 안):
    python3 /repo/data/pipeline/scripts/build_weather_rules.py --dry-run
    python3 /repo/data/pipeline/scripts/build_weather_rules.py --apply --backup
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# ---------- 표준 KMA 코드북 (기상청 단기예보 공식 코드) ----------
# PTY(강수형태): 0=없음, 1=비, 2=진눈깨비, 3=눈, 4=소나기, 5=빗방울, 6=빗방울눈날림, 7=눈날림
# 운영상 흔히 쓰이는 확장 키 5="소낙눈" 은 5="빗방울"과 혼동되므로 둘 다 보존.
STANDARD_PTY_MEANINGS = {
    "0": "강수없음",
    "1": "비",
    "2": "진눈깨비",
    "3": "눈",
    "4": "소나기",
    "5": "소낙눈",
    "6": "어는 비(얼음)",
    "7": "눈날림",
}

# SKY(하늘상태): 1=맑음, 3=구름많음, 4=흐림
STANDARD_SKY_MEANINGS = {
    "1": "맑음",
    "3": "구름많음",
    "4": "흐림",
}

# 모든 룰의 kma_fields 가 가져야 할 표준 키 (없으면 빈 문자열로 보강)
STANDARD_KMA_FIELDS = ["TMP", "PTY", "SKY", "POP", "WSD", "notes"]

# 기존에 보강이 필요한 기온 구간 (기존 0~5 보다 낮은 구간)
ADDITIONAL_TEMP_RANGES = [
    {
        "id": "temp_below_zero",
        "temperature_range": "-10~0도",
        "season": "한겨울",
        "description": "한파. 방한 극대화, 노출 부위 최소화.",
        "required_items": ["롱패딩", "두꺼운 코트", "히트텍 내복", "털모자", "목도리", "장갑", "방한 귀마개"],
        "recommended_tops": ["두꺼운 니트", "기모 맨투맨", "기모 후드티"],
        "recommended_bottoms": ["기모 데님", "기모 슬랙스", "방한 레깅스"],
        "recommended_shoes": ["방한 부츠", "털달린 스노우부츠"],
        "layering": "내복 → 두꺼운 니트 → 패딩 또는 롱코트 → 방한 액세서리 4레이어 이상",
        "avoid": ["얇은 자켓", "운동화 단독", "수면 양말 단독"],
        "styling_tip": "체감온도 -10도 이하로 떨어질 수 있음. 머리·목·손목 노출을 최소화.",
        "kma_fields": {
            "TMP": "-10~0도 범위",
            "PTY": "3(눈), 5(소낙눈), 7(눈날림), 0 (강수없음)",
            "SKY": "1(맑음), 4(흐림) - 맑은 날도 야간 급격히 냉각",
            "POP": "0~40% - 강설 시 야외 활동 자제",
            "WSD": "8m/s 이상 시 체감온도 추가 하락",
            "notes": "한파주의보/경보 발효 시 외출 자제, 동상·저체온증 주의. 보온에 집중.",
        },
    },
]


def load_rules(path: Path) -> list:
    """원본 룰 JSON 로드. 루트는 배열."""
    return json.loads(path.read_text(encoding="utf-8"))


def validate_pty_meaning(meaning: dict) -> list:
    """PTY_code_meaning dict 가 표준 키 0~7 을 모두 포함하는지 검증. 누락 키 목록 반환."""
    missing = []
    for code in STANDARD_PTY_MEANINGS:
        if code not in meaning:
            missing.append(code)
    return missing


def validate_sky_meaning(meaning: dict) -> list:
    """SKY_code_meaning dict 가 표준 키 1, 3, 4 를 모두 포함하는지 검증."""
    return [c for c in STANDARD_SKY_MEANINGS if c not in meaning]


def ensure_kma_fields(rule: dict, report: dict) -> dict:
    """룰의 kma_fields 가 표준 키를 모두 갖도록 보강. 변경 사실 report 에 기록."""
    kma = rule.setdefault("kma_fields", {})
    added = []
    for key in STANDARD_KMA_FIELDS:
        if key not in kma:
            kma[key] = ""  # 데이터 부재는 빈 문자열로 명시
            added.append(key)
    if added:
        report.setdefault("kma_fields_added", []).append({"id": rule.get("id"), "added": added})
    return rule


def fill_empty_required_items(rule: dict, report: dict) -> dict:
    """required_items 가 비어 있으면 weather_condition / temperature_range 로부터 보수적으로 채움."""
    required = rule.get("required_items")
    if not isinstance(required, list) or len(required) > 0:
        return rule

    rid = rule.get("id", "")
    filler = None
    if rid == "temp_20_25":
        filler = ["얇은 가디건 (저녁용)", "자외선 차단 모자"]
    elif rid == "temp_25_30":
        filler = ["얇은 카디건 (실내 냉방용)", "자외선 차단 모자 또는 선글라스"]

    if filler:
        rule["required_items"] = filler
        report.setdefault("required_filled", []).append({"id": rid, "items": filler})
    return rule


def check_existing_temp_ranges(rules: list) -> set:
    """기존 룰에 정의된 기온 구간 id 집합 반환."""
    return {r.get("id") for r in rules if str(r.get("id", "")).startswith("temp_")}


def add_missing_temp_ranges(rules: list, report: dict) -> list:
    """누락된 기온 구간 룰을 보강해 추가. 기존 룰은 절대 변경/삭제하지 않음."""
    existing = check_existing_temp_ranges(rules)
    added = []
    for new_rule in ADDITIONAL_TEMP_RANGES:
        if new_rule["id"] not in existing:
            rules.append(new_rule)
            added.append(new_rule["id"])
    if added:
        report["temp_ranges_added"] = added
    return rules


def check_pty_meaning_per_rule(rules: list, report: dict) -> None:
    """각 룰의 PTY_code_meaning 표준 키 누락 검증 + 자동 보강."""
    issues = []
    fixed = []
    for r in rules:
        meaning = r.get("kma_fields", {}).get("PTY_code_meaning")
        if not isinstance(meaning, dict):
            continue
        missing = validate_pty_meaning(meaning)
        if missing:
            issues.append({"id": r.get("id"), "missing_codes": missing})
            # 자동 보강 — 표준 키/라벨을 그대로 채움
            for code in missing:
                meaning[code] = STANDARD_PTY_MEANINGS[code]
            fixed.append({"id": r.get("id"), "added": missing})
    if issues:
        report["pty_meaning_issues"] = issues
    if fixed:
        report["pty_meaning_filled"] = fixed


def check_basic_structure(rules: list, report: dict) -> None:
    """모든 룰이 id 와 description 을 갖는지 등 기본 구조 검증."""
    issues = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            issues.append({"index": i, "issue": "not_a_dict"})
            continue
        if "id" not in r or not r["id"]:
            issues.append({"index": i, "issue": "missing_id"})
        if "description" not in r:
            issues.append({"index": i, "id": r.get("id"), "issue": "missing_description"})
    if issues:
        report["structure_issues"] = issues


def build_rules(input_path: Path) -> tuple:
    """원본 룰 로드 → 검증 → 보강 → 결과 반환. (rules, report, error_count)"""
    report: dict = {"input_path": str(input_path)}

    try:
        rules = load_rules(input_path)
    except Exception as e:  # noqa: BLE001
        report["load_error"] = str(e)
        return [], report, 1

    report["original_count"] = len(rules)
    report["original_temp_ids"] = sorted([r.get("id", "") for r in rules if str(r.get("id", "")).startswith("temp_")])
    report["original_weather_ids"] = sorted([r.get("id", "") for r in rules if str(r.get("id", "")).startswith("weather_")])

    check_basic_structure(rules, report)
    check_pty_meaning_per_rule(rules, report)

    # 보강 — 누락된 기온 구간 추가
    rules = add_missing_temp_ranges(rules, report)

    # 보강 — 모든 룰에 kma_fields 표준 키 보강
    for r in rules:
        ensure_kma_fields(r, report)

    # 보강 — required_items 비어있는 룰 채우기
    for r in rules:
        fill_empty_required_items(r, report)

    report["final_count"] = len(rules)
    report["final_temp_ids"] = sorted([r.get("id", "") for r in rules if str(r.get("id", "")).startswith("temp_")])
    report["final_weather_ids"] = sorted([r.get("id", "") for r in rules if str(r.get("id", "")).startswith("weather_")])

    error_count = 0
    error_count += len(report.get("structure_issues", []))
    # pty_meaning_issues 는 자동 보강된 경우(fixed 목록이 있으면) 결함으로 보지 않음
    fixed_pty = report.get("pty_meaning_filled", [])
    if not fixed_pty:
        error_count += len(report.get("pty_meaning_issues", []))
    error_count += len(report.get("load_error", ""))
    report["stats"] = {
        "total": len(rules),
        "original": report["original_count"],
        "added": len(rules) - report["original_count"],
        "errors": error_count,
    }

    return rules, report, error_count


def write_outputs(rules: list, output_path: Path, backup: bool, report: dict, input_path: Path = None) -> None:
    """output 파일 쓰기 + 선택적으로 .bak 백업.

    백업은 output_path 가 기존에 존재하면 그것을 .bak 으로 만든다.
    (input/output 동일 경로에서 --apply 시 원본이 .bak 으로 보존되도록 하기 위함)
    """
    if backup and output_path.exists():
        backup_path = output_path.with_suffix(output_path.suffix + ".bak")
        shutil.copy2(output_path, backup_path)
        report["backup_path"] = str(backup_path)

    output_path.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report["output_path"] = str(output_path)
    report["written"] = True


def main():
    """인자 파싱 → 빌드 → 출력 → 파일 쓰기(apply 시)."""
    parser = argparse.ArgumentParser(description="날씨별 코디 룰 검증/보강")
    parser.add_argument("--input", default="/repo/data/weather/weather_outfit_rules.json", help="원본 룰 JSON 경로")
    parser.add_argument("--output", default=None, help="결과 룰 JSON 경로 (기본: --input 과 동일)")
    parser.add_argument("--apply", action="store_true", help="실제 파일 덮어쓰기 (기본: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="alias: 기본 동작 (실제 파일 안 건드림)")
    parser.add_argument("--backup", action="store_true", default=True, help="--apply 시 .bak 백업 (기본 true; --no-backup 으로 끄기)")
    parser.add_argument("--no-backup", dest="backup", action="store_false", help=".bak 백업 안 만들기")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    rules, report, error_count = build_rules(input_path)
    report["apply"] = bool(args.apply)

    if args.apply:
        try:
            write_outputs(rules, output_path, args.backup, report)
        except Exception as e:  # noqa: BLE001
            report["write_error"] = str(e)
            error_count += 1
            report["stats"]["errors"] = error_count

    print(json.dumps({"stats": report.get("stats", {}), "report": report, "rules": rules}, ensure_ascii=False, indent=2))

    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()