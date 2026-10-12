"""Уведомления о новых заявках на примерку через MAX Bot API."""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, TypeVar

import requests
import urllib3.util.connection as urllib3_connection

from app.config import settings

log = logging.getLogger("app.max")

# Docker bridge: AAAA до *.max.ru часто не ходит; патч на весь процесс (как в рабочем one-liner на сервере).
urllib3_connection.allowed_gai_family = lambda: socket.AF_INET

MAX_API_BASE = "https://platform-api2.max.ru"
MAX_MESSAGES_URL = f"{MAX_API_BASE}/messages"
MAX_ME_URL = f"{MAX_API_BASE}/me"
MAX_UPDATES_URL = f"{MAX_API_BASE}/updates"
MAX_PHOTO_URLS_IN_MESSAGE = 8
MAX_MESSAGE_TEXT_LEN = 4000
# (connect, read) — handshake до max.ru с VPS иногда долгий
MAX_HTTP_TIMEOUT = (45.0, 90.0)
_MAX_HTTP_RETRIES = 3

_T = TypeVar("_T")


def _retry_on_timeout(call: Callable[[], _T]) -> _T:
    last: requests.RequestException | None = None
    for attempt in range(_MAX_HTTP_RETRIES):
        try:
            return call()
        except requests.RequestException as e:
            last = e
            if attempt + 1 >= _MAX_HTTP_RETRIES:
                break
            wait = 2.0 * (attempt + 1)
            log.warning("MAX API request retry %s/%s: %s", attempt + 1, _MAX_HTTP_RETRIES, e)
            time.sleep(wait)
    assert last is not None
    raise last


def _ca_bundle_path() -> str | None:
    bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if bundle and os.path.isfile(bundle):
        return bundle
    default = "/etc/ssl/certs/ca-certificates.crt"
    if os.path.isfile(default):
        return default
    return None


def _ssl_verify() -> bool | str:
    return _ca_bundle_path() or True


@dataclass(frozen=True)
class _MaxHttpResult:
    status_code: int
    body: str


_CURL_CODE_SUFFIX = "\n__CURL_HTTP_CODE__="


def _max_post_messages_via_curl(
    *,
    token: str,
    user_id: int,
    json_body: dict,
) -> _MaxHttpResult:
    """На части VPS Python/urllib3 до *.max.ru нестабилен; curl -4 — рабочий путь."""
    ca = _ca_bundle_path()
    cmd: list[str] = [
        "curl",
        "-4",
        "-sS",
        "--connect-timeout",
        "45",
        "--max-time",
        "90",
    ]
    if ca:
        cmd.extend(["--cacert", ca])
    cmd.extend(
        [
            "-X",
            "POST",
            "-H",
            f"Authorization: {_authorization_header(token)}",
            "-H",
            "Content-Type: application/json; charset=utf-8",
            "--data-binary",
            "@-",
            "-w",
            f"{_CURL_CODE_SUFFIX}%{{http_code}}",
            f"{MAX_MESSAGES_URL}?user_id={user_id}",
        ]
    )
    payload = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
    proc = subprocess.run(
        cmd,
        input=payload,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"curl exit {proc.returncode}: {err[:500]}")
    out = (proc.stdout or b"").decode("utf-8", errors="replace")
    if _CURL_CODE_SUFFIX not in out:
        raise RuntimeError(f"curl: unexpected output: {out[:300]}")
    body, _, code_str = out.rpartition(_CURL_CODE_SUFFIX)
    try:
        code = int(code_str.strip())
    except ValueError as e:
        raise RuntimeError(f"curl: bad http code {code_str!r}") from e
    if code <= 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"curl: no HTTP response (code={code_str!r}, exit={proc.returncode}): {err[:500]}"
        )
    return _MaxHttpResult(status_code=code, body=body.strip())


def _max_post_messages_via_relay(
    *,
    user_id: int,
    json_body: dict,
) -> _MaxHttpResult:
    relay = (settings.max_notify_relay_url or "").strip().rstrip("/")
    secret = (settings.max_relay_secret or "").strip()
    if not relay or not secret:
        raise RuntimeError("MAX_NOTIFY_RELAY_URL / MAX_RELAY_SECRET не заданы")
    # До relay на хосте — короткий connect; MAX API делает curl внутри relay
    relay_timeout = (8.0, 120.0)
    r = requests.post(
        f"{relay}/send",
        headers={"X-Max-Relay-Secret": secret, "Content-Type": "application/json"},
        json={"user_id": user_id, **json_body},
        timeout=relay_timeout,
    )
    if r.status_code != 200:
        return _MaxHttpResult(status_code=r.status_code, body=(r.text or "")[:500])
    data = r.json()
    return _MaxHttpResult(
        status_code=int(data.get("status_code") or 0),
        body=str(data.get("body") or ""),
    )


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

    def _do() -> requests.Response:
        return requests.get(
            url,
            params=params,
            headers=headers,
            timeout=MAX_HTTP_TIMEOUT,
            verify=verify,
        )

    return _retry_on_timeout(_do)


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

    def _do() -> requests.Response:
        return requests.post(
            url,
            params=params,
            headers=headers,
            json=json_body,
            timeout=MAX_HTTP_TIMEOUT,
            verify=verify,
        )

    return _retry_on_timeout(_do)


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
    msg_body = {"text": text, "notify": True}

    status_code = 0
    resp_body = ""
    use_relay = bool(
        (settings.max_notify_relay_url or "").strip()
        and (settings.max_relay_secret or "").strip()
    )
    try:
        if use_relay:
            sent = _max_post_messages_via_relay(user_id=user_id, json_body=msg_body)
        else:
            sent = _max_post_messages_via_curl(
                token=token,
                user_id=user_id,
                json_body=msg_body,
            )
        status_code = sent.status_code
        resp_body = sent.body
    except (OSError, RuntimeError, subprocess.TimeoutExpired, requests.RequestException) as curl_err:
        log.warning(
            "MAX notify curl failed request_id=%s: %s; fallback requests",
            request_id,
            curl_err,
        )
        try:
            r = _max_post(
                token=token,
                url=MAX_MESSAGES_URL,
                params={"user_id": user_id},
                json_body=msg_body,
            )
            status_code = r.status_code
            resp_body = r.text or ""
        except requests.RequestException as e:
            log.warning(
                "MAX notify error request_id=%s user_id=%s: %s",
                request_id,
                user_id,
                e,
            )
            return

    if status_code >= 400:
        log.warning(
            "MAX notify failed request_id=%s user_id=%s status=%s body=%s",
            request_id,
            user_id,
            status_code,
            resp_body[:500],
        )
        return
    log.info("MAX notify sent request_id=%s user_id=%s", request_id, user_id)
