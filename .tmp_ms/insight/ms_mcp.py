"""Минимальный клиент MCP МойСклад для локальных выгрузок.

URL берётся из ~/.cursor/mcp.json (сервер moysklad-all), в репозиторий не пишется.
Ответы кешируются в .tmp_ms/insight/cache, чтобы повторные прогоны не ходили в API.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)


def _server_url() -> str:
    cfg = json.loads(Path(os.path.expanduser("~/.cursor/mcp.json")).read_text())
    return cfg["mcpServers"]["moysklad-all"]["url"]


class MsMcp:
    def __init__(self) -> None:
        self.url = _server_url()
        self.session: str | None = None
        self._id = 0
        self._init()

    def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            # Cloudflare перед mcp-ms.com режет дефолтный User-Agent urllib (error 1010).
            "User-Agent": "Mozilla/5.0 antrasha-insight",
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=headers)
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    sid = resp.headers.get("Mcp-Session-Id")
                    if sid:
                        self.session = sid
                    body = resp.read().decode()
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 5:
                    raise
                time.sleep(5 * (attempt + 1))
        if not body.strip():
            return None
        if body.lstrip().startswith("{"):
            return json.loads(body)
        result = None
        for line in body.splitlines():
            if line.startswith("data:"):
                msg = json.loads(line[5:].strip())
                if "result" in msg or "error" in msg:
                    result = msg
        return result

    def _rpc(self, method: str, params: dict[str, Any]) -> Any:
        self._id += 1
        msg = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        if msg is None:
            raise RuntimeError(f"empty response for {method}")
        if "error" in msg:
            raise RuntimeError(msg["error"])
        return msg["result"]

    def _init(self) -> None:
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "antrasha-insight", "version": "0.1"},
            },
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, tool: str, args: dict[str, Any], *, cache: bool = True) -> Any:
        key = hashlib.sha1(json.dumps([tool, args], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = CACHE / f"{tool}_{key[:16]}.json"
        if cache and path.exists():
            return json.loads(path.read_text())
        res = self._rpc("tools/call", {"name": tool, "arguments": args})
        texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        raw = "\n".join(texts)
        if res.get("isError"):
            raise RuntimeError(f"{tool}: {raw[:500]}")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"{tool}: non-JSON response: {raw[:500]}")
        path.write_text(json.dumps(data, ensure_ascii=False))
        return data

    def call_all(self, tool: str, args: dict[str, Any], *, page: int = 1000) -> list[dict[str, Any]]:
        """Все страницы items для инструментов с limit/offset."""
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = self.call(tool, {**args, "limit": page, "offset": offset})
            items = data.get("items") or []
            rows.extend(items)
            total = data.get("total") or 0
            offset += len(items)
            if not items or offset >= total:
                return rows
            time.sleep(0.3)
