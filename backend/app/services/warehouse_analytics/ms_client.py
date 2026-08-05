"""Синхронный read-only клиент МойСклад Remap 1.2 для analytics."""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.services.warehouse_analytics.constants import MS_API_BASE

log = logging.getLogger("app.warehouse_analytics.ms")


class MoySkladAnalyticsError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class MoySkladAnalyticsClient:
    """Только GET. Bearer token."""

    def __init__(
        self,
        token: str,
        *,
        timeout: float = 60.0,
        proxies: dict[str, str] | None = None,
    ) -> None:
        self._token = token.strip()
        self._timeout = timeout
        self._proxies = proxies
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._token}",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/json",
            }
        )

    def close(self) -> None:
        self._session.close()

    def href(self, entity: str, entity_id: str) -> str:
        return f"{MS_API_BASE}/entity/{entity}/{entity_id}"

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("http") else f"{MS_API_BASE}/{path.lstrip('/')}"
        # requests кодирует params; для filter с `;` и `=` оставляем как есть через list of tuples
        try:
            res = self._session.get(
                url,
                params=params,
                timeout=self._timeout,
                proxies=self._proxies,
            )
        except requests.RequestException as e:
            raise MoySkladAnalyticsError(f"Сеть МойСклад: {e}") from e

        try:
            data = res.json()
        except ValueError:
            data = {"raw": res.text[:400]}

        if res.status_code >= 400:
            err = data.get("errors") if isinstance(data, dict) else None
            if isinstance(err, list) and err:
                msg = err[0].get("error") if isinstance(err[0], dict) else str(err[0])
            else:
                msg = str(data)[:300]
            log.warning("moysklad GET %s HTTP %s: %s", path, res.status_code, msg)
            raise MoySkladAnalyticsError(f"МойСклад HTTP {res.status_code}: {msg}", status=res.status_code)
        return data

    def get_rows(self, path: str, *, params: dict[str, Any] | None = None) -> tuple[list[dict], int]:
        data = self.get(path, params=params)
        if not isinstance(data, dict):
            return [], 0
        rows = data.get("rows")
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        size = int(meta.get("size") or 0) if meta else 0
        if not isinstance(rows, list):
            return [], size
        return [r for r in rows if isinstance(r, dict)], size


def money_rub(value: Any) -> float | None:
    """Суммы Remap API в копейках → рубли."""
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return round(n / 100.0, 2)


def encode_filter(parts: list[str]) -> str:
    return ";".join(parts)
