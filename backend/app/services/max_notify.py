"""Уведомления о новых заявках на примерку через MAX Bot API."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import requests

from app.config import settings

log = logging.getLogger("app.max")

MAX_MESSAGES_URL = "https://platform-api.max.ru/messages"
MAX_PHOTO_URLS_IN_MESSAGE = 8


def max_notify_configured() -> bool:
    return bool(
        settings.max_bot_token
        and str(settings.max_bot_token).strip()
        and settings.max_notify_user_id is not None
    )


def _format_fitting_request_text(
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
) -> str:
    source = "гость (без регистрации)" if is_guest else "зарегистрированный пользователь"
    name_line = display_name.strip() if display_name and display_name.strip() else "—"
    pct = round(match_rate * 100) if total > 0 else 0
    stats = f"{likes} / {total} ({pct}%)" if total > 0 else "без свайпов"

    lines = [
        "Новая заявка на примерку",
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

    return "\n".join(lines)


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
) -> None:
    if not max_notify_configured():
        return

    text = _format_fitting_request_text(
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
        r = requests.post(
            MAX_MESSAGES_URL,
            params={"user_id": user_id},
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
            },
            json={"text": text, "notify": True},
            timeout=(5.0, 15.0),
        )
        if r.status_code >= 400:
            log.warning(
                "MAX notify failed request_id=%s status=%s body=%s",
                request_id,
                r.status_code,
                (r.text or "")[:500],
            )
            return
        log.info("MAX notify sent request_id=%s user_id=%s", request_id, user_id)
    except requests.RequestException as e:
        log.warning("MAX notify error request_id=%s: %s", request_id, e)
