from __future__ import annotations

import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

# indexer/ 를 import 루트로 잡아 product_indexer·util 패키지를 찾게 한다.
INDEXER_ROOT = Path(__file__).resolve().parents[2]
if str(INDEXER_ROOT) not in sys.path:
    sys.path.insert(0, str(INDEXER_ROOT))

from product_indexer import product_indexer_api


class ProductIndexerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = product_indexer_api.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            product_indexer_api.ProductIndexerRequestHandler,
        )
        cls.thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_health_does_not_require_authentication(self) -> None:
        response = requests.get(f"{self.base_url}/health", timeout=2)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_trigger_requires_server_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            response = requests.post(
                f"{self.base_url}/v1/product-indexer/drain",
                json={"source": "eleven", "reason": "sync_completed"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 503)

    def test_trigger_rejects_invalid_token(self) -> None:
        with patch.dict(
            os.environ,
            {"PRODUCT_INDEXER_TRIGGER_TOKEN": "correct"},
            clear=True,
        ):
            response = requests.post(
                f"{self.base_url}/v1/product-indexer/drain",
                json={"source": "eleven", "reason": "sync_completed"},
                headers={"Authorization": "Bearer wrong"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 401)

    def test_trigger_starts_drain_and_returns_accepted(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"PRODUCT_INDEXER_TRIGGER_TOKEN": "correct"},
                clear=True,
            ),
            patch.object(
                product_indexer_api.manager,
                "start",
                return_value=("started", 1234),
            ) as start,
        ):
            response = requests.post(
                f"{self.base_url}/v1/product-indexer/drain",
                json={
                    "source": "naver",
                    "reason": "batch_completed",
                    "tagged_count": 4,
                },
                headers={"Authorization": "Bearer correct"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"status": "started", "pid": 1234})
        start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
