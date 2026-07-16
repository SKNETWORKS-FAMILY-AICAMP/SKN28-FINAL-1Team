#!/usr/bin/env python3
"""
5.2 - color/combination 룰 검증·보강 파이프라인 (read-only 컨테이너 호환).

역할:
  1) 기존 초안 두 개(color_matching_rules.json, item_combination_rules.json) 로드
  2) polyvore nondisjoint/train.json 일부(기본 5%)에서 통계 집계
     - 카테고리 페어 상위 30개
     - 같은 코디 안에서 자주 공존하는 색상 페어 (description에서 색상 키워드 매칭)
  3) 검증:
     - color: 14개 룰, id 중복 X, best/avoid 비어있지 않음, palette_reference 12색 시즌 표기
     - combination: id 중복 X, 모든 compatible_* 리스트 비어있지 않음 (avoid는 빈 배열 허용)
  4) 보강(보수): 메타 필드 last_updated / source_dataset_stats만 갱신 (id/필드 구조 유지)
  5) 변경 사항은 stdout에 patch(patch_entries + patch_payload) JSON 형식으로 출력.
     호스트(또는 호출자)는 patch_entries에 적힌 파일을 patch_payload로 직접 저장.
     --apply 시점엔 동일 패치를 stdout + 동시에 --patch-out 경로에도 저장.

CLI:
  --dry-run         (기본 True) 변경 없이 검증/통계만 stdout (patch 미출력)
  --apply           patch 출력 -- 파일 변경은 호출자가 책임
  --backup          (기본 True) --apply 시 .bak 1장 생성 (--output-dir 참조)
  --sample-ratio    polyvore train 샘플 비율 (기본 0.05)
  --data-dir        polyvore 데이터 디렉토리 (기본 /tmp/polyvore)
  --color-path      color 룰 JSON 경로 (기본 /repo/data/color/color_matching_rules.json)
  --combination-path combination 룰 JSON 경로
  --output-dir      read-write 가능한 작업 디렉토리 (기본 /tmp/work).
                    --apply + --backup 사용 시 .bak 생성 위치.
  --patch-out       --apply 시 패치 JSON 저장 경로 (기본 /tmp/work/patch.json)

종료 코드:
  0 = 검증 통과
  1 = 검증 실패
  2 = 환경 오류

근거: SKN28-FINAL-1Team 5.2 작업지시 (2026-07-13).
"""

import argparse
import json
import random
import re
import shutil
import sys
from collections import Counter
from pathlib import Path


COLOR_KEYWORDS = {
    "black": "블랙", "white": "화이트", "gray": "그레이", "grey": "그레이",
    "red": "레드", "orange": "오렌지", "yellow": "옐로우", "green": "그린",
    "blue": "블루", "navy": "네이비", "beige": "베이지", "brown": "브라운",
    "pink": "핑크", "purple": "퍼플", "silver": "실버", "gold": "골드",
    "burgundy": "버건디", "olive": "올리브", "khaki": "카키", "cream": "크림",
    "ivory": "아이보리", "tan": "탠", "coral": "코랄", "peach": "피치",
    "lavender": "라벤더", "mint": "민트", "turquoise": "터키석", "teal": "틸",
    "fuchsia": "후크시아", "magenta": "마젠타", "wine": "와인", "mustard": "머스타드",
    "salmon": "새먼", "plum": "자두", "maroon": "마룬", "charcoal": "차콜",
    "rose": "로즈", "mauve": "모브", "indigo": "인디고", "denim": "데님",
    "블랙": "블랙", "화이트": "화이트", "그레이": "그레이", "회색": "그레이",
    "빨강": "레드", "빨간": "레드", "레드": "레드",
    "주황": "오렌지", "주황색": "오렌지", "오렌지": "오렌지",
    "노랑": "옐로우", "노란": "옐로우", "노란색": "옐로우", "옐로우": "옐로우",
    "초록": "그린", "녹색": "그린", "그린": "그린",
    "파랑": "블루", "파란": "블루", "파란색": "블루", "블루": "블루",
    "네이비": "네이비", "베이지": "베이지", "갈색": "브라운", "브라운": "브라운",
    "분홍": "핑크", "핑크": "핑크", "보라": "퍼플", "퍼플": "퍼플",
    "실버": "실버", "골드": "골드", "버건디": "버건디", "올리브": "올리브",
    "카키": "카키", "크림": "크림", "아이보리": "아이보리", "탠": "탠",
    "코랄": "코랄", "피치": "피치", "라벤더": "라벤더", "민트": "민트",
    "와인": "와인", "머스타드": "머스타드", "차콜": "차콜", "데님": "데님",
}


def extract_colors(text: str) -> set:
    if not text:
        return set()
    text_lower = text.lower()
    found = set()
    for word, label in COLOR_KEYWORDS.items():
        if word.isascii() and word.isalpha():
            if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
                found.add(label)
        else:
            if word in text:
                found.add(label)
    return found


def load_polyvore_sample(data_dir: Path, sample_ratio: float, seed: int = 42):
    train_path = data_dir / "train.json"
    meta_path = data_dir / "item_metadata.json"
    if not train_path.exists():
        raise FileNotFoundError(f"missing {train_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"missing {meta_path}")

    rng = random.Random(seed)
    raw = json.loads(train_path.read_text(encoding="utf-8"))
    rng.shuffle(raw)
    n_sample = max(1, int(len(raw) * sample_ratio))
    sample = raw[:n_sample]
    meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))

    cat_pair_counter = Counter()
    color_pair_counter = Counter()
    cat_counts = Counter()
    color_counts = Counter()
    outfit_count_with_color = 0
    outfit_count_with_cat = 0
    skipped_no_meta = 0

    for outfit in sample:
        item_ids = [it["item_id"] for it in outfit["items"]]
        cats = []
        colors = set()
        skip = False
        for iid in item_ids:
            meta = meta_raw.get(iid)
            if not meta:
                skip = True
                break
            sc = meta.get("semantic_category") or "unknown"
            desc = (meta.get("description") or "") + " " + (meta.get("title") or "") + " " + (meta.get("url_name") or "")
            cats.append(sc)
            colors.update(extract_colors(desc))
        if skip:
            skipped_no_meta += 1
            continue

        unique_cats = sorted(set(cats))
        for i in range(len(unique_cats)):
            for j in range(i + 1, len(unique_cats)):
                cat_pair_counter[(unique_cats[i], unique_cats[j])] += 1
        if unique_cats:
            outfit_count_with_cat += 1
            for c in unique_cats:
                cat_counts[c] += 1

        unique_colors = sorted(colors)
        for i in range(len(unique_colors)):
            for j in range(i + 1, len(unique_colors)):
                color_pair_counter[(unique_colors[i], unique_colors[j])] += 1
        if unique_colors:
            outfit_count_with_color += 1
            for c in unique_colors:
                color_counts[c] += 1

    return {
        "stats": {
            "train_outfits_total": len(raw),
            "train_outfits_sampled": n_sample,
            "sample_ratio": sample_ratio,
            "skipped_no_meta": skipped_no_meta,
            "outfit_with_category": outfit_count_with_cat,
            "outfit_with_color": outfit_count_with_color,
            "category_counts_top": cat_counts.most_common(15),
            "color_counts_top": color_counts.most_common(15),
            "category_pairs_top30": [
                {"a": k[0], "b": k[1], "count": v}
                for k, v in cat_pair_counter.most_common(30)
            ],
            "color_pairs_top30": [
                {"a": k[0], "b": k[1], "count": v}
                for k, v in color_pair_counter.most_common(30)
            ],
        }
    }


REQUIRED_PALETTE_HINT = "12색"


def _check_id_unique(rules: list, label: str) -> list:
    errors = []
    seen = {}
    for i, r in enumerate(rules):
        rid = r.get("id")
        if not rid:
            errors.append(f"[{label}][{i}] missing id")
            continue
        if rid in seen:
            errors.append(f"[{label}] duplicated id: {rid}")
        seen[rid] = i
        if " " in rid:
            errors.append(f"[{label}] id contains space: {rid}")
    return errors


def validate_color(rules: list) -> dict:
    errors = []
    if len(rules) != 14:
        errors.append(f"expected 14 skin-tone rules, got {len(rules)}")
    errors += _check_id_unique(rules, "color")
    for i, r in enumerate(rules):
        for k in ("skin_tone_group", "skin_tone_subgroup", "description", "palette_reference"):
            v = r.get(k)
            if not v or not str(v).strip():
                errors.append(f"[color][{i}] ({r.get('id','?')}) missing/empty field: {k}")
        bc = r.get("best_colors")
        ac = r.get("avoid_colors")
        if not isinstance(bc, list) or len(bc) == 0:
            errors.append(f"[color][{i}] ({r.get('id','?')}) best_colors empty or not list")
        if not isinstance(ac, list) or len(ac) == 0:
            errors.append(f"[color][{i}] ({r.get('id','?')}) avoid_colors empty or not list")
        pr = r.get("palette_reference", "")
        if REQUIRED_PALETTE_HINT not in pr:
            errors.append(f"[color][{i}] ({r.get('id','?')}) palette_reference missing '{REQUIRED_PALETTE_HINT}': {pr}")
    return {"valid": len(errors) == 0, "errors": errors, "rule_count": len(rules)}


def validate_combination(rules: list) -> dict:
    errors = []
    if len(rules) < 1:
        errors.append("no combination rules")
    errors += _check_id_unique(rules, "combination")
    for i, r in enumerate(rules):
        for k in ("combination_type", "description"):
            v = r.get(k)
            if not v or not str(v).strip():
                errors.append(f"[combination][{i}] ({r.get('id','?')}) missing/empty field: {k}")
        compat_fields = [k for k in r.keys() if k.startswith("compatible_")]
        if not compat_fields:
            errors.append(f"[combination][{i}] ({r.get('id','?')}) no compatible_* field")
        for cf in compat_fields:
            v = r.get(cf)
            if not isinstance(v, list) or len(v) == 0:
                errors.append(f"[combination][{i}] ({r.get('id','?')}) {cf} empty or not list")
        if "avoid_combinations" in r:
            ac = r["avoid_combinations"]
            if not isinstance(ac, list):
                errors.append(f"[combination][{i}] ({r.get('id','?')}) avoid_combinations not list")
    return {"valid": len(errors) == 0, "errors": errors, "rule_count": len(rules)}


def annotate_meta(rules: list, dataset_meta: dict, last_updated: str) -> tuple:
    """메타 필드 부착. (added_count, modified_count) 반환.

    기존 필드는 절대 변경·삭제하지 않는다. last_updated는 어차피 메타이므로 갱신 허용.
    """
    added = 0
    modified = 0
    for r in rules:
        if "last_updated" in r:
            modified += 1
            r["last_updated"] = last_updated
        else:
            added += 1
            r["last_updated"] = last_updated
        if "source_dataset_stats" in r:
            modified += 1
            r["source_dataset_stats"] = dataset_meta
        else:
            added += 1
            r["source_dataset_stats"] = dataset_meta
    return added, modified


def write_with_backup(src: Path, dst: Path, content: bytes, output_dir: Path) -> dict:
    """호스트 FS에 패치 적용 + .bak 1장.

    - src: 원본 절대 경로 (read-only 컨테이너에서는 못 씀, 정보용으로만 보관)
    - dst: 보통 src와 동일 (호출자가 절대경로/상대경로로 적용)
    - output_dir: 백업 staging 디렉토리 (read-write 보장)
    Returns: {"backup": "..."} or {"backup_skipped": "..."}
    """
    backup_dir = output_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    # .bak 단 한 장 보장
    existing_baks = sorted(backup_dir.glob(f"{src.name}.bak*"))
    if existing_baks:
        return {"backup": str(existing_baks[0]), "backup_status": "kept"}
    bak = backup_dir / f"{src.name}.bak"
    bak.write_bytes(content)
    return {"backup": str(bak), "backup_status": "created"}


def main() -> int:
    p = argparse.ArgumentParser(description="5.2 color/combination 룰 검증·보강")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup", action="store_true", default=True)
    p.add_argument("--sample-ratio", type=float, default=0.05)
    p.add_argument("--data-dir", default="/tmp/polyvore")
    p.add_argument("--color-path", default="/repo/data/color/color_matching_rules.json")
    p.add_argument("--combination-path", default="/repo/data/combination/item_combination_rules.json")
    p.add_argument("--output-dir", default="/tmp/work", help="read-write 작업 디렉토리")
    p.add_argument("--patch-out", default="", help="--apply 시 patch 저장 파일 (기본: output-dir/patch.json)")
    args = p.parse_args()

    if args.apply:
        args.dry_run = False

    color_path = Path(args.color_path)
    combo_path = Path(args.combination_path)

    try:
        color_rules = json.loads(color_path.read_text(encoding="utf-8"))
        combo_rules = json.loads(combo_path.read_text(encoding="utf-8"))
        color_bytes = color_path.read_bytes()
        combo_bytes = combo_path.read_bytes()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(json.dumps({"stage": "load", "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2

    color_val = validate_color(color_rules)
    combo_val = validate_combination(combo_rules)

    stats = {}
    try:
        stats = load_polyvore_sample(Path(args.data_dir), args.sample_ratio)["stats"]
    except FileNotFoundError as e:
        stats = {"error": str(e), "note": "polyvore 데이터 부재, 통계 없이 검증 진행"}

    from datetime import datetime, timezone, timedelta
    KST = timezone(timedelta(hours=9))
    last_updated = datetime.now(KST).strftime("%Y-%m-%d")

    dataset_meta = {
        "sampled_outfits": stats.get("train_outfits_sampled"),
        "sample_ratio": stats.get("sample_ratio"),
        "color_pairs_top5": stats.get("color_pairs_top30", [])[:5],
        "category_pairs_top5": stats.get("category_pairs_top30", [])[:5],
        "generated_at": last_updated,
    }
    if "error" in stats:
        dataset_meta["error"] = stats["error"]

    diff_summary = {
        "color_will_add_meta": not args.dry_run,
        "combination_will_add_meta": not args.dry_run,
        "color_will_add_new_rules": False,
        "combination_will_add_new_rules": False,
        "note": "메타 필드(last_updated, source_dataset_stats)만 부착. 기존 룰 id/필드 구조는 그대로.",
    }

    report = {
        "stage": "report",
        "dry_run": args.dry_run,
        "color_validation": color_val,
        "combination_validation": combo_val,
        "polyvore_stats_summary": {
            "sampled_outfits": stats.get("train_outfits_sampled"),
            "outfit_with_color": stats.get("outfit_with_color"),
            "outfit_with_category": stats.get("outfit_with_category"),
            "skipped_no_meta": stats.get("skipped_no_meta"),
        },
        "polyvore_stats_full": stats,
        "diff_summary": diff_summary,
    }

    if not (color_val["valid"] and combo_val["valid"]):
        # 검증 실패 - 메타 부착 X, 통계만 stdout
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    # --apply: 메모리 상에서 메타 부착 후 patch_payload 생성
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    patch_out = Path(args.patch_out) if args.patch_out else (output_dir / "patch.json")

    color_added, color_modified = annotate_meta(color_rules, dataset_meta, last_updated)
    combo_added, combo_modified = annotate_meta(combo_rules, dataset_meta, last_updated)

    patch_payload = {
        "version": 1,
        "last_updated": last_updated,
        "entries": [
            {
                "path": str(color_path),
                "format": "json",
                "indent": 2,
                "ensure_ascii": False,
                "trailing_newline": True,
                "content": color_rules,
                "backup_source_bytes_len": len(color_bytes),
            },
            {
                "path": str(combo_path),
                "format": "json",
                "indent": 2,
                "ensure_ascii": False,
                "trailing_newline": True,
                "content": combo_rules,
                "backup_source_bytes_len": len(combo_bytes),
            },
        ],
    }

    # patch 저장
    patch_out.write_text(json.dumps(patch_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    backup_info = []
    if args.backup:
        backup_info.append(write_with_backup(color_path, color_path, color_bytes, output_dir))
        backup_info.append(write_with_backup(combo_path, combo_path, combo_bytes, output_dir))

    report["patch_out"] = str(patch_out)
    report["patch_summary"] = {
        "color_meta_added_or_modified": [color_added, color_modified],
        "combo_meta_added_or_modified": [combo_added, combo_modified],
        "backups": backup_info,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
