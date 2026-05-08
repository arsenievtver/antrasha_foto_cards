"""HTTP-клиент к Ximilar Fashion Tagging API."""

from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger("app.ximilar")

XIMILAR_DETECT_TAGS_ALL = "https://api.ximilar.com/tagging/fashion/v2/detect_tags_all"
XIMILAR_DETECT_TAGS = "https://api.ximilar.com/tagging/fashion/v2/detect_tags"


def _auth_headers(api_token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Token {api_token.strip()}",
    }


def _body_for_url(image_url: str) -> dict[str, Any]:
    return {"records": [{"_url": image_url}]}


def _http_error_message(r: requests.Response) -> str:
    body = (r.text or "").strip()[:1200]
    if body:
        return f"HTTP {r.status_code} {r.reason}: {body}"
    return f"HTTP {r.status_code} {r.reason} (пустое тело)"


def detect_tags_all(*, image_url: str, api_token: str, timeout: float = 90.0) -> dict[str, Any]:
    """
    Сначала detect_tags_all (все предметы), при 403 — fallback на detect_tags (крупнейший предмет).
    Требуется публичный HTTPS _url. Текст ответа Ximilar при ошибке попадает в исключение (см. логи).
    """
    headers = _auth_headers(api_token)
    body = _body_for_url(image_url)
    attempts: list[tuple[str, str]] = [
        ("detect_tags_all", XIMILAR_DETECT_TAGS_ALL),
        ("detect_tags", XIMILAR_DETECT_TAGS),
    ]
    last_msg = ""
    for name, endpoint in attempts:
        r = requests.post(
            endpoint,
            headers=headers,
            json=body,
            timeout=timeout,
        )
        if r.status_code < 400:
            return r.json()
        last_msg = f"{name} → {_http_error_message(r)}"
        log.warning("ximilar %s", last_msg)
        if r.status_code != 403:
            break
    raise requests.HTTPError(last_msg or "Ximilar: нет ответа")
