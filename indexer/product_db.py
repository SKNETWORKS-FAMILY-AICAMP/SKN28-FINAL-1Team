"""쇼핑 상품 임베딩 worker용 PostgreSQL 작업/상태 계층."""

from __future__ import annotations

from typing import Any

import product_config as config
import psycopg2
from psycopg2.extras import RealDictCursor

_SOURCE_CONFIG = {
    "naver": {
        "table": "naver_product",
        "external_id": "naver_product_id",
        "select": """
            SELECT id, 'naver' AS source,
                   naver_product_id AS external_product_id,
                   title, link, image_url, lprice AS price, mall_name, brand,
                   category_large, category_small,
                   season, style, color, pattern, fit, material, sleeve, length,
                   usage, layer_role, layer_order, tagging_status
            FROM naver_product
            WHERE naver_product_id = %s
        """,
    },
    "eleven": {
        "table": "eleven_product",
        "external_id": "eleven_product_id",
        "select": """
            SELECT id, 'eleven' AS source,
                   eleven_product_id AS external_product_id,
                   title, link, image_url,
                   COALESCE(sale_price, product_price) AS price,
                   mall_name, NULL::text AS brand,
                   category_large, category_small,
                   season, style, color, pattern, fit, material, sleeve, length,
                   usage, layer_role, layer_order, tagging_status
            FROM eleven_product
            WHERE eleven_product_id = %s
        """,
    },
}


def _source_config(source: str) -> dict[str, str]:
    try:
        return _SOURCE_CONFIG[source]
    except KeyError as exc:
        raise ValueError(f"지원하지 않는 상품 source: {source}") from exc


def get_connection():
    if config.DATABASE_URL:
        return psycopg2.connect(config.DATABASE_URL)
    return psycopg2.connect(
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
    )


def reset_stale_jobs(conn, stale_minutes: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE product_embedding_job
            SET status = 'pending',
                claimed_at = NULL,
                available_at = NOW(),
                updated_at = NOW(),
                last_error = COALESCE(
                    last_error,
                    'worker 종료로 인해 stale 작업을 재개함'
                )
            WHERE status = 'processing'
              AND claimed_at < NOW() - (%s * INTERVAL '1 minute')
            """,
            (stale_minutes,),
        )
        count = cur.rowcount
    conn.commit()
    return count


def claim_jobs(
    conn,
    limit: int,
    target_version: str,
) -> list[dict[str, Any]]:
    """처리 가능한 작업을 SKIP LOCKED로 선점하고 시도 횟수를 증가시킨다."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            WITH candidates AS (
                SELECT id
                FROM product_embedding_job
                WHERE status = 'pending'
                  AND available_at <= NOW()
                  AND target_version = %s
                ORDER BY id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE product_embedding_job AS job
            SET status = 'processing',
                attempt_count = job.attempt_count + 1,
                claimed_at = NOW(),
                updated_at = NOW()
            FROM candidates
            WHERE job.id = candidates.id
            RETURNING job.id, job.source, job.external_product_id,
                      job.target_version, job.generation, job.attempt_count
            """,
            (target_version, limit),
        )
        jobs = [dict(row) for row in cur.fetchall()]
        for source in _SOURCE_CONFIG:
            external_ids = [
                job["external_product_id"] for job in jobs if job["source"] == source
            ]
            if not external_ids:
                continue
            source_config = _source_config(source)
            cur.execute(
                f"""
                UPDATE {source_config["table"]}
                SET embedding_status = 'processing',
                    updated_at = NOW()
                WHERE {source_config["external_id"]} = ANY(%s)
                  AND embedding_status = 'pending'
                """,
                (external_ids,),
            )
    conn.commit()
    return jobs


def fetch_product(
    conn,
    source: str,
    external_product_id: str,
) -> dict[str, Any] | None:
    source_config = _source_config(source)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(source_config["select"], (external_product_id,))
        row = cur.fetchone()
    return dict(row) if row else None


def mark_success(
    conn,
    job: dict[str, Any],
    *,
    embedding_version: str,
    image_s3_key: str,
    image_checksum: str,
) -> bool:
    """현재 generation 작업만 완료 처리한다.

    태깅 완료로 generation이 증가한 경우 이전 결과는 Qdrant에 잠시 들어갈 수
    있지만 DB 완료 상태는 쓰지 않고 새 pending 작업이 곧 다시 색인한다.
    """
    source_config = _source_config(job["source"])
    retry_count = max(0, int(job["attempt_count"]) - 1)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE product_embedding_job
            SET status = 'completed',
                last_error = NULL,
                completed_at = NOW(),
                claimed_at = NULL,
                updated_at = NOW()
            WHERE id = %s
              AND generation = %s
              AND status = 'processing'
            RETURNING id
            """,
            (job["id"], job["generation"]),
        )
        accepted = cur.fetchone() is not None
        if accepted:
            cur.execute(
                f"""
                UPDATE {source_config["table"]}
                SET embedding_status = 'completed',
                    embedding_version = %s,
                    embedding_retry_count = %s,
                    embedding_error = NULL,
                    image_s3_key = %s,
                    image_checksum = %s,
                    image_embedded_at = NOW(),
                    text_embedded_at = NOW(),
                    embedded_at = NOW(),
                    updated_at = NOW()
                WHERE {source_config["external_id"]} = %s
                """,
                (
                    embedding_version,
                    retry_count,
                    image_s3_key,
                    image_checksum,
                    job["external_product_id"],
                ),
            )
    conn.commit()
    return accepted


def mark_failure(
    conn,
    job: dict[str, Any],
    error: str,
    *,
    max_retries: int,
    retry_delay_seconds: int,
    transient: bool = True,
) -> str | None:
    """실패를 기록하고 재시도 또는 최종 failed 상태로 전이한다."""
    source_config = _source_config(job["source"])
    max_attempts = 1 + max_retries
    should_retry = transient and int(job["attempt_count"]) < max_attempts
    next_status = "pending" if should_retry else "failed"
    retry_count = max(0, int(job["attempt_count"]) - 1)
    safe_error = error[:4000]

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE product_embedding_job
            SET status = %s,
                last_error = %s,
                available_at = CASE
                    WHEN %s THEN NOW() + (%s * INTERVAL '1 second')
                    ELSE available_at
                END,
                claimed_at = NULL,
                completed_at = NULL,
                updated_at = NOW()
            WHERE id = %s
              AND generation = %s
              AND status = 'processing'
            RETURNING id
            """,
            (
                next_status,
                safe_error,
                should_retry,
                retry_delay_seconds,
                job["id"],
                job["generation"],
            ),
        )
        accepted = cur.fetchone() is not None
        if accepted:
            cur.execute(
                f"""
                UPDATE {source_config["table"]}
                SET embedding_status = %s,
                    embedding_retry_count = %s,
                    embedding_error = %s,
                    updated_at = NOW()
                WHERE {source_config["external_id"]} = %s
                """,
                (
                    next_status,
                    retry_count,
                    safe_error,
                    job["external_product_id"],
                ),
            )
    conn.commit()
    return next_status if accepted else None
