from __future__ import annotations

import sys
import unittest
from pathlib import Path

INDEXER_ROOT = Path(__file__).resolve().parents[1]
if str(INDEXER_ROOT) not in sys.path:
    sys.path.insert(0, str(INDEXER_ROOT))

import product_db


class FakeCursor:
    def __init__(self, *, rows=None, one_results=None):
        self.rows = list(rows or [])
        self.one_results = list(one_results or [])
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one_results.pop(0) if self.one_results else None


class FakeConnection:
    def __init__(self, *, rows=None, one_results=None):
        self.cursor_instance = FakeCursor(rows=rows, one_results=one_results)
        self.commits = 0

    def cursor(self, *args, **kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


class ProductDbTests(unittest.TestCase):
    def test_claim_filters_by_worker_version_and_marks_product_processing(self) -> None:
        job = {
            "id": 1,
            "source": "naver",
            "external_product_id": "100",
            "target_version": "test-v1",
            "generation": 1,
            "attempt_count": 1,
        }
        conn = FakeConnection(rows=[job])

        jobs = product_db.claim_jobs(conn, 5, "test-v1")

        self.assertEqual(jobs, [job])
        claim_sql, claim_params = conn.cursor_instance.executed[0]
        self.assertIn("target_version = %s", claim_sql)
        self.assertEqual(claim_params, ("test-v1", 5))
        product_sql, product_params = conn.cursor_instance.executed[1]
        self.assertIn("UPDATE naver_product", product_sql)
        self.assertEqual(product_params, (["100"],))
        self.assertEqual(conn.commits, 1)

    def test_failure_retries_only_twice_after_initial_attempt(self) -> None:
        base_job = {
            "id": 1,
            "source": "eleven",
            "external_product_id": "200",
            "generation": 1,
        }
        retry_conn = FakeConnection(one_results=[(1,)])
        final_conn = FakeConnection(one_results=[(1,)])

        retry_status = product_db.mark_failure(
            retry_conn,
            {**base_job, "attempt_count": 1},
            "temporary",
            max_retries=2,
            retry_delay_seconds=30,
        )
        final_status = product_db.mark_failure(
            final_conn,
            {**base_job, "attempt_count": 3},
            "temporary",
            max_retries=2,
            retry_delay_seconds=30,
        )

        self.assertEqual(retry_status, "pending")
        self.assertEqual(final_status, "failed")
        self.assertEqual(
            retry_conn.cursor_instance.executed[0][1][0],
            "pending",
        )
        self.assertEqual(
            final_conn.cursor_instance.executed[0][1][0],
            "failed",
        )

    def test_stale_generation_cannot_mark_product_completed(self) -> None:
        conn = FakeConnection(one_results=[None])
        job = {
            "id": 1,
            "source": "naver",
            "external_product_id": "100",
            "generation": 1,
            "attempt_count": 1,
        }

        accepted = product_db.mark_success(
            conn,
            job,
            embedding_version="test-v1",
            image_s3_key="products/naver/100/hash.jpg",
            image_checksum="a" * 64,
        )

        self.assertFalse(accepted)
        self.assertEqual(len(conn.cursor_instance.executed), 1)


if __name__ == "__main__":
    unittest.main()
