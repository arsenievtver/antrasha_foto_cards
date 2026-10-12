#!/usr/bin/env python3
"""Кто писал боту: user_id для MAX_NOTIFY_USER_ID. Сначала отправьте боту сообщение из MAX."""

from __future__ import annotations

import requests

from app.services.max_notify import list_recent_max_sender_user_ids


def main() -> None:
    try:
        status, ids, marker = list_recent_max_sender_user_ids(limit=50)
    except requests.RequestException as e:
        print("MAX API недоступен (таймаут/ssl). Повторите через минуту или:")
        print("  docker compose … exec backend curl -4 -sS --cacert /etc/ssl/certs/ca-certificates.crt \\")
        print('    -H "Authorization: <MAX_BOT_TOKEN>" "https://platform-api2.max.ru/updates?limit=20"')
        print("error:", e)
        raise SystemExit(1) from e
    print("updates_http_status=", status)
    print("marker=", marker)
    if status != 200:
        raise SystemExit(1)
    if not ids:
        print(
            "human user_id не найдены. Напишите боту с телефона (тест) и запустите скрипт снова."
        )
        raise SystemExit(2)
    print("candidate MAX_NOTIFY_USER_ID values (люди, не боты):")
    for uid in sorted(ids):
        print(f"  {uid}")


if __name__ == "__main__":
    main()
