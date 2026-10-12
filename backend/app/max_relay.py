"""
HTTP-ретранслятор MAX API на network_mode: host (Docker bridge до *.max.ru часто не ходит).

Запуск: python -m app.max_relay
Слушает только 127.0.0.1 — backend ходит через host.docker.internal.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from app.services import max_notify

log = logging.getLogger("app.max.relay")


def _check_secret(handler: BaseHTTPRequestHandler) -> bool:
    expected = (os.environ.get("MAX_RELAY_SECRET") or "").strip()
    if not expected:
        log.error("MAX_RELAY_SECRET не задан — relay не принимает запросы")
        return False
    got = (handler.headers.get("X-Max-Relay-Secret") or "").strip()
    return got == expected


class _RelayHandler(BaseHTTPRequestHandler):
    server_version = "AntrashaMaxRelay/1"

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)

    def do_POST(self) -> None:
        if self.path not in ("/send", "/send/"):
            self.send_error(404)
            return
        if not _check_secret(self):
            self.send_error(403)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
            user_id = int(data["user_id"])
            text = str(data["text"])
            notify = bool(data.get("notify", True))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            self.send_error(400, "JSON: user_id, text, notify?")
            return

        token = (os.environ.get("MAX_BOT_TOKEN") or "").strip()
        if not token:
            self.send_error(503, "MAX_BOT_TOKEN not set on relay")
            return

        try:
            res = max_notify._max_post_messages_via_curl(
                token=token,
                user_id=user_id,
                json_body={"text": text, "notify": notify},
            )
        except Exception as e:
            log.warning("relay curl failed: %s", e)
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            err = json.dumps({"error": str(e)[:500]}, ensure_ascii=False)
            self.end_headers()
            self.wfile.write(err.encode("utf-8"))
            return

        out = json.dumps(
            {"status_code": res.status_code, "body": res.body},
            ensure_ascii=False,
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(out.encode("utf-8"))


def _parse_bind() -> tuple[str, int]:
    raw = (os.environ.get("MAX_RELAY_BIND") or "127.0.0.1:18080").strip()
    host, _, port_s = raw.partition(":")
    port = int(port_s or "18080")
    return host, port


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    host, port = _parse_bind()
    # IPv4-only bind на host
    class _Server(ThreadingHTTPServer):
        address_family = socket.AF_INET

    server = _Server((host, port), _RelayHandler)
    log.info("MAX relay listening on http://%s:%s (POST /send)", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
