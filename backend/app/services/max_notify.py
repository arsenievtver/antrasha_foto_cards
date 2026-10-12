"""Уведомления о новых заявках на примерку через MAX Bot API."""

from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime

import requests
import urllib3.util.connection as urllib3_connection

from app.config import settings

log = logging.getLogger("app.max")

MAX_API_BASE = "https://platform-api2.max.ru"
MAX_MESSAGES_URL = f"{MAX_API_BASE}/messages"
MAX_ME_URL = f"{MAX_API_BASE}/me"
MAX_UPDATES_URL = f"{MAX_API_BASE}/updates"
MAX_PHOTO_URLS_IN_MESSAGE = 8
MAX_MESSAGE_TEXT_LEN = 4000
# (connect, read)
MAX_HTTP_TIMEOUT = (25.0, 60.0)
_max_ipv4_lock = threading.Lock()


@contextmanager
def _force_ipv4_dns():
    """В bridge-сети Docker AAAA часто «чёрная дыра» → timeout на TLS handshake."""
    with _max_ipv4_lock:
        orig = urllib3_connection.allowed_gai_family

        def _ipv4_only() -> int:
            return socket.AF_INET

        urllib3_connection.allowed_gai_family = _ipv4_only
        try:
            yield
        finally:
            urllib3_connection.allowed_gai_family = orig


def _ssl_verify() -> bool | str:
    bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if bundle and os.path.isfile(bundle):
        return bundle
    default = "/etc/ssl/certs/ca-certificates.crt"
    if os.path.isfile(default):
        return default
    return True


def _authorization_header(raw_token: str) -> str:
    token = raw_token.strip().strip('"').strip("'")
    if token.lower().startswith("bearer "):
        return token
    return token


def max_notify_configured() -> bool:
    return bool(
        settings.max_bot_token
        and str(settings.max_bot_token).strip()
        and settings.max_notify_user_id is not None
    )


def _truncate_message_text(text: str) -> str:
    if len(text) <= MAX_MESSAGE_TEXT_LEN:
        return text
    suffix = "\n… (сообщение обрезано)"
    keep = MAX_MESSAGE_TEXT_LEN - len(suffix)
    return text[:keep] + suffix


def _max_get(*, token: str, url: str, params: dict | None = None) -> requests.Response:
    headers = {"Authorization": _authorization_header(token)}
    verify = _ssl_verify()
    with _force_ipv4_dns():
        return requests.get(
            url,
            params=params,
            headers=headers,
            timeout=MAX_HTTP_TIMEOUT,
            verify=verify,
        )


def _max_post(
    *,
    token: str,
    url: str,
    params: dict[str, int] | None = None,
    json_body: dict | None = None,
) -> requests.Response:
    headers = {
        "Authorization": _authorization_header(token),
        "Content-Type": "application/json",
    }
    verify = _ssl_verify()
    with _force_ipv4_dns():
        return requests.post(
            url,
            params=params,
            headers=headers,
            json=json_body,
            timeout=MAX_HTTP_TIMEOUT,
            verify=verify,
        )


def probe_max_bot_api() -> tuple[bool, str]:
    """Проверка токена и сети (GET /me)."""
    if not settings.max_bot_token or not str(settings.max_bot_token).strip():
        return False, "MAX_BOT_TOKEN не задан"
    token = str(settings.max_bot_token).strip()
    try:
        r = _max_get(token=token, url=MAX_ME_URL)
    except requests.RequestException as e:
        return False, f"сеть/ssl (api2): {e}"
    if r.status_code == 200:
        return True, "GET /me ok"
    if r.status_code == 401:
        return False, "401: неверный MAX_BOT_TOKEN"
    return False, f"GET /me status={r.status_code} body={(r.text or '')[:200]}"


def _collect_human_user_ids(payload: object, out: set[int]) -> None:
    if isinstance(payload, dict):
        uid = payload.get("user_id")
        if isinstance(uid, int) and not payload.get("is_bot"):
            out.add(uid)
        for v in payload.values():
            _collect_human_user_ids(v, out)
    elif isinstance(payload, list):
        for item in payload:
            _collect_human_user_ids(item, out)


def list_recent_max_sender_user_ids(*, limit: int = 20) -> tuple[int, set[int], int | None]:
    """
    GET /updates — user_id людей, писавших боту (для MAX_NOTIFY_USER_ID).
    Возвращает (http_status, user_ids, marker).
    """
    if not settings.max_bot_token or not str(settings.max_bot_token).strip():
        return 0, set(), None
    token = str(settings.max_bot_token).strip()
    r = _max_get(token=token, url=MAX_UPDATES_URL, params={"limit": limit})
    if r.status_code != 200:
        return r.status_code, set(), None
    data = r.json()
    ids: set[int] = set()
    _collect_human_user_ids(data, ids)
    marker = data.get("marker") if isinstance(data, dict) else None
    m = int(marker) if isinstance(marker, int) else None
    return 200, ids, m


def _format_fitting_request_text(
    *,
    heading: str,
    request_id: uuid.UUID,
    display_name: str | None,
    phone: str,
    likes: int,
    total: int,
    match_rate: float,
    note: str | None,
    is_guest: bool,
    liked_photo_urls: list[str],
    created_at: datetime,
) -> str:
    source = "гость (без регистрации)" if is_guest else "зарегистрированный пользователь"
    name_line = display_name.strip() if display_name and display_name.strip() else "—"
    pct = round(match_rate * 100) if total > 0 else 0
    stats = f"{likes} / {total} ({pct}%)" if total > 0 else "без свайпов"

    lines = [
        heading,
        "",
        f"Имя: {name_line}",
        f"Телефон: {phone}",
        f"Свайпы: {stats}",
        f"Источник: {source}",
    ]
    if note and note.strip():
        lines.extend(["", f"Комментарий: {note.strip()}"])
    lines.extend(
        [
            "",
            f"ID заявки: {request_id}",
            f"Время: {created_at.astimezone().strftime('%d.%m.%Y %H:%M %Z')}",
        ],
    )

    urls = [u.strip() for u in liked_photo_urls if u and str(u).strip()]
    if urls:
        lines.append("")
        shown = urls[:MAX_PHOTO_URLS_IN_MESSAGE]
        lines.append(f"Понравившиеся фото ({len(urls)}):")
        for url in shown:
            lines.append(f"• {url}")
        rest = len(urls) - len(shown)
        if rest > 0:
            lines.append(f"… и ещё {rest}")

    return _truncate_message_text("\n".join(lines))


def send_fitting_request_notification(
    *,
    request_id: uuid.UUID,
    display_name: str | None,
    phone: str,
    likes: int,
    total: int,
    match_rate: float,
    note: str | None,
    is_guest: bool,
    liked_photo_urls: list[str],
    created_at: datetime,
    heading: str = "Новая заявка на примерку",
) -> None:
    if not max_notify_configured():
        log.warning("MAX notify skipped request_id=%s: bot not configured", request_id)
        return

    text = _format_fitting_request_text(
        heading=heading,
        request_id=request_id,
        display_name=display_name,
        phone=phone,
        likes=likes,
        total=total,
        match_rate=match_rate,
        note=note,
        is_guest=is_guest,
        liked_photo_urls=liked_photo_urls,
        created_at=created_at,
    )
    token = str(settings.max_bot_token).strip()
    user_id = int(settings.max_notify_user_id)  # type: ignore[arg-type]

    try:
        r = _max_post(
            token=token,
            url=MAX_MESSAGES_URL,
            params={"user_id": user_id},
            json_body={"text": text, "notify": True},
        )
        if r.status_code >= 400:
            log.warning(
                "MAX notify failed request_id=%s user_id=%s status=%s body=%s",
                request_id,
                user_id,
                r.status_code,
                (r.text or "")[:500],
            )
            return
        log.info("MAX notify sent request_id=%s user_id=%s", request_id, user_id)
    except requests.RequestException as e:
        log.warning(
            "MAX notify error request_id=%s user_id=%s: %s",
            request_id,
            user_id,
            e,
        )
