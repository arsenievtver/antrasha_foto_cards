#!/usr/bin/env python3
"""Тестовое сообщение в MAX (curl). PYTHONPATH=/app python scripts/test_max_send.py"""

from __future__ import annotations

from app.config import settings
from app.services.max_notify import (
    _max_post_messages_via_curl,
    _max_post_messages_via_relay,
    max_notify_configured,
)


def main() -> None:
    if not max_notify_configured():
        print("MAX не настроен в env")
        raise SystemExit(1)
    uid = int(settings.max_notify_user_id)  # type: ignore[arg-type]
    body = {"text": "Тест заявки (backend)", "notify": True}
    secret_ok = bool((settings.max_relay_secret or "").strip())
    unix = (settings.max_relay_unix or "").strip()
    relay_url = (settings.max_notify_relay_url or "").strip()
    if secret_ok and (unix or relay_url):
        print("via=relay", unix or relay_url)
        res = _max_post_messages_via_relay(user_id=uid, json_body=body)
    else:
        print("via=curl (direct from container — часто не работает на VPS)")
        token = str(settings.max_bot_token).strip()
        res = _max_post_messages_via_curl(token=token, user_id=uid, json_body=body)
    print("status=", res.status_code)
    print("body=", res.body[:400])
    if res.status_code < 200 or res.status_code >= 400:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
