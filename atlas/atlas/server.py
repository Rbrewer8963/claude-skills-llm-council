"""Zero-dependency HTTP server exposing the ATLAS engine as a JSON API.

Built on the standard-library ``http.server`` with a threading mixin, so there
is nothing to install and the container stays tiny. The request handler is a
thin adapter: it reads and size-limits the body, decodes JSON, delegates to
:func:`atlas.service.route`, and writes the JSON response. All the logic and
error mapping live in the service layer.

Endpoints
---------
    GET  /health          liveness probe
    GET  /version         service name + version
    POST /analyze         full risk report (risk + MC + stress + compliance)
    POST /risk            risk analytics only
    POST /stress          stress-test suite
    POST /optimize        portfolio construction (min_variance|max_sharpe|risk_parity)
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from .config import Config
from .logging_setup import audit_event, configure
from .service import route

_log = logging.getLogger("atlas")


class _Handler(BaseHTTPRequestHandler):
    server_version = "ATLAS"
    protocol_version = "HTTP/1.1"
    config: Config = Config()

    # Silence the default noisy stderr logging; we log structured lines instead.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: N802
        return

    def _write(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        if length > self.config.max_body_bytes:
            raise _BodyTooLarge(length)
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _dispatch(self, method: str) -> None:
        try:
            body = self._read_body() if method == "POST" else {}
        except _BodyTooLarge as exc:
            self._write(413, {"error": "payload_too_large", "detail": str(exc)})
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._write(400, {"error": "invalid_json", "detail": str(exc)})
            return

        try:
            status, payload = route(method, self.path.split("?")[0], body, self.config)
        except Exception:  # noqa: BLE001 - last-resort guard; never leak a stack trace
            _log.exception("unhandled error", extra={"fields": {"path": self.path}})
            self._write(500, {"error": "internal_error",
                              "detail": "an unexpected error occurred"})
            return

        audit_event("request", method=method, path=self.path.split("?")[0], status=status)
        self._write(status, payload)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")


class _BodyTooLarge(Exception):
    def __init__(self, size: int):
        super().__init__(f"request body {size} bytes exceeds limit")


def make_server(config: Config | None = None) -> ThreadingHTTPServer:
    config = config or Config.from_env()
    configure(config)
    _Handler.config = config
    httpd = ThreadingHTTPServer((config.host, config.port), _Handler)
    return httpd


def serve(config: Config | None = None) -> None:
    config = config or Config.from_env()
    httpd = make_server(config)
    _log.info("atlas server listening", extra={"fields": {
        "host": config.host, "port": config.port}})
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _log.info("shutting down")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
