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

# dev.max.ru: основной хост api2; legacy — запасной при сетевых сбоях на новом VPS
MAX_MESSAGES_URLS = (
    "https://platform-api2.max.ru/messages",
    "https://platform-api.max.ru/messages",
)
MAX_ME_URLS = (
    "https://platform-api2.max.ru/me",
    "https://platform-api.max.ru/me",
)
MAX_PHOTO_URLS_IN_MESSAGE = 8
MAX_MESSAGE_TEXT_LEN = 4000
# (connect, read)
MAX_HTTP_TIMEOUT = (25.0, 60.0)
_max_ipv4_lock = threading.Lock()
_max_session: requests.Session | None = None


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


def _max_http_session() -> requests.Session:
    global _max_session
    if _max_session is None:
        _max_session = requests.Session()
    return _max_session


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


def _post_with_fallback(
    *,
    urls: tuple[str, ...],
    params: dict[str, int],
    token: str,
    json_body: dict,
) -> requests.Response:
    last_exc: requests.RequestException | None = None
    session = _max_http_session()
    headers = {
        "Authorization": _authorization_header(token),
        "Content-Type": "application/json",
    }
    verify = _ssl_verify()

    with _force_ipv4_dns():
        for url in urls:
            try:
                return session.post(
                    url,
                    params=params,
                    headers=headers,
                    json=json_body,
                    timeout=MAX_HTTP_TIMEOUT,
                    verify=verify,
                )
            except requests.RequestException as e:
                last_exc = e
                log.warning("MAX API POST failed url=%s: %s", url, e)
        if last_exc is not None:
            raise last_exc
    raise RuntimeError("MAX API: no URLs configured")


def probe_max_bot_api() -> tuple[bool, str]:
    """
    Проверка токена и сети (GET /me). Для диагностики на сервере, не в hot path.
    """
    if not max_notify_configured():
        return False, "MAX_BOT_TOKEN или MAX_NOTIFY_USER_ID не заданы"
    token = str(settings.max_bot_token).strip()
    session = _max_http_session()
    headers = {"Authorization": _authorization_header(token)}
    verify = _ssl_verify()

    with _force_ipv4_dns():
        for url in MAX_ME_URLS:
            try:
                r = session.get(url, headers=headers, timeout=MAX_HTTP_TIMEOUT, verify=verify)
                if r.status_code == 200:
                    return True, "GET /me ok"
                if r.status_code == 401:
                    return False, "401: неверный MAX_BOT_TOKEN"
                return False, f"GET /me status={r.status_code} body={(r.text or '')[:200]}"
            except requests.RequestException as e:
                last = str(e)
        return False, f"сеть/ssl: {last}"


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
        r = _post_with_fallback(
            urls=MAX_MESSAGES_URLS,
            params={"user_id": user_id},
            token=token,
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
