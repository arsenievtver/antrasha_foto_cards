"""In-process TTL cache для analytics operations."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any


class TtlCache:
    def __init__(self, *, default_ttl_sec: float = 600.0, max_items: int = 256) -> None:
        self._ttl = default_ttl_sec
        self._max = max_items
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, Any]] = {}

    def _evict(self) -> None:
        now = time.monotonic()
        dead = [k for k, (exp, _) in self._data.items() if exp <= now]
        for k in dead:
            self._data.pop(k, None)
        while len(self._data) > self._max:
            # drop oldest by expiry
            oldest = min(self._data.items(), key=lambda kv: kv[1][0])[0]
            self._data.pop(oldest, None)

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            exp, value = item
            if exp <= time.monotonic():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, *, ttl_sec: float | None = None) -> None:
        with self._lock:
            self._evict()
            self._data[key] = (time.monotonic() + (ttl_sec if ttl_sec is not None else self._ttl), value)


def cache_key(operation: str, args: dict[str, Any]) -> str:
    payload = json.dumps({"op": operation, "args": args}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


ANALYTICS_CACHE = TtlCache(default_ttl_sec=600.0, max_items=256)
