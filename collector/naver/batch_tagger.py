"""
OpenAI Batch API 태깅 (동기 대비 토큰 단가 50% 할인).

흐름:
  1. submit_pending(): tagging_status='pending' 상품을 JSONL로 만들어 배치 제출
     → 해당 상품은 'queued'로 전환 (중복 제출 방지)
  2. poll_batches(): 진행 중 배치 상태 확인
     → completed면 출력 파일을 파싱해 상품별 태그 반영 ('tagged'/'failed')
     → failed/expired/cancelled면 배치 기록 갱신, 상품은 pending으로 복귀
  3. 어떤 배치에도 속하지 않은 'queued' 잔여물은 pending으로 복구

배치 추적 테이블(naver_tagging_batch)의 스키마는 Django migration
(api/apps/catalog/0002)이 소유한다.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import db
from attribute_extractor import extract_attributes
from config import (
    BATCH_COMPLETION_WINDOW,
    BATCH_INCLUDE_IMAGE,
    BATCH_MAX_REQUESTS,
    LLM_TEMPERATURE,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    logger,
)
from llm_tagger import build_messages, merge_tags, response_format

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

# OpenAI Batch 상태값
_OPEN_STATUSES = {"validating", "in_progress", "finalizing"}
_FAIL_STATUSES = {"failed", "expired", "cancelled", "cancelling"}


def _client() -> "OpenAI":
    if OpenAI is None:
        raise RuntimeError("openai 패키지가 없습니다. requirements.naver.txt를 설치하세요.")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY가 없습니다. .env에 설정하세요.")
    return OpenAI(api_key=OPENAI_API_KEY)


# ------------------------------------------------------------
# 제출
# ------------------------------------------------------------


def _build_request_line(product: Dict[str, Any]) -> str:
    """상품 1건 → Batch JSONL 요청 라인. custom_id = naver_product.id"""
    rule_attrs = extract_attributes(product["title"])
    messages = build_messages(
        title=product["title"],
        category_large=product["category_large"],
        category_small=product["category_small"],
        naver_categories=[product.get(f"naver_category{i}") or "" for i in range(1, 5)],
        rule_attrs=rule_attrs,
        image_url=product.get("image_url") if BATCH_INCLUDE_IMAGE else None,
    )
    request = {
        "custom_id": str(product["id"]),
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": OPENAI_MODEL,
            "temperature": LLM_TEMPERATURE,
            "messages": messages,
            "response_format": response_format(),
        },
    }
    return json.dumps(request, ensure_ascii=False)


def submit_pending(conn) -> int:
    """pending 상품 전체를 BATCH_MAX_REQUESTS 단위로 나눠 배치 제출. 제출 건수 반환."""
    client = _client()
    total_submitted = 0

    while True:
        products = db.fetch_pending_products(conn, BATCH_MAX_REQUESTS)
        if not products:
            break

        jsonl = "\n".join(_build_request_line(p) for p in products)
        product_ids = [p["id"] for p in products]

        input_file = client.files.create(
            file=("tagging_batch.jsonl", jsonl.encode("utf-8")),
            purpose="batch",
        )
        batch = client.batches.create(
            input_file_id=input_file.id,
            endpoint="/v1/chat/completions",
            completion_window=BATCH_COMPLETION_WINDOW,
        )

        db.insert_tagging_batch(
            conn, batch.id, OPENAI_MODEL, len(products), BATCH_INCLUDE_IMAGE, input_file.id
        )
        db.set_products_tagging_status(conn, product_ids, "queued")
        total_submitted += len(products)
        logger.info("배치 제출: batch_id=%s, %s건 (이미지 포함=%s)", batch.id, len(products), BATCH_INCLUDE_IMAGE)

    if total_submitted == 0:
        logger.info("배치 제출 대상(pending)이 없습니다.")
    return total_submitted


# ------------------------------------------------------------
# 폴링 / 결과 반영
# ------------------------------------------------------------


def poll_batches(conn) -> int:
    """진행 중 배치 상태 확인 및 완료분 반영. 이번 폴링에서 태깅 반영된 건수 반환."""
    open_batches = db.fetch_open_tagging_batches(conn)
    if not open_batches:
        return 0

    client = _client()
    tagged_total = 0

    for record in open_batches:
        batch = client.batches.retrieve(record["batch_id"])

        if batch.status in _OPEN_STATUSES:
            db.update_tagging_batch(conn, batch.id, batch.status)
            logger.info("배치 진행 중: %s (%s)", batch.id, batch.status)
            continue

        if batch.status in _FAIL_STATUSES:
            error_text = str(getattr(batch, "errors", None) or batch.status)[:1000]
            db.update_tagging_batch(
                conn, batch.id, batch.status, error=error_text, completed=True
            )
            logger.warning("배치 실패: %s (%s) — 상품은 pending으로 복귀합니다.", batch.id, batch.status)
            continue

        if batch.status == "completed":
            tagged = _apply_completed_batch(conn, client, batch)
            tagged_total += tagged
            db.update_tagging_batch(
                conn,
                batch.id,
                "completed",
                output_file_id=batch.output_file_id,
                error_file_id=batch.error_file_id,
                completed=True,
            )
            logger.info("배치 완료 반영: %s, tagged=%s건", batch.id, tagged)

    # 실패/누락으로 queued에 남은 상품 복구 (진행 중 배치가 없을 때만)
    restored = db.reset_orphan_queued_products(conn)
    if restored:
        logger.info("queued 잔여 상품 %s건을 pending으로 복구", restored)

    return tagged_total


def _apply_completed_batch(conn, client, batch) -> int:
    """완료 배치의 출력 파일을 파싱해 상품 태그를 반영한다."""
    lines: List[str] = []
    if batch.output_file_id:
        lines.extend(client.files.content(batch.output_file_id).text.splitlines())

    # 결과 파싱: custom_id → llm_tags | 실패
    results: Dict[int, Dict[str, Any]] = {}
    failed_ids: List[int] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            product_id = int(obj["custom_id"])
            response = obj.get("response") or {}
            if obj.get("error") or response.get("status_code") != 200:
                failed_ids.append(product_id)
                continue
            content = response["body"]["choices"][0]["message"]["content"]
            results[product_id] = json.loads(content)
        except (KeyError, ValueError, TypeError):
            logger.warning("배치 출력 라인 파싱 실패: %s", line[:200])
            continue

    # 에러 파일에 있는 요청도 실패 처리
    if batch.error_file_id:
        for line in client.files.content(batch.error_file_id).text.splitlines():
            try:
                failed_ids.append(int(json.loads(line)["custom_id"]))
            except (KeyError, ValueError, TypeError):
                continue

    # 규칙 추출 재계산 후 병합·반영
    products = db.fetch_products_by_ids(conn, list(results.keys()))
    tagged = 0
    for product_id, llm_tags in results.items():
        product = products.get(product_id)
        if product is None:
            continue
        rule_attrs = extract_attributes(product["title"])
        merged, tag_source = merge_tags(rule_attrs, llm_tags)
        db.update_product_tags(
            conn,
            product_id,
            merged,
            {
                "tagging_status": "tagged",
                "tagging_model": OPENAI_MODEL,
                "tagging_used_image": BATCH_INCLUDE_IMAGE,
                "tag_source": tag_source,
            },
        )
        tagged += 1

    if failed_ids:
        db.set_products_tagging_status(conn, failed_ids, "failed")
        logger.warning("배치 내 실패 요청 %s건 → tagging_status=failed", len(failed_ids))

    return tagged
