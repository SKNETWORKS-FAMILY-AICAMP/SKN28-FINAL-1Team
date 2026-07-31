"""GPU 서버에서 product-indexer drain을 시작하는 경량 HTTP API."""

from __future__ import annotations

import json
import logging
import os
import secrets
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

logger = logging.getLogger("product_indexer_api")

TRIGGER_PATH = "/v1/product-indexer/drain"
HEALTH_PATH = "/health"


class DrainProcessManager:
    """한 API 프로세스에서 drain subprocess를 하나만 실행한다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None

    def status(self) -> tuple[bool, int | None]:
        with self._lock:
            if self._process is None:
                return False, None
            if self._process.poll() is not None:
                self._process = None
                return False, None
            return True, self._process.pid

    def start(self) -> tuple[str, int]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return "already_running", self._process.pid

            command = [
                sys.executable,
                "-m",
                "product_indexer.product_indexer",
                "--drain",
            ]
            # 패키지 상대 import가 동작하도록 패키지 상위(/app)에서 실행한다.
            process = subprocess.Popen(
                command,
                cwd=str(Path(__file__).resolve().parents[1]),
            )
            self._process = process
            threading.Thread(
                target=self._wait_for_exit,
                args=(process,),
                daemon=True,
            ).start()
            logger.info("product-indexer drain 시작: pid=%s", process.pid)
            return "started", process.pid

    def _wait_for_exit(self, process: subprocess.Popen[bytes]) -> None:
        return_code = process.wait()
        logger.info(
            "product-indexer drain 종료: pid=%s, return_code=%s",
            process.pid,
            return_code,
        )
        with self._lock:
            if self._process is process:
                self._process = None


manager = DrainProcessManager()


def _authorized(header_value: str | None) -> tuple[bool, bool]:
    """(인증 성공, 서버 token 설정 여부)를 반환한다."""

    expected = os.getenv("PRODUCT_INDEXER_TRIGGER_TOKEN", "").strip()
    if not expected:
        return False, False
    prefix = "Bearer "
    if not header_value or not header_value.startswith(prefix):
        return False, True
    supplied = header_value[len(prefix) :].strip()
    return secrets.compare_digest(supplied, expected), True


class ProductIndexerRequestHandler(BaseHTTPRequestHandler):
    server_version = "SKN28ProductIndexer/1.0"

    def do_GET(self) -> None:
        if self.path != HEALTH_PATH:
            self._json_response(HTTPStatus.NOT_FOUND, {"detail": "not found"})
            return
        running, pid = manager.status()
        self._json_response(
            HTTPStatus.OK,
            {
                "status": "ok",
                "drain_running": running,
                "pid": pid,
            },
        )

    def do_POST(self) -> None:
        if self.path != TRIGGER_PATH:
            self._json_response(HTTPStatus.NOT_FOUND, {"detail": "not found"})
            return

        authorized, configured = _authorized(self.headers.get("Authorization"))
        if not configured:
            self._json_response(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"detail": "trigger token is not configured"},
            )
            return
        if not authorized:
            self._json_response(
                HTTPStatus.UNAUTHORIZED,
                {"detail": "invalid bearer token"},
                extra_headers={"WWW-Authenticate": "Bearer"},
            )
            return

        payload = self._read_json()
        if payload is None:
            return
        if not _valid_payload(payload):
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"detail": "source and reason are required"},
            )
            return

        status, pid = manager.start()
        logger.info(
            "원격 drain 트리거 수신: source=%s, reason=%s, tagged_count=%s, status=%s",
            payload["source"],
            payload["reason"],
            payload.get("tagged_count"),
            status,
        )
        self._json_response(
            HTTPStatus.ACCEPTED,
            {
                "status": status,
                "pid": pid,
            },
        )

    def log_message(self, format: str, *args: Any) -> None:
        logger.info("HTTP %s - %s", self.address_string(), format % args)

    def _read_json(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length < 1 or content_length > 64 * 1024:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"detail": "invalid request body"},
            )
            return None
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"detail": "invalid JSON"},
            )
            return None
        if not isinstance(payload, dict):
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"detail": "JSON object required"},
            )
            return None
        return payload

    def _json_response(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def _valid_payload(payload: dict[str, Any]) -> bool:
    source = payload.get("source")
    reason = payload.get("reason")
    if source not in {"naver", "eleven", "manual"}:
        return False
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 100:
        return False
    tagged_count = payload.get("tagged_count")
    return tagged_count is None or (
        isinstance(tagged_count, int)
        and not isinstance(tagged_count, bool)
        and tagged_count >= 0
    )


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    host = os.getenv("PRODUCT_INDEXER_API_HOST", "0.0.0.0")
    port = int(os.getenv("PRODUCT_INDEXER_API_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), ProductIndexerRequestHandler)
    logger.info("product-indexer API 시작: %s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("product-indexer API 종료 요청")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
